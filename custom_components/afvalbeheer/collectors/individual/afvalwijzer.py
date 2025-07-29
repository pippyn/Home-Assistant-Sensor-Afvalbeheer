"""
Afvalwijzer collector for waste data from Afvalwijzer API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_PAPER_PMD, WASTE_TYPE_GREENGREY, WASTE_TYPE_BRANCHES,
    WASTE_TYPE_BULKLITTER, WASTE_TYPE_BULKYGARDENWASTE, WASTE_TYPE_GLASS,
    WASTE_TYPE_GREEN, WASTE_TYPE_KCA_LOCATION, WASTE_TYPE_KCA, WASTE_TYPE_GREY,
    WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER, WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE
)

_LOGGER = logging.getLogger(__name__)


class AfvalwijzerCollector(WasteCollector):
    """
    Collector for Afvalwijzer waste data.
    """
    WASTE_TYPE_MAPPING = {
        'dhm': WASTE_TYPE_PAPER_PMD,
        'restgft': WASTE_TYPE_GREENGREY,
        'takken': WASTE_TYPE_BRANCHES,
        'grofvuil': WASTE_TYPE_BULKLITTER,
        'tuinafval': WASTE_TYPE_BULKYGARDENWASTE,
        'glas': WASTE_TYPE_GLASS,
        'gft': WASTE_TYPE_GREEN,
        'keukenafval': WASTE_TYPE_GREEN,
        'kcalocatie': WASTE_TYPE_KCA_LOCATION,
        'kca': WASTE_TYPE_KCA,
        'restafval': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'gkbp': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstbomen': WASTE_TYPE_TREE,
        'pd': WASTE_TYPE_PACKAGES,
        'md': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.apikey = '5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca'
        self.waste_collector_url = self.waste_collector

    def __get_data(self):
        _LOGGER.debug("Fetching data from Afvalwijzer")
        get_url = 'https://api.{}.nl/webservices/appsinput/?apikey={}&method=postcodecheck&postcode={}&street=&huisnummer={}&toevoeging={}&app_name=afvalwijzer&platform=web&afvaldata={}&langs=nl'.format(
                self.waste_collector_url, self.apikey, self.postcode, self.street_number, self.suffix, datetime.today().strftime('%Y-%m-%d'))
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Afvalwijzer API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            data = []

            if 'ophaaldagen' in response:
                data = data + response['ophaaldagen']['data']

            if 'ophaaldagenNext' in response:
                data = data + response['ophaaldagenNext']['data']

            if not data:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in data:
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