"""
Opzet collector for waste data from Opzet-based APIs.
Used by 5+ municipalities with common API structure.
"""
import logging
from datetime import datetime
import requests
import socket
from contextlib import contextmanager
import urllib3.util.connection as _urllib3_connection

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_PMD_GREY, WASTE_TYPE_PAPER_PMD, WASTE_TYPE_BRANCHES, WASTE_TYPE_BULKLITTER,
    WASTE_TYPE_GLASS, WASTE_TYPE_GREENGREY, WASTE_TYPE_GREEN, WASTE_TYPE_KCA,
    WASTE_TYPE_GREY_BAGS, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER,
    WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE, OPZET_COLLECTOR_URLS, DEFAULT_REQUEST_TIMEOUT
)

_LOGGER = logging.getLogger(__name__)

@contextmanager
def _force_ipv4_resolution():
    """
    Temporarily force urllib3 to resolve only IPv4 addresses by overriding
    allowed_gai_family(). This is safer than tweaking internal constants like
    HAS_IPV6, and it's scoped to just the wrapped call.
    """
    if _urllib3_connection is None:
        # If urllib3 can't be imported for some reason, just no-op.
        yield
        return

    original = getattr(_urllib3_connection, "allowed_gai_family", None)
    try:
        _urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
        yield
    finally:
        if original is not None:
            _urllib3_connection.allowed_gai_family = original


class OpzetCollector(WasteCollector):
    """
    Collector for Opzet waste data.
    """
    WASTE_TYPE_MAPPING = {
        'pbd/papier': WASTE_TYPE_PAPER_PMD,
        'snoeiafval': WASTE_TYPE_BRANCHES,
        'sloop': WASTE_TYPE_BULKLITTER,
        'glas': WASTE_TYPE_GLASS,
        'duobak': WASTE_TYPE_GREENGREY,
        'groente': WASTE_TYPE_GREEN,
        'etensresten': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        'groene container': WASTE_TYPE_GREEN,
        'chemisch': WASTE_TYPE_KCA,
        'kca': WASTE_TYPE_KCA,
        'tariefzak restafval': WASTE_TYPE_GREY_BAGS,
        'restafvalzakken': WASTE_TYPE_GREY_BAGS,
        'rest+pmd': WASTE_TYPE_PMD_GREY,
        'rest': WASTE_TYPE_GREY,
        'grijze container': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstb': WASTE_TYPE_TREE,
        'plastic': WASTE_TYPE_PACKAGES,
        'pmd': WASTE_TYPE_PACKAGES,
        'pbd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = OPZET_COLLECTOR_URLS[self.waste_collector]
        self.bag_id = None
        if waste_collector == "suez":
            self._verify = False
        else:
            self._verify = True

        self._session = requests.Session()

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Opzet")
        url = "{}/rest/adressen/{}-{}".format(self.main_url, self.postcode, self.street_number)

        with _force_ipv4_resolution():
            response = self._session.get(url, verify=self._verify, timeout=DEFAULT_REQUEST_TIMEOUT).json()

        if not response:
            _LOGGER.error('Address not found!')
            return

        if len(response) > 1 and self.suffix:
            for item in response:
                if item['huisletter'] == self.suffix or item['huisnummerToevoeging'] == self.suffix:
                    self.bag_id = item['bagId']
                    break
        else:
            self.bag_id = response[0]['bagId']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Opzet")
        url = "{}/rest/adressen/{}/afvalstromen".format(self.main_url, self.bag_id)

        with _force_ipv4_resolution():
            return self._session.get(url, verify=self._verify, timeout=DEFAULT_REQUEST_TIMEOUT)

    def __get_calendar(self, year):
        _LOGGER.debug("Fetching calendar for %s from Opzet", year)
        url = "{}/rest/adressen/{}/kalender/{}".format(self.main_url, self.bag_id, year)

        try:
            with _force_ipv4_resolution():
                response = self._session.get(url, verify=self._verify, timeout=DEFAULT_REQUEST_TIMEOUT)
            if response.status_code != 200:
                return []
            data = response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            _LOGGER.debug('Calendar for %s not available: %r', year, exc)
            return []

        return data if isinstance(data, list) else []

    def __get_calendar_dates(self, streams):
        """Return (waste stream, date) pairs from today on, for this year and the next."""
        streams_by_id = {item.get('id'): item for item in streams}
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        dates = []
        for year in (now.year, now.year + 1):
            for entry in self.__get_calendar(year):
                item = streams_by_id.get(entry.get('afvalstroom_id'))
                ophaaldatum = entry.get('ophaaldatum')
                if item and ophaaldatum and ophaaldatum >= today:
                    dates.append((item, ophaaldatum))
        return dates

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Opzet API")

        try:
            if not self.bag_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            # The afvalstromen endpoint only holds the next pickup per waste stream. The calendar endpoint,
            # which the municipalities' own websites use, holds the whole year. Use it when it has dates.
            dates = await self.hass.async_add_executor_job(self.__get_calendar_dates, response)
            if not dates:
                dates = [(item, item['ophaaldatum']) for item in response if item.get('ophaaldatum')]

            for item, ophaaldatum in dates:
                waste_type = self.map_waste_type(item['menu_title'])
                if not waste_type:
                    continue

                # icon_data may not always exist, so we check before using it
                icon_data = item['icon_data'] if 'icon_data' in item else None

                collection = WasteCollection.create(
                    date=datetime.strptime(ophaaldatum, '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['menu_title'],
                    icon_data=icon_data,
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
