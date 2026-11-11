"""Read Reinis's full calendar through the website's anonymous JSON API."""
import json
import logging
import re
from datetime import datetime, timedelta

import requests
from homeassistant.util import dt as dt_util

from ..base import WasteCollector
from ...models import WasteCollection, WasteCollectionRepository
from ...const import (
    BURGERPORTAAL_USER_AGENT, DEFAULT_REQUEST_TIMEOUT, WASTE_TYPE_GLASS, WASTE_TYPE_GREEN,
    WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER, WASTE_TYPE_TEXTILE,
)

_LOGGER = logging.getLogger(__name__)
_SCRIPT_RE = re.compile(r'/_next/static/chunks/[\w.\-]+\.js')
_ACTION_RE = re.compile(r'"([0-9a-f]{40,})"[^"]*"ensureAnonSessionAction"')


class ReinisCollector(WasteCollector):
    """Fetch a year of collections using a fresh anonymous website session.

    All session operations run in one executor job. Re-establishing the session
    each refresh avoids storing cookies or depending on their expiry, and makes
    the old token-bearing iCal auth store unnecessary.
    """

    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'groente': WASTE_TYPE_GREEN,
        'pmd': WASTE_TYPE_PACKAGES,
        'plastic': WASTE_TYPE_PACKAGES,
        'opk': WASTE_TYPE_PAPER,
        'papier': WASTE_TYPE_PAPER,
        'rest': WASTE_TYPE_GREY,
        'glas': WASTE_TYPE_GLASS,
        'textiel': WASTE_TYPE_TEXTILE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = 'https://reinis.nl'

    @staticmethod
    def __request(session, method, url, **kwargs):
        response = getattr(session, method)(
            url,
            headers={'User-Agent': BURGERPORTAAL_USER_AGENT, **kwargs.pop('headers', {})},
            timeout=DEFAULT_REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def __find_address_action(self, session):
        page = self.__request(session, 'get', f'{self.main_url}/postcode')
        for script in dict.fromkeys(_SCRIPT_RE.findall(page.text)):
            response = self.__request(session, 'get', self.main_url + script)
            match = _ACTION_RE.search(response.text)
            if match:
                return match.group(1)
        return None

    def __get_data(self):
        """Resolve the address and request the full calendar, not homepage pickups."""
        with requests.Session() as session:
            action = self.__find_address_action(session)
            if not action:
                _LOGGER.error('Could not find the Reinis address lookup on reinis.nl')
                return None
            address = {'postcode': self.postcode, 'huisnummer': str(self.street_number)}
            if self.suffix:
                address['toev'] = self.suffix
            response = self.__request(
                session, 'post', f'{self.main_url}/postcode',
                headers={
                    'Next-Action': action,
                    'Content-Type': 'text/plain;charset=UTF-8',
                    'Accept': 'text/x-component',
                },
                data=json.dumps([address]),
            )
            result = _action_result(response.text)
            if not result or result.get('ok') is not True:
                _LOGGER.error('Reinis address lookup failed')
                return None
            today = dt_util.now().date()
            # 365 days between endpoints stays within the API's 366-day limit,
            # including when the API counts both endpoints.
            response = self.__request(
                session, 'get', f'{self.main_url}/api/proxy/pickups/calendar',
                params={
                    'addressId': result['data']['addressId'],
                    'from': today.isoformat(),
                    'to': (today + timedelta(days=365)).isoformat(),
                },
            )
            return response.json()

    async def _async_update(self) -> bool:
        """Publish a complete calendar only after validating every collection."""
        try:
            response = await self.hass.async_add_executor_job(self.__get_data)
            if not isinstance(response, dict) or response.get('ok') is not True:
                _LOGGER.error('Reinis returned no calendar')
                return False
            days = response['data']['days']
            if not isinstance(days, list):
                raise ValueError('Invalid calendar days')
            collections = WasteCollectionRepository()
            for day in days:
                day_date = datetime.strptime(day['date'], '%Y-%m-%d')
                if not isinstance(day['pickups'], list):
                    raise ValueError('Invalid calendar pickups')
                for pickup in day['pickups']:
                    date = datetime.strptime(pickup['date'], '%Y-%m-%d')
                    stream = pickup['streamId']
                    if date != day_date or not isinstance(stream, str) or not stream.strip():
                        raise ValueError('Invalid collection')
                    waste_type = self.map_waste_type(stream)
                    if not waste_type:
                        continue
                    collection = WasteCollection.create(date, waste_type, stream)
                    if collection not in collections:
                        collections.add(collection)
            self.collections = collections
            return True
        except requests.exceptions.RequestException as exc:
            # Never include session data, addresses or response bodies in logs.
            _LOGGER.error('Error fetching Reinis calendar (%s)', type(exc).__name__)
            return False


def _action_result(text):
    """Extract the postcode server action's result from its React response."""
    for line in text.splitlines():
        _, _, value = line.partition(':')
        if not value.startswith('{'):
            continue
        try:
            result = json.loads(value)
        except ValueError:
            continue
        if isinstance(result, dict) and 'ok' in result:
            return result
    return None
