"""
Irado collector for waste data from Irado API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_GREEN, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER

_LOGGER = logging.getLogger(__name__)


class IradoCollector(WasteCollector):
    """
    Collector for Irado waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'papier': WASTE_TYPE_PAPER,
        'pmd': WASTE_TYPE_PACKAGES,
        'rest': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://irado.nl/wp-json/wsa/v1/"

    def __get_data(self):
        _LOGGER.debug("Fetching data from Irado")
        get_url = '{}location/address/calendar/pickups?zipcode={}&number={}&extention={}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Irado API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            items = response.get("data")
            if not items:
                _LOGGER.error("No waste data found in response object!")
                return

            self.collections.remove_all()

            for item in items:
                waste_type_raw = item.get("type")
                if not waste_type_raw:
                    continue

                waste_type = self.map_waste_type(waste_type_raw)
                if not waste_type:
                    continue

                # New format: date is dd/mm/YYYY
                date_str = item.get("date")
                if not date_str:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(date_str, '%d-%m-%Y').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False