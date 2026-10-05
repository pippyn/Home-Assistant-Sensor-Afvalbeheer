"""
RecycleApp collector for waste data from RecycleApp API.
"""
import logging
from datetime import datetime, timedelta

import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BULKLITTER, WASTE_TYPE_GLASS, WASTE_TYPE_GREEN, WASTE_TYPE_GREY,
    WASTE_TYPE_PAPER, WASTE_TYPE_TEXTILE, WASTE_TYPE_PACKAGES, WASTE_TYPE_PLASTIC,
    WASTE_TYPE_BRANCHES, WASTE_TYPE_SOFT_PLASTIC
)

_LOGGER = logging.getLogger(__name__)


class RecycleApp(WasteCollector):
    """
    Collector for RecycleApp waste data.
    """
    WASTE_TYPE_MAPPING = {
        'grof': WASTE_TYPE_BULKLITTER,
        'groot huisvuil': WASTE_TYPE_BULKLITTER,
        # 'glas': WASTE_TYPE_GLASS,
        'glas': WASTE_TYPE_GLASS,
        # 'duobak': WASTE_TYPE_GREENGREY,
        'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        # 'chemisch': WASTE_TYPE_KCA,
        # 'kca': WASTE_TYPE_KCA,
        'huisvuil': WASTE_TYPE_GREY,
        'rest': WASTE_TYPE_GREY,
        'ordures ménagères': WASTE_TYPE_GREY,
        # 'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        # 'kerstb': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
        'gemengde': WASTE_TYPE_PLASTIC,
        'snoeihout': WASTE_TYPE_BRANCHES,
        'takken': WASTE_TYPE_BRANCHES,
        'zachte plastics': WASTE_TYPE_SOFT_PLASTIC,
        'roze zak': WASTE_TYPE_SOFT_PLASTIC,
        'déchets résiduels': WASTE_TYPE_GREY,
        'déchets ménagers résiduels': WASTE_TYPE_GREY,
        'déchets organiques': WASTE_TYPE_GREEN,
        'omb': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, street_name):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.street_name = street_name
        self.main_url = 'https://api.fostplus.be/recyclecms/public/v1/'
        self.xconsumer = 'recycleapp.be'
        self.postcode_id = ''
        self.street_id = ''
        self._auth_loaded = False
        self._auth_changed = False

    def __get_headers(self):
        _LOGGER.debug("Getting headers for RecycleApp")
        headers = {
            'x-consumer': self.xconsumer,
            'User-Agent': '',
        }
        return headers

    def __get_location_ids(self):
        _LOGGER.debug("Fetching location IDs from RecycleApp")
        response = requests.get(
            "{}zipcodes".format(self.main_url),
            headers=self.__get_headers(),
            params={'q': self.postcode},
        )
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for postcode_id')
            return
        zipcodes = response.json().get('items', [])
        if not zipcodes:
            _LOGGER.error('No postcode found for RecycleApp')
            return

        for zipcode in zipcodes:
            zipcode_id = zipcode['id']
            response = requests.get(
                "{}streets".format(self.main_url),
                headers=self.__get_headers(),
                params={'q': self.street_name, 'zipcodes': zipcode_id},
            )
            if response.status_code != 200:
                _LOGGER.error('Invalid response from server for street_id')
                continue
            streets = response.json().get('items', [])
            if not streets:
                continue

            self.postcode_id = zipcode_id
            for item in streets:
                if item.get('name') == self.street_name or item.get('names', {}).get('nl') == self.street_name:
                    self.street_id = item['id']
                    break
            if not self.street_id:
                self.street_id = streets[0]['id']
            self._auth_changed = True
            return

        _LOGGER.error('No street found for RecycleApp')

    async def __load_auth_data(self):
        """Load persisted RecycleApp auth and location data once."""
        if self._auth_loaded:
            return

        data = await self.async_load_auth_data()
        self._auth_loaded = True

        if not data:
            return

        self.postcode_id = data.get('postcode_id') or ''
        self.street_id = data.get('street_id') or ''

    async def __save_auth_data(self):
        """Persist RecycleApp auth and location data when it changes."""
        if not self._auth_changed:
            return

        await self.async_save_auth_data({
            'postcode_id': self.postcode_id,
            'street_id': self.street_id,
        })
        self._auth_changed = False

    def __get_data(self):
        _LOGGER.debug("Fetching data from RecycleApp")
        startdate = datetime.now().strftime("%Y-%m-%d")
        enddate = (datetime.now() + timedelta(days=+60)).strftime("%Y-%m-%d")
        response = requests.get(
            "{}collections".format(self.main_url),
            headers=self.__get_headers(),
            params={
                'zipcodeId': self.postcode_id,
                'streetId': self.street_id,
                'houseNumber': self.street_number,
                'fromDate': startdate,
                'untilDate': enddate,
                'size': 100,
            },
        )
        return response

    def __clear_location_ids(self):
        self.postcode_id = ''
        self.street_id = ''
        self._auth_changed = True

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using RecycleApp API")

        try:
            await self.__load_auth_data()

            if not self.postcode_id or not self.street_id:
                await self.hass.async_add_executor_job(self.__get_location_ids)
                await self.__save_auth_data()

            if not self.postcode_id or not self.street_id:
                return

            r = await self.hass.async_add_executor_job(self.__get_data)
            if r.status_code in (400, 404):
                await self.hass.async_add_executor_job(self.__clear_location_ids)
                await self.hass.async_add_executor_job(self.__get_location_ids)
                await self.__save_auth_data()
                if self.postcode_id and self.street_id:
                    r = await self.hass.async_add_executor_job(self.__get_data)

            if r.status_code != 200:
                _LOGGER.error('Invalid response from server for collection data')
                return
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            for item in response['items']:
                if not item['timestamp']:
                    continue
                if not item['fraction'] or not 'name' in item['fraction'] or not 'nl' in item['fraction']['name']:
                    continue
                if 'exception' in item and 'replacedBy' in item['exception']:
                    continue

                waste_type = self.map_waste_type(item['fraction']['name']['nl'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['fraction']['name']['nl']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
