"""
WasteCollection model for representing individual waste pickup events.
"""
from datetime import datetime


class WasteCollection(object):
    """
    Represents a waste collection event.
    """

    def __init__(self):
        self.date = None
        self.waste_type = None
        self.waste_type_slug = None
        self.icon_data = None

    @classmethod
    def create(cls, date, waste_type, waste_type_slug, icon_data=None):
        collection = cls()
        collection.date = date
        collection.waste_type = waste_type
        collection.waste_type_slug = waste_type_slug
        collection.icon_data = icon_data
        return collection

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, WasteCollection):
            return (self.date == other.date and self.waste_type == other.waste_type and self.icon_data == other.icon_data)
        return NotImplemented