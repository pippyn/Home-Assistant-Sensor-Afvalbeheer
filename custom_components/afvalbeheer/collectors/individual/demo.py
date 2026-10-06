"""
Demo collector that generates fake collection dates for every known waste type.
Used to test sensors and icons without depending on a real API.
"""
import logging
from datetime import datetime, timedelta

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BRANCHES, WASTE_TYPE_BULKLITTER, WASTE_TYPE_BULKYGARDENWASTE,
    WASTE_TYPE_GLASS, WASTE_TYPE_GREEN, WASTE_TYPE_GREENGREY, WASTE_TYPE_GREY,
    WASTE_TYPE_GREY_BAGS, WASTE_TYPE_KCA, WASTE_TYPE_KCA_LOCATION, WASTE_TYPE_MILIEUB,
    WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER, WASTE_TYPE_PAPER_PMD, WASTE_TYPE_PLASTIC,
    WASTE_TYPE_PMD_GREY, WASTE_TYPE_REMAINDER, WASTE_TYPE_SOFT_PLASTIC, WASTE_TYPE_SORTI,
    WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE,
)

_LOGGER = logging.getLogger(__name__)

# Every waste type constant, plus names that only exist as icon keys
DEMO_WASTE_TYPES = [
    WASTE_TYPE_GREEN, WASTE_TYPE_GLASS, WASTE_TYPE_PAPER, WASTE_TYPE_PACKAGES, WASTE_TYPE_GREY,
    'KCA', WASTE_TYPE_TEXTILE, WASTE_TYPE_TREE, WASTE_TYPE_BULKLITTER, WASTE_TYPE_BULKYGARDENWASTE,
    WASTE_TYPE_PMD_GREY, 'GFTgratis', WASTE_TYPE_SORTI, WASTE_TYPE_PAPER_PMD, 'PBD',
    WASTE_TYPE_PLASTIC, WASTE_TYPE_SOFT_PLASTIC, WASTE_TYPE_BRANCHES, WASTE_TYPE_GREENGREY,
    WASTE_TYPE_GREY_BAGS, WASTE_TYPE_KCA, WASTE_TYPE_KCA_LOCATION, WASTE_TYPE_MILIEUB,
    WASTE_TYPE_REMAINDER,
]

DEMO_REPEAT_DAYS = 14
DEMO_REPEATS = 4


class DemoCollector(WasteCollector):
    """
    Collector that returns fake data for all waste types.
    Two waste types share each day, starting today, so the today/tomorrow
    sensors always have data. Each type repeats every DEMO_REPEAT_DAYS days.
    """
    WASTE_TYPE_MAPPING = {}

    async def update(self):
        _LOGGER.debug("Generating demo waste collection dates")
        self.collections.remove_all()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for index, waste_type in enumerate(DEMO_WASTE_TYPES):
            for repeat in range(DEMO_REPEATS):
                self.collections.add(WasteCollection.create(
                    date=today + timedelta(days=index // 2 + repeat * DEMO_REPEAT_DAYS),
                    waste_type=self.map_waste_type(waste_type),
                    waste_type_slug=waste_type.lower(),
                ))
