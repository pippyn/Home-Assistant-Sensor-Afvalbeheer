"""
Opzet collector for waste data from Opzet-based APIs.
Used by 5+ municipalities with common API structure.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_PAPER_PMD, WASTE_TYPE_BRANCHES, WASTE_TYPE_BULKLITTER,
    WASTE_TYPE_GLASS, WASTE_TYPE_GREENGREY, WASTE_TYPE_GREEN, WASTE_TYPE_KCA,
    WASTE_TYPE_GREY_BAGS, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER,
    WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE, OPZET_COLLECTOR_URLS
)

_LOGGER = logging.getLogger(__name__)


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
        'gft': WASTE_TYPE_GREEN,
        'groene container': WASTE_TYPE_GREEN,
        'chemisch': WASTE_TYPE_KCA,
        'kca': WASTE_TYPE_KCA,
        'tariefzak restafval': WASTE_TYPE_GREY_BAGS,
        'restafvalzakken': WASTE_TYPE_GREY_BAGS,
        'rest': WASTE_TYPE_GREY,
        'grijze container': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstb': WASTE_TYPE_TREE,
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

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Opzet")
        response = requests.get(
            "{}/rest/adressen/{}-{}".format(self.main_url, self.postcode, self.street_number), verify=self._verify).json()

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
        get_url = "{}/rest/adressen/{}/afvalstromen".format(
                self.main_url,
                self.bag_id)
        return requests.get(get_url, verify=self._verify)

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

            for item in response:
                if not item['ophaaldatum']:
                    continue

                waste_type = self.map_waste_type(item['menu_title'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['ophaaldatum'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['menu_title'],
                    icon_data=item['icon_data']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False