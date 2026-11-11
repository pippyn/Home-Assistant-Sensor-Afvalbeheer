"""
Base class for all waste collectors.
"""
import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..models import WasteCollection, WasteCollectionRepository

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
        self.last_update_success = None
        self.last_successful_update = None
        self._update_lock = asyncio.Lock()
        self._auth_store = Store(hass, 1, self._auth_store_key)
        self._collections_identity = {}
        self._collections_store = Store(hass, 1, self._collections_store_key)

    @property
    def _store_address(self):
        return f"{self.postcode}_{self.street_number}_{self.suffix or ''}".lower()

    @property
    def _auth_store_key(self):
        """Return a unique storage key for collector authentication data."""
        return f"{DOMAIN}.{self.waste_collector}_{self._store_address}_auth"

    @property
    def _collections_store_key(self):
        """Return a unique storage key for the last successfully fetched calendar."""
        identity = {"address": self._collections_identity, "mapping": list((self.custom_mapping or {}).items())}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        return f"{DOMAIN}.{self.waste_collector}_{self._store_address}_{digest}_collections"

    def configure_collections_store(self, identity: dict) -> None:
        """Scope cached, mapped dates to the complete configured address.

        Use configuration rather than resolved collector IDs, which can change
        during a refresh. Mapping order matters because the first match wins.
        Authentication storage deliberately keeps its existing key.
        """
        self._collections_identity = identity.copy()
        self._collections_store = Store(self.hass, 1, self._collections_store_key)

    async def update(self) -> bool:
        """Refresh collections, retaining the last valid calendar on failure.

        Implementations build a new repository and publish it only after parsing
        succeeds. A successful empty calendar must explicitly return True too.
        """
        async with self._update_lock:
            previous = self.collections
            self.last_update_success = False
            try:
                success = await self._async_update() is True
                self.last_update_success = success
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                # Payload values and exception messages may contain personal data.
                _LOGGER.error(
                    "Invalid collection response from %s (%s)",
                    self.waste_collector, type(exc).__name__,
                )
                success = False
            finally:
                if not self.last_update_success:
                    self.collections = previous
            if success:
                self.last_successful_update = dt_util.utcnow()
                await self._async_save_collections()
            return success

    @abstractmethod
    async def _async_update(self) -> bool:
        """Build and publish a complete calendar, returning explicit success."""

    async def _async_save_collections(self):
        """Keep the calendar across restarts; icons are stored once per waste type."""
        icons = {}
        collections = []
        for collection in self.collections:
            item = collection.as_dict()
            icon_data = item.pop("icon_data")
            if icon_data is not None:
                icons[collection.waste_type] = icon_data
            collections.append(item)
        try:
            await self._collections_store.async_save({
                "last_successful_update": self.last_successful_update.isoformat(),
                "collections": collections,
                "icons": icons,
            })
        except (HomeAssistantError, OSError) as exc:
            _LOGGER.warning(
                "Could not store the calendar of %s (%s)", self.waste_collector, type(exc).__name__,
            )

    async def async_load_stored_collections(self):
        """Start from the calendar stored after the last successful refresh.

        The stored calendar is only a starting point: the collector still
        refreshes, and its sensors report the data as stale until it succeeds.
        """
        if len(self.collections):
            return
        try:
            data = await self._collections_store.async_load()
        except (HomeAssistantError, OSError) as exc:
            _LOGGER.warning(
                "Could not read the stored calendar of %s (%s)", self.waste_collector, type(exc).__name__,
            )
            return
        if not isinstance(data, dict):
            return
        collections = WasteCollectionRepository()
        try:
            icons = data.get("icons") or {}
            for item in data["collections"]:
                collections.add(WasteCollection.from_dict(item, icons.get(item["waste_type"])))
            last_successful_update = dt_util.parse_datetime(data["last_successful_update"])
        except (AttributeError, KeyError, TypeError, ValueError):
            _LOGGER.warning("Ignoring the unreadable stored calendar of %s", self.waste_collector)
            return
        self.collections = collections
        self.last_successful_update = last_successful_update

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
