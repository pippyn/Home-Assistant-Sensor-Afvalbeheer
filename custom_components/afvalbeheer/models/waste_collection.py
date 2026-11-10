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

    def as_dict(self):
        """Return a JSON-serialisable copy, used to keep the calendar across restarts."""
        return {
            "date": self.date.isoformat(),
            "waste_type": self.waste_type,
            "waste_type_slug": self.waste_type_slug,
            "icon_data": self.icon_data,
        }

    @classmethod
    def from_dict(cls, data, icon_data=None):
        """Rebuild a collection stored by as_dict."""
        return cls.create(
            date=datetime.fromisoformat(data["date"]),
            waste_type=data["waste_type"],
            waste_type_slug=data.get("waste_type_slug"),
            icon_data=icon_data,
        )

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, WasteCollection):
            return (self.date == other.date and self.waste_type == other.waste_type and self.icon_data == other.icon_data)
        return NotImplemented