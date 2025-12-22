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

    def __fetch_irado_data(self):
        _LOGGER.debug("Fetching data from Irado")

        query_params = "zipcode={}&number={}".format(self.postcode, self.street_number)

        # Add extention only if suffix contains a non-empty string
        if isinstance(self.suffix, str) and self.suffix.strip():
            query_params += "&extention={}".format(self.suffix.strip())

        get_url = "{}location/address/calendar/pickups?{}".format(self.main_url, query_params)
        
        get_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Home-Assistant-Sensor-Afvalbeheer',
        }

        return requests.get(url=get_url, headers=get_headers)

    def __parse_irado_date(self, date_str):
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            _LOGGER.warning("Invalid date format: %s", date_str)
            return None

    async def update(self):
        _LOGGER.debug("Updating waste collection dates using Irado API")

        try:
            r = await self.hass.async_add_executor_job(self.__fetch_irado_data)

            if r.status_code != 200:
                _LOGGER.error("Irado API error %s", r.status_code)
                return
    
            try:
                response = r.json()
            except ValueError:
                _LOGGER.error("Irado API returned invalid JSON: %s", r.text[:500])
                return
           
            items = response.get("data")
            if not items:
                _LOGGER.error("No waste data found in response object!")
                return

            self.collections.remove_all()

            for item in items:
                waste_type_raw = item.get("type")
                date = self.__parse_irado_date(item.get("date"))
                
                if not waste_type_raw or not date:
                    continue

                waste_type = self.map_waste_type(waste_type_raw)
                if not waste_type:
                    _LOGGER.debug("Skipping unknown waste type: %s", waste_type)
                    continue

                collection = WasteCollection.create(
                    date=date,
                    waste_type=waste_type,
                    waste_type_slug=waste_type
                )

                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False