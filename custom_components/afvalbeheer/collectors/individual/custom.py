"""
Custom collector for manually entered waste collection dates.
"""
import logging
from datetime import date, datetime

from ..base import WasteCollector
from ...models import WasteCollection

_LOGGER = logging.getLogger(__name__)


def normalize_custom_dates(dates):
    """
    Return the dates as a sorted list of unique ISO date strings.

    Accepts ISO strings (config flow) as well as date objects (YAML parses
    unquoted dates like 2026-11-03 to datetime.date). Invalid values are skipped.
    """
    normalized = set()
    for value in dates or []:
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            normalized.add(value.isoformat())
            continue
        try:
            normalized.add(datetime.strptime(str(value).strip(), "%Y-%m-%d").date().isoformat())
        except ValueError:
            _LOGGER.warning("Invalid date '%s' for custom collector, skipping", value)
    return sorted(normalized)


class CustomCollector(WasteCollector):
    """
    Collector that uses manually entered dates instead of an API.
    """

    WASTE_TYPE_MAPPING = {}

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, waste_type, dates):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.waste_type = waste_type
        self.dates = dates or []

    async def update(self):
        """Load manually entered dates into the collections repository."""
        self.collections.remove_all()
        if not self.waste_type:
            _LOGGER.warning("Custom collector has no waste type configured, no collections loaded")
            return

        waste_type_slug = self.waste_type.lower().replace(" ", "-")
        for date_str in normalize_custom_dates(self.dates):
            self.collections.add(WasteCollection.create(
                date=datetime.strptime(date_str, "%Y-%m-%d"),
                waste_type=self.waste_type,
                waste_type_slug=waste_type_slug,
            ))
