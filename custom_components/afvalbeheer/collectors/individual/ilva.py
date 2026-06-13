import logging
from datetime import datetime
import asyncio
from typing import Optional

from homeassistant.helpers.storage import Store
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiohttp

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_GREEN,
    WASTE_TYPE_GREY,
    WASTE_TYPE_PAPER,
    WASTE_TYPE_GLASS,
    WASTE_TYPE_PACKAGES,
    WASTE_TYPE_TREE,
    WASTE_TYPE_TEXTILE,
    WASTE_TYPE_BULKLITTER,
    WASTE_TYPE_KCA,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ILVACollector(WasteCollector):

    WASTE_TYPE_MAPPING = {
        "gft": WASTE_TYPE_GREEN,
        "huisvuil": WASTE_TYPE_GREY,
        "papier": WASTE_TYPE_PAPER,
        "glas": WASTE_TYPE_GLASS,
        "pmd": WASTE_TYPE_PACKAGES,
        "kerst": WASTE_TYPE_TREE,
        "textiel": WASTE_TYPE_TEXTILE,
        "grof": WASTE_TYPE_BULKLITTER,
        "kga": WASTE_TYPE_KCA,
    }

    def __init__(
        self,
        hass,
        waste_collector,
        postcode,
        street_number,
        suffix,
        custom_mapping,
        street_name,
        city_name,
    ):
        super().__init__(
            hass,
            waste_collector,
            postcode,
            street_number,
            suffix,
            custom_mapping,
        )

        self.street_name = street_name
        self.city_name = city_name
        self.base_url = "https://sync-ilva-be.cloud.glue.be/api"
        # ID cache store
        try:
            address = f"{self.postcode}_{self.street_number}_{self.suffix or ''}".lower()
            self._id_store = Store(hass, 1, f"{DOMAIN}.{self.waste_collector}_{address}_idcache")
        except Exception:
            self._id_store = None
        self._cached_ids = {}

    async def async_load_id_cache(self):
        if not self._id_store:
            return
        try:
            data = await self._id_store.async_load()
            if data:
                self._cached_ids = data
        except Exception:
            _LOGGER.debug("No ID cache loaded for ILVA")

    async def async_save_id_cache(self):
        if not self._id_store:
            return
        try:
            await self._id_store.async_save(self._cached_ids)
        except Exception as err:
            _LOGGER.debug("Failed to save ILVA id cache: %s", err)

    async def _fetch_json(self, url: str) -> Optional[dict]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("HTTP error fetching %s: %s", url, err)
            raise

    async def async_get_street_id(self) -> int:
        # Use cache if available
        if "street_id" in self._cached_ids:
            return self._cached_ids["street_id"]

        url = f"{self.base_url}/streets?q={self.street_name}"
        data = await self._fetch_json(url)
        streets = data.get("data", []) if data else []

        candidate_id = None
        for street in streets:
            name = street.get("name", "")
            sub = street.get("sub_municipality") or {}
            zip_code = sub.get("zip") or sub.get("zipcode") or ""
            if name.lower() == (self.street_name or "").lower():
                # Prefer exact postcode match
                if zip_code and zip_code == (self.postcode or ""):
                    candidate_id = street.get("id")
                    break
                # keep as fallback
                if candidate_id is None:
                    candidate_id = street.get("id")

        if candidate_id is None:
            raise Exception(f"Street not found: {self.street_name}")

        self._cached_ids["street_id"] = candidate_id
        await self.async_save_id_cache()
        return candidate_id

    async def async_get_address_id(self, street_id: int) -> int:
        if "address_id" in self._cached_ids:
            return self._cached_ids["address_id"]

        url = f"{self.base_url}/streets/{street_id}/addresses?q={self.street_number}"
        data = await self._fetch_json(url)
        addresses = data.get("data", []) if data else []

        if not addresses:
            raise Exception(f"Address not found: {self.street_number}")

        address_id = addresses[0].get("id")
        self._cached_ids["address_id"] = address_id
        await self.async_save_id_cache()
        return address_id

    async def async_get_collections(self, address_id: int):
        url = f"{self.base_url}/addresses/{address_id}/days"
        data = await self._fetch_json(url)
        return data.get("data", []) if data else []

    async def update(self):
        self.collections.remove_all()
        await self.async_load_id_cache()

        try:
            street_id = await self.async_get_street_id()
            address_id = await self.async_get_address_id(street_id)
            collections = await self.async_get_collections(address_id)

            for item in collections:
                waste_name = item.get("waste_type", {}).get("name", "")
                mapped_type = self.map_waste_type(waste_name)
                try:
                    collection_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
                except Exception:
                    _LOGGER.debug("Skipping invalid date in ILVA item: %s", item)
                    continue

                self.collections.add(
                    WasteCollection.create(
                        collection_date,
                        waste_name,
                        mapped_type,
                    )
                )

            _LOGGER.info("Loaded %s ILVA collections", len(collections))

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("ILVA network error: %s", err)
        except Exception as err:
            _LOGGER.error("ILVA update failed: %s", err)