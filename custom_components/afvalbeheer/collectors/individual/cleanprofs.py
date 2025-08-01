"""
Cleanprofs collector for waste data from Cleanprofs API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_GREEN, WASTE_TYPE_GREY

_LOGGER = logging.getLogger(__name__)


class CleanprofsCollector(WasteCollector):
    """
    Collector for Cleanprofs waste data.
    """
    WASTE_TYPE_MAPPING = {
        'GFT': WASTE_TYPE_GREEN,
        'RST': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://cleanprofs.jmsdev.nl/"

    def __get_data(self):
        _LOGGER.debug("Fetching data from Cleanprofs")
        get_url = '{}api/get-plannings-address?zipcode={}&house_number={}'.format(
                self.main_url, self.postcode, self.street_number)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Cleanprofs API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                if not item['full_date']:
                    continue

                waste_type = self.map_waste_type(item['product_name'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['full_date'], '%Y-%m-%d').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['product_name']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False