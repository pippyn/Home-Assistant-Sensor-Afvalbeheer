"""
Reinis collector for waste data from Reinis-based APIs.
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
    WASTE_TYPE_PAPER, WASTE_TYPE_REMAINDER, WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE
)
from urllib3.exceptions import InsecureRequestWarning


_LOGGER = logging.getLogger(__name__)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class ReinisCollector(WasteCollector):
    """
    Collector for Reinis waste data.
    """
    WASTE_TYPE_MAPPING = {
        'Groente': WASTE_TYPE_GREEN,
        'Plastic': WASTE_TYPE_PACKAGES,
        'Papier': WASTE_TYPE_PAPER,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://reinis.nl"
        self.bagid = None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Reinis")
        
        response = requests.get(
            "{}/adressen/{}:{}{}".format(self.main_url, self.postcode, self.street_number, self.suffix), timeout=60, verify=False).json()
        
        if not response or 'bagid' not in response[0]:
            _LOGGER.error('Address not found!')
            return

        self.bagid = response[0]['bagid']

    def __get_waste_types(self):
        waste_types = requests.get(
            "{}/rest/adressen/{}/afvalstromen/".format(self.main_url, self.bagid), timeout=60, verify=False).json()
        return waste_types

    def __get_data(self):
        _LOGGER.debug("Fetching data from Reinis")
        now = datetime.now()
        data = []
        for year in (now.year, now.year + 1):
            year_data = requests.get(
                "{}/rest/adressen/{}/kalender/{}".format(self.main_url, self.bagid, year),
                timeout=60,
                verify=False,
            ).json()
            if year_data:
                data.extend(year_data)
            else:
                _LOGGER.debug("No Reinis data found for year %s", year)
        return data

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Reinis API")

        try:
            if not self.bagid:
                await self.hass.async_add_executor_job(self.__fetch_address)

            response = await self.hass.async_add_executor_job(self.__get_data)
            waste_types = await self.hass.async_add_executor_job(self.__get_waste_types)

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                waste_type = next((self.map_waste_type(a['title']) for a in waste_types if a['id'] == item['afvalstroom_id']), None)
                
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['ophaaldatum'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['afvalstroom_id']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
