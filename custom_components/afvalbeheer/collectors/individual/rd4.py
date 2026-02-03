"""
RD4 collector for waste data from RD4 API.
"""
import logging
import re
from datetime import datetime
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BRANCHES, WASTE_TYPE_GREEN, WASTE_TYPE_GREY,
    WASTE_TYPE_PAPER, WASTE_TYPE_TREE, WASTE_TYPE_PACKAGES
)

_LOGGER = logging.getLogger(__name__)


class RD4Collector(WasteCollector):
    """
    Collector for RD4 waste data.
    """
    WASTE_TYPE_MAPPING = {
        'pruning': WASTE_TYPE_BRANCHES,
        # 'sloop': WASTE_TYPE_BULKLITTER,
        # 'glas': WASTE_TYPE_GLASS,
        # 'duobak': WASTE_TYPE_GREENGREY,
        # 'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        # 'chemisch': WASTE_TYPE_KCA,
        # 'kca': WASTE_TYPE_KCA,
        'residual': WASTE_TYPE_GREY,
        # 'plastic': WASTE_TYPE_PACKAGES,
        'paper': WASTE_TYPE_PAPER,
        'best_bag': "best-tas",
        'christmas_trees': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = 'https://data.rd4.nl/api/v1/waste-calendar'
        self.postcode_split = re.search(r"(\d\d\d\d) ?([A-z][A-z])", self.postcode)
        self.postcode = self.postcode_split.group(1) + '+' + self.postcode_split.group(2).upper()

    def __get_data(self):
        _LOGGER.debug("Fetching data from RD4")
        today = datetime.today()
        items = []

        for year in (today.year, today.year + 1):
            response = requests.get(
                '{}?postal_code={}&house_number={}&house_number_extension={}&year={}'.format(
                    self.main_url, self.postcode, self.street_number, self.suffix, year
                )
            )
            year_data = response.json()

            if not year_data or not year_data.get("success"):
                _LOGGER.debug("No RD4 data found for year %s", year)
                continue

            items.extend(year_data["data"]["items"][0])

        return items

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using RD4 API")

        try:
            items = await self.hass.async_add_executor_job(self.__get_data)

            if not items:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            for item in items:

                waste_type = self.map_waste_type(item["type"])
                date = item["date"]

                if not waste_type or not date:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(date, "%Y-%m-%d"),
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
