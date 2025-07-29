"""
DeAfvalApp collector for waste data from DeAfvalApp API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_PLASTIC, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_TREE

_LOGGER = logging.getLogger(__name__)


class DeAfvalAppCollector(WasteCollector):
    """
    Collector for DeAfvalApp waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gemengde plastics': WASTE_TYPE_PLASTIC,
        'zak_blauw': WASTE_TYPE_GREY,
        'pbp': WASTE_TYPE_PACKAGES,
        'rest': WASTE_TYPE_GREY,
        'kerstboom': WASTE_TYPE_TREE
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "http://dataservice.deafvalapp.nl"

    def __get_data(self):
        _LOGGER.debug("Fetching data from DeAfvalApp")
        get_url = '{}/dataservice/DataServiceServlet?service=OPHAALSCHEMA&land=NL&postcode={}&straatId=0&huisnr={}&huisnrtoev={}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using DeAfvalApp API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.text

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for rows in response.strip().split('\n'):
                waste_type = self.map_waste_type(rows.split(';')[0])
                if not waste_type:
                    continue

                for ophaaldatum in rows.split(';')[1:-1]:
                    if not ophaaldatum:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(ophaaldatum, '%d-%m-%Y'),
                        waste_type=waste_type,
                        waste_type_slug=rows.split(';')[0]
                    )
                    if collection not in self.collections:
                        self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False