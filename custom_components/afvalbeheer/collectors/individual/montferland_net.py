"""
MontferlandNet collector for waste data from Montferland API.
"""
import logging
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_GLASS, WASTE_TYPE_GREEN, WASTE_TYPE_GREY,
    WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER, WASTE_TYPE_TEXTILE
)

_LOGGER = logging.getLogger(__name__)


class MontferlandNetCollector(WasteCollector):
    """
    Collector for Montferland waste data.
    """
    WASTE_TYPE_MAPPING = {
        'Glas': WASTE_TYPE_GLASS,
        'GFT': WASTE_TYPE_GREEN,
        'Rest afval': WASTE_TYPE_GREY,
        'PMD': WASTE_TYPE_PACKAGES,
        'Papier': WASTE_TYPE_PAPER,
        'Textiel': WASTE_TYPE_TEXTILE,
        # 'kerstboom': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "http://afvalwijzer.afvaloverzicht.nl/"
        self.query_start = "?Username=GSD&Password=gsd$2014"
        self.administratie_id = None
        self.adres_id = None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Montferland")
        response = requests.get('{}Login.ashx{}&Postcode={}&Huisnummer={}&Toevoeging='.format(
            self.main_url, self.query_start, self.postcode, self.street_number, self.suffix)).json()

        if not response[0]['AdresID']:
            _LOGGER.error('AdresID not found!')
            return

        if not response[0]['AdministratieID']:
            _LOGGER.error('AdministratieID not found!')
            return

        self.adres_id = response[0]["AdresID"]
        self.administratie_id = response[0]["AdministratieID"]

    def __get_data(self):
        _LOGGER.debug("Fetching data from Montferland")
        data = []

        today = datetime.today()
        year = today.year

        get_url = '{}/OphaalDatums.ashx/{}&ADM_ID={}&ADR_ID={}&Jaar={}'.format(
                self.main_url, self.query_start, self.administratie_id, self.adres_id, year)
        data = requests.get(get_url).json()

        return data

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Montferland API")

        try:
            if not self.administratie_id or not self.adres_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                if not item['Datum']:
                    continue

                waste_type = self.map_waste_type(item['Soort'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['Datum'], '%Y-%m-%dT%H:%M:%S'),
                    waste_type=waste_type,
                    waste_type_slug=item['Soort']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False