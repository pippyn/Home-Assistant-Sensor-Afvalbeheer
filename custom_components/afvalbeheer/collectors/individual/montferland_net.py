"""Montferland collector using the municipality's HTTPS app API."""
import logging
from datetime import datetime
from urllib.parse import quote

import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    DEFAULT_REQUEST_TIMEOUT,
    WASTE_TYPE_GREEN,
    WASTE_TYPE_GREY,
    WASTE_TYPE_PACKAGES,
    WASTE_TYPE_PAPER,
)

_LOGGER = logging.getLogger(__name__)

MONTFERLAND_API_URL = "https://montferlandapp-api-prod.azurewebsites.net"
# Shared application token shipped with the Montferland Android app (19.1).
MONTFERLAND_API_KEY = "77FE5F8B-9051-4B05-A525-C7CCCD42236F"


class MontferlandNetCollector(WasteCollector):
    """Fetch upcoming pickups without the legacy cleartext address lookup."""

    # Preserve the legacy slugs for existing custom mappings and sensor attributes.
    WASTE_TYPE_MAPPING = {
        'GFT': WASTE_TYPE_GREEN,
        'Rest afval': WASTE_TYPE_GREY,
        'PMD': WASTE_TYPE_PACKAGES,
        'Papier': WASTE_TYPE_PAPER,
    }
    FRACTION_SLUGS = {1: 'Rest afval', 2: 'GFT', 3: 'Papier', 10: 'PMD'}

    def __get_data(self):
        """Fetch JSON with verified TLS, without redirects or HTTP fallback."""
        address = (
            str(self.postcode).replace(' ', '').upper(),
            str(self.street_number),
            self.suffix or '',
        )
        path = '/'.join(quote(str(part), safe='') for part in address)
        response = requests.get(
            f"{MONTFERLAND_API_URL}/api/v1/Garbage/{path}",
            headers={'authToken': MONTFERLAND_API_KEY},
            timeout=DEFAULT_REQUEST_TIMEOUT,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise requests.exceptions.RequestException("Montferland returned an unexpected redirect")
        response.raise_for_status()
        return response.json()

    async def update(self):
        """Replace collections only after a complete, successful response."""
        try:
            response = await self.hass.async_add_executor_job(self.__get_data)
        except (requests.exceptions.RequestException, ValueError) as exc:
            # Request exceptions can include the address URL or authentication headers.
            _LOGGER.error("Error fetching Montferland data (%s)", type(exc).__name__)
            return False

        if not isinstance(response, dict) or response.get('errorCode') != 0:
            _LOGGER.error("Montferland API returned an error or invalid response")
            return False
        items = response.get('collections')
        if not isinstance(items, list):
            _LOGGER.error("Montferland API returned invalid collections")
            return False

        collections = []
        try:
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Invalid collection")
                slug = self.FRACTION_SLUGS.get(item.get('fraction'))
                if slug is None:
                    _LOGGER.warning("Skipping unknown Montferland waste fraction")
                    continue
                waste_type = self.map_waste_type(slug)
                if not waste_type:
                    continue
                collection = WasteCollection.create(
                    date=datetime.fromisoformat(item['collectionDate']),
                    waste_type=waste_type,
                    waste_type_slug=slug,
                )
                if collection not in collections:
                    collections.append(collection)
        except (KeyError, TypeError, ValueError):
            _LOGGER.error("Montferland API returned invalid collection data")
            return False

        self.collections.remove_all()
        for collection in collections:
            self.collections.add(collection)
