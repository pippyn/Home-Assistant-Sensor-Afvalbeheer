"""
Base class for all waste collectors.
"""
import logging
from abc import ABC, abstractmethod

from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from ..models import WasteCollectionRepository

_LOGGER = logging.getLogger(__name__)


class WasteCollector(ABC):
    """
    Abstract base class for waste collectors.
    """

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        self.hass = hass
        self.waste_collector = waste_collector
        self.postcode = postcode
        self.street_number = street_number
        self.suffix = suffix
        self.custom_mapping = custom_mapping
        self.collections = WasteCollectionRepository()
        self._auth_store = Store(hass, 1, self._auth_store_key)

    @property
    def _auth_store_key(self):
        """Return a unique storage key for collector authentication data."""
        address = f"{self.postcode}_{self.street_number}_{self.suffix or ''}".lower()
        return f"{DOMAIN}.{self.waste_collector}_{address}_auth"

    @abstractmethod
    async def update(self):
        pass

    async def async_load_auth_data(self):
        """Load persisted collector authentication data."""
        return await self._auth_store.async_load()

    async def async_save_auth_data(self, data):
        """Persist collector authentication data."""
        await self._auth_store.async_save(data)

    def map_waste_type(self, name):
        _LOGGER.debug(f"Mapping waste type for name: {name}")
        if self.custom_mapping:
            for from_type, to_type in self.custom_mapping.items():
                if from_type.lower() in name.lower():
                    return to_type
        for from_type, to_type in self.WASTE_TYPE_MAPPING.items():
            if from_type.lower() in name.lower():
                return to_type
        return name
