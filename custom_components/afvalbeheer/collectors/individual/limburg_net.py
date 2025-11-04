"""
LimburgNet collector for waste data from Limburg.net API.
"""
import logging
from datetime import datetime, timedelta
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BULKLITTER, WASTE_TYPE_BULKYGARDENWASTE, WASTE_TYPE_GREEN,
    WASTE_TYPE_GLASS, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER,
    WASTE_TYPE_TEXTILE
)

_LOGGER = logging.getLogger(__name__)


class LimburgNetCollector(WasteCollector):
    """
    Collector for Limburg.net waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'tak-snoeiafval': WASTE_TYPE_BRANCHES,
        # 'gemengde plastics': WASTE_TYPE_PLASTIC,
        'Grofvuil': WASTE_TYPE_BULKLITTER,
        'Groenafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Tuin- En Snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Tuinafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Keukenafval': WASTE_TYPE_GREEN,
        # 'grof huisvuil afroep': WASTE_TYPE_BULKLITTER,
        # 'tak-snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Glas': WASTE_TYPE_GLASS,
        'GFT': WASTE_TYPE_GREEN,
        # 'batterij': WASTE_TYPE_KCA,
        'Huisvuil': WASTE_TYPE_GREY,
        'PMD': WASTE_TYPE_PACKAGES,
        'Papier': WASTE_TYPE_PAPER,
        'Textiel': WASTE_TYPE_TEXTILE,
        # 'kerstboom': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, street_name, city_name):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.city_name = city_name
        self.street_name = street_name.replace(" ", "+")
        self.main_url = "https://limburg.net/api-proxy/public"
        self.city_id = None
        self.street_id = None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Limburg.net")
        response = requests.get('{}/afval-kalender/gemeenten/search?query={}'.format(
            self.main_url, self.city_name), verify='custom_components/afvalbeheer/certificates/limburg_net.pem').json()

        if not response[0]['nisCode']:
            _LOGGER.error('City not found!')
            return

        self.city_id = response[0]["nisCode"]

        response = requests.get('{}/afval-kalender/gemeente/{}/straten/search?query={}'.format(
            self.main_url, self.city_id, self.street_name), verify='custom_components/afvalbeheer/certificates/limburg_net.pem').json()

        if not response[0]['nummer']:
            _LOGGER.error('Street not found!')
            return

        self.street_id = response[0]['nummer']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Limburg.net")
        data = []

        for x in range(0, 3):
            if x == 0:
                today = datetime.today()
            else:
                today = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            year = today.year
            month = today.month
            get_url = '{}/kalender/{}/{}-{}?straatNummer={}&huisNummer={}&toevoeging={}'.format(
                    self.main_url, self.city_id, year, month, self.street_id, self.street_number, self.suffix)
            month_json = requests.get(get_url, verify='custom_components/afvalbeheer/certificates/limburg_net.pem').json()
            data = data + month_json['events']

        return data

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Limburg.net API")

        try:
            if not self.city_id or not self.street_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                if not item['date']:
                    continue

                waste_type = self.map_waste_type(item['title'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['title']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False