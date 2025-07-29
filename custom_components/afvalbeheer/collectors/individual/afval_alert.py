"""
AfvalAlert collector for waste data from AfvalAlert API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_GREEN, WASTE_TYPE_GREY, WASTE_TYPE_MILIEUB, WASTE_TYPE_TREE

_LOGGER = logging.getLogger(__name__)


class AfvalAlertCollector(WasteCollector):
    """
    Collector for AfvalAlert waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'tak-snoeiafval': WASTE_TYPE_BRANCHES,
        # 'gemengde plastics': WASTE_TYPE_PLASTIC,
        # 'grof huisvuil': WASTE_TYPE_BULKLITTER,
        # 'grof huisvuil afroep': WASTE_TYPE_BULKLITTER,
        # 'tak-snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        # 'fles-groen-glas': WASTE_TYPE_GLASS,
        'gft': WASTE_TYPE_GREEN,
        # 'batterij': WASTE_TYPE_KCA,
        'rest': WASTE_TYPE_GREY,
        'milb': WASTE_TYPE_MILIEUB,
        # 'p-k': WASTE_TYPE_PAPER,
        # 'shirt-textiel': WASTE_TYPE_TEXTILE,
        'kerst': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://www.afvalalert.nl/kalender"

    def __get_data(self):
        _LOGGER.debug("Fetching data from AfvalAlert")
        get_url = '{}/{}/{}{}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using AfvalAlert API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response['items']:
                if not item['date']:
                    continue

                waste_type = self.map_waste_type(item['type'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['date'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False