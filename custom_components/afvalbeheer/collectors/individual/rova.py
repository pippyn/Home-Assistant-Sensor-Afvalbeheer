"""
ROVA collector for waste data from ROVA API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_GREEN, WASTE_TYPE_PAPER, WASTE_TYPE_PACKAGES

_LOGGER = logging.getLogger(__name__)


class ROVACollector(WasteCollector):
    """
    Collector for ROVA waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'papier': WASTE_TYPE_PAPER,
        'pmd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = 'https://www.rova.nl'

    def __get_data(self):
        _LOGGER.debug("Fetching data from ROVA")
        self.today = datetime.today()
        self.year = self.today.year
        response = requests.get(
            '{}/api/waste-calendar/upcoming?houseNumber={}&addition={}&postalcode={}&take=10'.format(self.main_url, self.street_number, self.suffix, self.postcode)
        )
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using ROVA API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                waste_type = self.map_waste_type(item["wasteType"]["title"])
                date = item["date"]

                if not waste_type or not date:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(date, '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item["wasteType"]["title"]
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False