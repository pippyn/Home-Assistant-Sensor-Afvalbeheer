"""
Klikogroep collector for waste data from Klikocontainermanager APIs.
Used by multiple municipalities with common API structure.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_GREEN, WASTE_TYPE_PAPER, WASTE_TYPE_PACKAGES,
    WASTE_TYPE_GREY, KLIKOGROEP_COLLECTOR_IDS
)

_LOGGER = logging.getLogger(__name__)


class KlikogroepCollector(WasteCollector):
    """
    Collector for Klikogroep waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'papier': WASTE_TYPE_PAPER,
        'pmd': WASTE_TYPE_PACKAGES,
        'restafval': WASTE_TYPE_GREY,
        'rest': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        collector_config = KLIKOGROEP_COLLECTOR_IDS[self.waste_collector]
        self.organization_id = collector_config['id']
        self.hostname = collector_config['url']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Klikogroep")
        path = f'/MyKliko/wasteCalendarJSON/{self.organization_id}/{self.postcode}/{self.street_number}'
        url = f'https://{self.hostname}{path}'

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Home-Assistant-Sensor-Afvalbeheer',
        }

        response = requests.get(url, headers=headers, verify=False)
        return response.json()

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Klikogroep API")

        try:
            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response or 'calendar' not in response or not response['calendar']:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            for date_string, trash_types in response['calendar'].items():
                try:
                    date = datetime.strptime(date_string, '%Y-%m-%d')

                    for trash_type_name in trash_types.keys():
                        waste_type = self.map_waste_type(trash_type_name.lower())

                        if not waste_type:
                            continue

                        collection = WasteCollection.create(
                            date=date,
                            waste_type=waste_type,
                            waste_type_slug=trash_type_name.lower()
                        )
                        if collection not in self.collections:
                            self.collections.add(collection)

                except ValueError as e:
                    _LOGGER.warning(f'Error parsing date {date_string}: %r', e)
                    continue

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
