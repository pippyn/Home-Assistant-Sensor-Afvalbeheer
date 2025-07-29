"""
Burgerportaal collector for waste data from Burgerportaal-based APIs.
Used by 10+ municipalities with common API structure.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_GREEN, WASTE_TYPE_PAPER, WASTE_TYPE_PMD_GREY, WASTE_TYPE_GREY,
    BURGERPORTAAL_COLLECTOR_IDS
)

_LOGGER = logging.getLogger(__name__)


class BurgerportaalCollector(WasteCollector):
    """
    Collector for Burgerportaal waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'opk': WASTE_TYPE_PAPER,
        'pmdrest': WASTE_TYPE_PMD_GREY,
        'rest': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.company_code = BURGERPORTAAL_COLLECTOR_IDS[self.waste_collector]
        self.apikey = 'AIzaSyA6NkRqJypTfP-cjWzrZNFJzPUbBaGjOdk'
        self.refresh_token = ''
        self.id_token = ''
        self.address_id = ''

    def __fetch_refresh_token(self):
        _LOGGER.debug("Fetching refresh token from Burgerportaal")
        response = requests.post("https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={}".format(self.apikey)).json()
        if not response:
            _LOGGER.error('Unable to fetch refresh token!')
            return
        self.refresh_token = response['refreshToken']
        self.id_token = response['idToken']

    def __fetch_id_token(self):
        _LOGGER.debug("Fetching ID token from Burgerportaal")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type' : 'refresh_token',
            'refresh_token' : self.refresh_token
        }

        response = requests.post("https://securetoken.googleapis.com/v1/token?key={}".format(self.apikey), headers=headers, data=data).json()
        if not response:
            _LOGGER.error('Unable to fetch ID token!')
            return
        self.id_token = response['id_token']

    def __fetch_address_id(self):
        _LOGGER.debug("Fetching address ID from Burgerportaal")
        headers = {
            'authorization': self.id_token
        }

        response = requests.get("https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{}/address?zipcode={}&housenumber={}".format(
            self.company_code, self.postcode, self.street_number), headers=headers).json()
        if not response:
            _LOGGER.error('Unable to fetch address!')
            return

        for address in response:
            if 'addition' in address and address['addition'] == self.suffix.upper():
                self.address_id = address['addressId']

        if not self.address_id:
            self.address_id = response[-1]['addressId']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Burgerportaal")
        headers = {
            'authorization': self.id_token
        }

        response = requests.get("https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{}/address/{}/calendar".format(
            self.company_code, self.address_id), headers=headers).json()
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Burgerportaal API")

        try:
            if not self.refresh_token:
                await self.hass.async_add_executor_job(self.__fetch_refresh_token)
            else:
                await self.hass.async_add_executor_job(self.__fetch_id_token)

            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address_id)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()
            
            for item in response:
                if not item['collectionDate']:
                    continue

                waste_type = self.map_waste_type(item['fraction'].lower())
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['collectionDate'].split("T")[0], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['fraction'].lower()
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False