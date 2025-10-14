"""
Ximmio collector for waste data from Ximmio-based APIs.
Used by 20+ municipalities with common API structure.
"""
import logging
from datetime import datetime, timedelta
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BRANCHES, WASTE_TYPE_BULKLITTER, WASTE_TYPE_BULKYGARDENWASTE,
    WASTE_TYPE_PMD_GREY, WASTE_TYPE_GLASS, WASTE_TYPE_GREENGREY,
    WASTE_TYPE_GREEN, WASTE_TYPE_GREY, WASTE_TYPE_KCA, WASTE_TYPE_PACKAGES,
    WASTE_TYPE_PAPER, WASTE_TYPE_REMAINDER, WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE,
    XIMMIO_COLLECTOR_IDS
)

_LOGGER = logging.getLogger(__name__)


class XimmioCollector(WasteCollector):
    """
    Collector for Ximmio waste data.
    """
    WASTE_TYPE_MAPPING = {
        'BRANCHES': WASTE_TYPE_BRANCHES,
        'BULKLITTER': WASTE_TYPE_BULKLITTER,
        'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        'BULKYRESTWASTE': WASTE_TYPE_PMD_GREY,
        'GLASS': WASTE_TYPE_GLASS,
        'GREENGREY': WASTE_TYPE_GREENGREY,
        'GREEN': WASTE_TYPE_GREEN,
        'GREY': WASTE_TYPE_GREY,
        'KCA': WASTE_TYPE_KCA,
        'PLASTIC': WASTE_TYPE_PACKAGES,
        'PACKAGES': WASTE_TYPE_PACKAGES,
        'PAPER': WASTE_TYPE_PAPER,
        'REMAINDER': WASTE_TYPE_REMAINDER,
        'TEXTILE': WASTE_TYPE_TEXTILE,
        'TREE': WASTE_TYPE_TREE,
    }

    XIMMIO_URLS = {
        'avalex': "https://wasteprod2api.ximmio.com",
        'meerlanden': "https://wasteprod2api.ximmio.com",
        'rad': "https://wasteprod2api.ximmio.com",
        'westland': "https://wasteprod2api.ximmio.com",
        'woerden': "https://wasteprod2api.ximmio.com",
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, address_id, customer_id):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.postcode = self.postcode.upper()
        if self.waste_collector in self.XIMMIO_URLS.keys():
            self.main_url = self.XIMMIO_URLS[self.waste_collector]
        else:
            self.main_url = "https://wasteapi.ximmio.com"
        self.company_code = XIMMIO_COLLECTOR_IDS[self.waste_collector]
        self.community = ""
        self.customer_id = customer_id
        self.address_id = address_id if address_id else None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Ximmio")
        data = {
            "postCode": self.postcode,
            "houseNumber": self.street_number,
            "companyCode": self.company_code
        }

        if self.customer_id:
            data["commercialNumber"] = self.customer_id

        response = requests.post(
            "{}/api/FetchAdress".format(self.main_url),
            data=data).json()

        if not response['dataList']:
            _LOGGER.error('Address not found!')
            return

        if response['dataList'][0]['Community']:
            self.community = response['dataList'][0]['Community']

        self.address_id = response['dataList'][0]['UniqueId']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Ximmio")
        data = {
            "uniqueAddressID": self.address_id,
            "startDate": datetime.now().strftime('%Y-%m-%d'),
            "endDate": (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
            "companyCode": self.company_code,
            "community": self.community
        }

        if self.customer_id:
            data["isCommercial"] = True

        response = requests.post(
            "{}/api/GetCalendar".format(self.main_url),
            data=data)
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Ximmio API")

        try:
            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response or not response['dataList']:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response['dataList']:
                for date in item['pickupDates']:
                    waste_type = self.map_waste_type(item['_pickupTypeText'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(date, '%Y-%m-%dT%H:%M:%S'),
                        waste_type=waste_type,
                        waste_type_slug=item['_pickupTypeText']
                    )
                    if collection not in self.collections:
                        self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False