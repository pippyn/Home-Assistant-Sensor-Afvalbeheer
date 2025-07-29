"""
Omrin collector for waste data from Omrin API.
"""
import logging
import json
import uuid
from datetime import datetime
import requests
from rsa import pkcs1
from Crypto.PublicKey import RSA
from base64 import b64decode, b64encode

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BULKLITTER, WASTE_TYPE_GREEN, WASTE_TYPE_KCA,
    WASTE_TYPE_SORTI, WASTE_TYPE_PAPER
)

_LOGGER = logging.getLogger(__name__)


class OmrinCollector(WasteCollector):
    """
    Collector for Omrin waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'BRANCHES': WASTE_TYPE_BRANCHES,
        'Grofvuil': WASTE_TYPE_BULKLITTER,
        'Grofvuil en elektrische apparaten': WASTE_TYPE_BULKLITTER,
        # 'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        # 'GLASS': WASTE_TYPE_GLASS,
        'Biobak op afroep': WASTE_TYPE_GREEN,
        'Biobak': WASTE_TYPE_GREEN,
        'GFT': WASTE_TYPE_GREEN,
        # 'GREY': WASTE_TYPE_GREY,
        'KCA': WASTE_TYPE_KCA,
        'Chemisch afval': WASTE_TYPE_KCA,
        'Sortibak': WASTE_TYPE_SORTI,
        'Papier': WASTE_TYPE_PAPER,
        # 'REMAINDER': WASTE_TYPE_REMAINDER,
        # 'TEXTILE': WASTE_TYPE_TEXTILE,
        # 'TREE': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://api-omrin.freed.nl/Account"
        self.appId = uuid.uuid1().__str__()
        self.publicKey = None

    def __fetch_publickey(self):
        _LOGGER.debug("Fetching public key from Omrin")
        response = requests.post("{}/GetToken/".format(self.main_url), json={'AppId': self.appId, 'AppVersion': '', 'OsVersion': '', 'Platform': 'HomeAssistant'}).json()
        self.publicKey = b64decode(response['PublicKey'])

    def __get_data(self):
        _LOGGER.debug("Fetching data from Omrin")
        rsaPublicKey = RSA.importKey(self.publicKey)
        requestBody = {'a': False, 'Email': None, 'Password': None, 'PostalCode': self.postcode, 'HouseNumber': self.street_number}

        encryptedRequest = pkcs1.encrypt(json.dumps(requestBody).encode(), rsaPublicKey)
        base64EncodedRequest = b64encode(encryptedRequest).decode("utf-8")

        response = requests.post("{}/FetchAccount/".format(self.main_url) + self.appId, '"' + base64EncodedRequest + '"', timeout=60).json()
        return response['CalendarV2']

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Omrin API")

        try:
            if not self.publicKey:
                await self.hass.async_add_executor_job(self.__fetch_publickey)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                if not item['Datum']:
                    continue

                if item['Datum'] == '0001-01-01T00:00:00':
                    continue

                waste_type = self.map_waste_type(item['Omschrijving'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['Datum'], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['Omschrijving']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False