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
        self.main_url = 'https://www.recycleapp.be/api/app/v1/'
        self.xsecret = 'Op2tDi2pBmh1wzeC5TaN2U3knZan7ATcfOQgxh4vqC0mDKmnPP2qzoQusmInpglfIkxx8SZrasBqi5zgMSvyHggK9j6xCQNQ8xwPFY2o03GCcQfcXVOyKsvGWLze7iwcfcgk2Ujpl0dmrt3hSJMCDqzAlvTrsvAEiaSzC9hKRwhijQAFHuFIhJssnHtDSB76vnFQeTCCvwVB27DjSVpDmq8fWQKEmjEncdLqIsRnfxLcOjGIVwX5V0LBntVbeiBvcjyKF2nQ08rIxqHHGXNJ6SbnAmTgsPTg7k6Ejqa7dVfTmGtEPdftezDbuEc8DdK66KDecqnxwOOPSJIN0zaJ6k2Ye2tgMSxxf16gxAmaOUqHS0i7dtG5PgPSINti3qlDdw6DTKEPni7X0rxM'
        self.xconsumer = 'recycleapp.be'
        self.accessToken = ''
        self.postcode_id = ''
        self.street_id = ''

    def __get_headers(self):
        _LOGGER.debug("Getting headers for RecycleApp")
        headers = {
            'x-secret': self.xsecret,
            'x-consumer': self.xconsumer,
            'User-Agent': '',
            'Authorization': self.accessToken,
        }
        return headers

    def __get_access_token(self):
        _LOGGER.debug("Fetching access token from RecycleApp")
        response = requests.get("{}access-token".format(self.main_url), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for accessToken')
            return
        self.accessToken = response.json()['accessToken']

    def __get_location_ids(self):
        _LOGGER.debug("Fetching location IDs from RecycleApp")
        response = requests.get("{}zipcodes?q={}".format(self.main_url, self.postcode), headers=self.__get_headers())
        if response.status_code == 401:
            self.__get_access_token()
            response = requests.get("{}zipcodes?q={}".format(self.main_url, self.postcode), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for postcode_id')
            return
        self.postcode_id = response.json()['items'][0]['id']
        response = requests.get("{}streets?q={}&zipcodes={}".format(self.main_url, self.street_name, self.postcode_id), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for street_id')
            return
        for item in response.json()['items']:
            if item['name'] == self.street_name:
                self.street_id = item['id']
        if not self.street_id:
            self.street_id = response.json()['items'][0]['id']

    def __get_data(self):
        _LOGGER.debug("Fetching data from RecycleApp")
        startdate = datetime.now().strftime("%Y-%m-%d")
        enddate = (datetime.now() + timedelta(days=+60)).strftime("%Y-%m-%d")
        response = requests.get("{}collections?zipcodeId={}&streetId={}&houseNumber={}&fromDate={}&untilDate={}&size=100".format(
            self.main_url,
            self.postcode_id,
            self.street_id,
            self.street_number,
            startdate,
            enddate),
            headers=self.__get_headers())
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using RecycleApp API")

        try:
            await self.hass.async_add_executor_job(self.__get_access_token)

            if (not self.postcode_id or not self.street_id) and self.accessToken:
                await self.hass.async_add_executor_job(self.__get_location_ids)

            if not self.postcode_id or not self.street_id or not self.accessToken:
                return

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
                    date=datetime.strptime(item['timestamp'], '%Y-%m-%dT%H:%M:%S.000Z'),
                    waste_type=waste_type,
                    waste_type_slug=item['fraction']['name']['nl']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
