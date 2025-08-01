"""
WasteCollectionRepository for managing waste collection data.
"""
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class WasteCollectionRepository(object):
    """
    Repository for managing waste collections.
    """

    def __init__(self):
        self.collections = []

    def __iter__(self):
        for collection in self.collections:
            yield collection

    def __len__(self):
        return len(self.collections)

    def add(self, collection):
        _LOGGER.debug(f"Adding collection: {collection}")
        self.collections.append(collection)

    def remove_all(self):
        _LOGGER.debug("Removing all collections")
        self.collections = []

    def get_sorted(self):
        _LOGGER.debug("Getting sorted collections")
        return sorted(self.collections, key=lambda x: x.date)

    def get_upcoming(self):
        _LOGGER.debug("Getting upcoming collections")
        today = datetime.now()
        return list(filter(lambda x: x.date.date() >= today.date(), self.get_sorted()))

    def get_first_upcoming(self, waste_types=None):
        _LOGGER.debug(f"Getting first upcoming collection for waste types: {waste_types}")
        upcoming = self.get_upcoming()
        if not upcoming or not waste_types:
            return []
        waste_types_lc = [wt.lower() for wt in waste_types]
        first = next(filter(lambda x: x.waste_type and x.waste_type.lower() in waste_types_lc, upcoming), None)
        if not first:
            return []
        first_date = first.date.date()
        return list(filter(lambda x: x.date.date() == first_date and x.waste_type and x.waste_type.lower() in waste_types_lc, upcoming))
    
    def get_upcoming_by_type(self, waste_type):
        _LOGGER.debug(f"Getting upcoming collections for waste type: {waste_type}")
        today = datetime.now()
        return list(filter(lambda x: x.date.date() >= today.date() and x.waste_type.lower() == waste_type.lower(), self.get_sorted()))

    def get_first_upcoming_by_type(self, waste_type):
        _LOGGER.debug(f"Getting first upcoming collection for waste type: {waste_type}")
        upcoming = self.get_upcoming_by_type(waste_type)
        return upcoming[0] if upcoming else None

    def get_by_date(self, date, waste_types=None):
        _LOGGER.debug(f"Getting collections by date: {date} and waste types: {waste_types}")
        if waste_types:
            return list(filter(lambda x: x.date.date() == date.date() and x.waste_type.lower() in (waste_type.lower() for waste_type in waste_types), self.get_sorted()))
        else:
            return list(filter(lambda x: x.date.date() == date.date(), self.get_sorted()))

    def get_available_waste_types(self):
        _LOGGER.debug("Getting available waste types")
        possible_waste_types = {collection.waste_type for collection in self.collections}
        return sorted(possible_waste_types, key=str.lower)
    
    def get_available_waste_type_slugs(self):
        _LOGGER.debug("Getting available waste type slugs")
        possible_waste_type_slugs = {collection.waste_type_slug for collection in self.collections}
        return sorted(possible_waste_type_slugs, key=str.lower)