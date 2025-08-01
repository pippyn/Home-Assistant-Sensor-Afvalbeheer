"""
Models for waste collection data.
"""
from .waste_collection import WasteCollection
from .waste_repository import WasteCollectionRepository

__all__ = ["WasteCollection", "WasteCollectionRepository"]