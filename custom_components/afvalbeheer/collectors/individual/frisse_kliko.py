"""
Frisse Kliko collector for bin cleaning data from Frisse Kliko API.
"""
import base64
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BRANCHES,
    WASTE_TYPE_BULKLITTER,
    WASTE_TYPE_GLASS,
    WASTE_TYPE_GREEN,
    WASTE_TYPE_GREY,
    WASTE_TYPE_KCA,
    WASTE_TYPE_PACKAGES,
    WASTE_TYPE_PAPER,
    WASTE_TYPE_TEXTILE,
    WASTE_TYPE_TREE,
)

_LOGGER = logging.getLogger(__name__)


def _extract_jwt_expiry(token: str) -> Optional[datetime]:
    """Extract expiry datetime from JWT token payload."""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).replace(tzinfo=None)
    except Exception as exc:
        _LOGGER.debug("Could not extract JWT expiry: %r", exc)
    return None


class FrisseKlikoCollector(WasteCollector):
    """
    Collector for Frisse Kliko container cleaning data.
    """
    WASTE_TYPE_MAPPING = {
        'pmd': WASTE_TYPE_PACKAGES,
        'grijs': WASTE_TYPE_GREY,
        'rest': WASTE_TYPE_GREY,
        'restafval': WASTE_TYPE_GREY,
        'gfte': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        'groen': WASTE_TYPE_GREEN,
        'groen/gft': WASTE_TYPE_GREEN,
        'papier': WASTE_TYPE_PAPER,
        'kerstboom': WASTE_TYPE_TREE,
        'kerstbomen': WASTE_TYPE_TREE,
        'glas': WASTE_TYPE_GLASS,
        'textiel': WASTE_TYPE_TEXTILE,
        'takken': WASTE_TYPE_BRANCHES,
        'snoeihout': WASTE_TYPE_BRANCHES,
        'grofvuil': WASTE_TYPE_BULKLITTER,
        'kca': WASTE_TYPE_KCA,
        'chemisch': WASTE_TYPE_KCA,
        'reiniging': 'Reiniging',
        'kliko-reiniging': 'Reiniging',
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, street_name=None):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.street_name = street_name
        self.base_url = "https://api.frissekliko.nl"
        self.token: Optional[str] = None
        self.customer_id: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._auth_loaded = False
        self._auth_changed = False

    def _normalize_postcode(self) -> str:
        """Normalize Dutch postcode (uppercase, no whitespace)."""
        return str(self.postcode).replace(" ", "").upper()

    def _normalize_house_number(self) -> str:
        """Combine house number and optional suffix."""
        if self.suffix:
            suffix_clean = str(self.suffix).strip()
            num_clean = str(self.street_number).strip()
            if not num_clean.endswith(suffix_clean):
                return f"{num_clean}{suffix_clean}"
        return str(self.street_number).strip()

    def _is_token_valid(self) -> bool:
        """Check if cached token is present and not expired."""
        if not self.token or not self.customer_id:
            return False
        if self.token_expires_at:
            if datetime.now() >= self.token_expires_at:
                _LOGGER.debug("Frisse Kliko token is expired")
                return False
        return True

    def __load_auth_data(self):
        """Load persisted auth data once."""
        if self._auth_loaded:
            return

        data = None
        try:
            # We call this synchronously from executor job if needed or via async helper
            pass
        except Exception:
            pass

    async def async_load_and_init_auth(self):
        """Load stored auth credentials asynchronously."""
        if self._auth_loaded:
            return
        data = await self.async_load_auth_data()
        self._auth_loaded = True
        if not data:
            return

        self.token = data.get("access_token")
        self.customer_id = data.get("customer_id")
        expires_at_str = data.get("token_expires_at")
        if expires_at_str:
            try:
                self.token_expires_at = datetime.fromisoformat(expires_at_str)
            except (ValueError, TypeError):
                self.token_expires_at = None

    async def async_save_current_auth(self):
        """Persist updated auth data."""
        if not self._auth_changed:
            return
        await self.async_save_auth_data({
            "access_token": self.token,
            "customer_id": self.customer_id,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
        })
        self._auth_changed = False

    def __login(self) -> Optional[Dict[str, Any]]:
        """Authenticate with Frisse Kliko using address and return customer data."""
        _LOGGER.debug("Authenticating with Frisse Kliko by address")
        postcode = self._normalize_postcode()
        house_number = self._normalize_house_number()

        payload: Dict[str, Any] = {
            "postcode": postcode,
            "house_number": house_number,
        }
        if self.street_name and str(self.street_name).strip():
            payload["street"] = str(self.street_name).strip()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Home-Assistant-Sensor-Afvalbeheer",
        }

        url = f"{self.base_url}/api/auth/customer/by-address"
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code != 200:
            _LOGGER.error(
                "Frisse Kliko authentication failed with status %d: %s",
                response.status_code,
                response.text,
            )
            return None

        data = response.json()
        if not data or "detail" in data:
            _LOGGER.warning(
                "No Frisse Kliko customer found for address %s %s: %s",
                postcode,
                house_number,
                data.get("detail") if isinstance(data, dict) else data,
            )
            return None

        access_token = data.get("access_token")
        customer = data.get("customer")

        if not access_token or not customer:
            _LOGGER.error("Invalid response format from Frisse Kliko auth endpoint")
            return None

        self.token = access_token
        self.customer_id = customer.get("id") or f"{postcode}-{house_number}"
        self.token_expires_at = _extract_jwt_expiry(access_token)
        self._auth_changed = True
        _LOGGER.debug("Frisse Kliko authentication successful, customer_id: %s", self.customer_id)

        return customer

    def __get_customer(self) -> Optional[Dict[str, Any]]:
        """Fetch customer profile using existing token or authenticate if needed."""
        if self._is_token_valid():
            _LOGGER.debug("Fetching Frisse Kliko customer data for id: %s", self.customer_id)
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Home-Assistant-Sensor-Afvalbeheer",
            }
            url = f"{self.base_url}/api/customers/{self.customer_id}"
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    _LOGGER.debug("Stored Frisse Kliko token expired/unauthorized; re-authenticating")
                else:
                    _LOGGER.warning(
                        "Unexpected status %d when fetching customer %s: %s",
                        response.status_code,
                        self.customer_id,
                        response.text,
                    )
            except requests.exceptions.RequestException as exc:
                _LOGGER.warning("Failed to fetch customer using token: %r, retrying login", exc)

        return self.__login()

    def _parse_collections(self, customer: Dict[str, Any]) -> None:
        """Parse customer bin cleaning dates into collections repository."""
        self.collections.remove_all()

        clean_dates = []
        raw_next_clean_date = customer.get("next_clean_date")
        if raw_next_clean_date:
            if isinstance(raw_next_clean_date, list):
                clean_dates.extend(raw_next_clean_date)
            else:
                clean_dates.append(raw_next_clean_date)

        raw_clean_dates = customer.get("clean_dates") or customer.get("cleaning_dates")
        if raw_clean_dates:
            if isinstance(raw_clean_dates, list):
                clean_dates.extend(raw_clean_dates)
            else:
                clean_dates.append(raw_clean_dates)

        clean_containers = customer.get("clean_containers") or []
        if isinstance(clean_containers, str):
            try:
                clean_containers = json.loads(clean_containers)
            except json.JSONDecodeError:
                clean_containers = [c.strip() for c in clean_containers.split(",") if c.strip()]

        for clean_date_entry in clean_dates:
            try:
                clean_date_str = str(clean_date_entry).split("T")[0]
                clean_date = datetime.strptime(clean_date_str, "%Y-%m-%d").replace(tzinfo=None)

                # General bin cleaning collection
                clean_collection = WasteCollection.create(
                    date=clean_date,
                    waste_type=self.map_waste_type("reiniging"),
                    waste_type_slug="reiniging",
                )
                if clean_collection not in self.collections:
                    self.collections.add(clean_collection)

                # Specific container cleaning collections
                if isinstance(clean_containers, list):
                    for container in clean_containers:
                        if not container:
                            continue
                        container_str = str(container).strip()
                        mapped_container = self.map_waste_type(container_str) or container_str.capitalize()
                        slug = f"reiniging_{container_str.lower().replace('/', '_')}"
                        container_collection = WasteCollection.create(
                            date=clean_date,
                            waste_type=f"Reiniging {mapped_container}",
                            waste_type_slug=slug,
                        )
                        if container_collection not in self.collections:
                            self.collections.add(container_collection)
            except (ValueError, TypeError) as exc:
                _LOGGER.warning("Error parsing cleaning date '%s': %r", clean_date_entry, exc)

    async def update(self):
        """Update cleaning dates using Frisse Kliko API."""
        _LOGGER.debug("Updating cleaning dates using Frisse Kliko API")

        try:
            await self.async_load_and_init_auth()

            customer = await self.hass.async_add_executor_job(self.__get_customer)
            if self._auth_changed:
                await self.async_save_current_auth()

            if not customer:
                _LOGGER.error("No waste data found for Frisse Kliko at %s %s", self.postcode, self.street_number)
                return False

            self._parse_collections(customer)

            if len(self.collections) == 0:
                _LOGGER.error("No waste collections could be parsed for Frisse Kliko")
                return False

            return True

        except requests.exceptions.RequestException as exc:
            _LOGGER.error("Error occurred while fetching data from Frisse Kliko: %r", exc)
            return False
