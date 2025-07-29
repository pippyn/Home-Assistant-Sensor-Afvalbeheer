"""
Straatbeeld collector for waste data from Straatbeeld API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_GREEN, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES,
    WASTE_TYPE_PAPER, WASTE_TYPE_TREE
)

_LOGGER = logging.getLogger(__name__)


class StraatbeeldCollector(WasteCollector):
    """
    Collector for Straatbeeld waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'rest': WASTE_TYPE_GREY,
        'pmd': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'kerstboom': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://drimmelen-afvalkalender-api.straatbeeld.online"

    def __get_data(self):
        _LOGGER.debug("Fetching data from Straatbeeld")
        data = {
            "postal_code": self.postcode,
            "house_number": self.street_number,
            "house_letter": self.suffix,
        }

        return requests.post(f"{self.main_url}/find-address", data=data)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Straatbeeld API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            if r.status_code != 200:
                _LOGGER.error('Invalid response from server for collection data')
                return
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            for _, months in response['collections'].items():
                for _, days in months.items():
                    for day in days:

                        date = datetime.strptime(day['date']['formatted'], '%Y-%m-%d')

                        for item in day['data']:

                            waste_type = self.map_waste_type(item['id'])
                            if not waste_type:
                                continue

                            collection = WasteCollection.create(
                                date=date,
                                waste_type=waste_type,
                                waste_type_slug=item['id']
                            )
                            if collection not in self.collections:
                                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False