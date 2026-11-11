"""
Reinis collector for waste data from Reinis.

Since November 2026 Reinis runs on a new website (reinis.nl). The collector
does what that website does: it looks the address up through the postcode
form, asks for the address's calendar link ("add to calendar") and reads the
collection dates from that iCal feed. The link does not expire, so it is
stored and the lookup only runs again when Reinis rejects the link.
"""
import json
import logging
import re
from datetime import datetime

import requests
from homeassistant.util import dt as dt_util

from ..base import WasteCollector
from ...models import WasteCollection, WasteCollectionRepository
from ...const import (
    BURGERPORTAAL_USER_AGENT, DEFAULT_REQUEST_TIMEOUT, WASTE_TYPE_GLASS, WASTE_TYPE_GREEN,
    WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER, WASTE_TYPE_TEXTILE,
)


_LOGGER = logging.getLogger(__name__)

# The postcode form is a Next.js server action; its id changes with every
# deployment of the website, so it is read from the page's scripts.
_SCRIPT_RE = re.compile(r'/_next/static/chunks/[\w.\-]+\.js')
_ACTION_RE = re.compile(r'"([0-9a-f]{40,})"[^"]*"ensureAnonSessionAction"')
_SUMMARY_SUFFIX_RE = re.compile(r'\s+inzameling$', re.IGNORECASE)
_REJECTED_LINK_STATUS = (401, 403, 404, 410)


class ReinisCollector(WasteCollector):
    """
    Collector for Reinis waste data.
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
        self.main_url = "https://reinis.nl"
        self.feed_url = None
        self._auth_loaded = False

    async def __load_auth_data(self):
        """Load the stored calendar link once."""
        if self._auth_loaded:
            return
        data = await self.async_load_auth_data()
        self._auth_loaded = True
        if data:
            self.feed_url = data.get('feed_url') or None

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
        page = self.__request(session, 'get', f"{self.main_url}/postcode")
        for script in dict.fromkeys(_SCRIPT_RE.findall(page.text)):
            match = _ACTION_RE.search(self.__request(session, 'get', self.main_url + script).text)
            if match:
                return match.group(1)
        return None

    def __resolve_feed_url(self):
        """Look the address up like the website does and return its calendar link."""
        _LOGGER.debug("Looking up the Reinis address")
        with requests.Session() as session:
            action = self.__find_address_action(session)
            if not action:
                _LOGGER.error("Could not find the Reinis address lookup on reinis.nl")
                return None

            address = {'postcode': self.postcode, 'huisnummer': str(self.street_number)}
            if self.suffix:
                address['toev'] = self.suffix
            response = self.__request(
                session, 'post', f"{self.main_url}/postcode",
                headers={
                    'Next-Action': action,
                    'Content-Type': 'text/plain;charset=UTF-8',
                    'Accept': 'text/x-component',
                },
                data=json.dumps([address]),
            )
            result = _action_result(response.text)
            if not result or not result.get('ok'):
                error = result.get('error') if result else None
                _LOGGER.error("Reinis did not find the address (%s)", error or 'no answer')
                return None

            response = self.__request(
                session, 'get', f"{self.main_url}/api/proxy/pickups/ical-subscription",
                params={'addressId': result['data']['addressId']},
            )
            return response.json()['data']['url']

    def __get_feed(self):
        """Return the iCal feed, or None when Reinis no longer accepts the link."""
        response = requests.get(
            self.feed_url, headers={'User-Agent': BURGERPORTAAL_USER_AGENT}, timeout=DEFAULT_REQUEST_TIMEOUT,
        )
        if response.status_code in _REJECTED_LINK_STATUS:
            return None
        if not response.ok and 'json' in response.headers.get('Content-Type', ''):
            return response.text  # Reinis's error object, e.g. FEED_UNAVAILABLE
        response.raise_for_status()
        return response.text

    async def _async_update(self) -> bool:
        _LOGGER.debug("Updating Waste collection dates using Reinis API")

        try:
            await self.__load_auth_data()
            if not self.feed_url:
                self.feed_url = await self.hass.async_add_executor_job(self.__resolve_feed_url)
                if not self.feed_url:
                    return False
                await self.async_save_auth_data({'feed_url': self.feed_url})

            feed = await self.hass.async_add_executor_job(self.__get_feed)
            if feed is None:
                _LOGGER.error("Reinis rejected the stored calendar link; the address is looked up again next time")
                self.feed_url = None
                await self.async_save_auth_data({})
                return False
            if not isinstance(feed, str) or not feed.lstrip().startswith('BEGIN:VCALENDAR'):
                # Reinis answers with an error object (e.g. FEED_UNAVAILABLE) when it has no dates.
                _LOGGER.error("Reinis returned no calendar: %s", _error_code(feed))
                return False

            collections = WasteCollectionRepository()
            for event in _parse_events(feed):
                summary = _SUMMARY_SUFFIX_RE.sub('', event.get('SUMMARY', '')).strip()
                if not summary or 'DTSTART' not in event:
                    continue
                waste_type = self.map_waste_type(summary)
                if not waste_type:
                    continue
                collection = WasteCollection.create(
                    date=_event_date(event['DTSTART']),
                    waste_type=waste_type,
                    waste_type_slug=summary,
                )
                if collection not in collections:
                    collections.add(collection)

            self.collections = collections
            return True

        except requests.exceptions.RequestException as exc:
            # The calendar link carries an access token: never log the URL.
            _LOGGER.error('Error occurred while fetching data from Reinis (%s)', type(exc).__name__)
            return False


def _action_result(text):
    """Return the server action's result object from its React Server Components response."""
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


def _error_code(feed):
    try:
        error = json.loads(feed).get('error') or {}
        return error.get('code') or 'unknown error'
    except (AttributeError, TypeError, ValueError):
        return 'unexpected response'


def _parse_events(feed):
    """Return the VEVENT properties of an iCal feed as dicts (parameters dropped)."""
    lines = []
    for line in feed.splitlines():
        if line[:1] in (' ', '\t') and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    events, event = [], None
    components = []
    calendar_seen = False
    for line in lines:
        if not line:
            continue
        if line.startswith('BEGIN:'):
            component = line[6:]
            if not components:
                if calendar_seen or component != 'VCALENDAR':
                    raise ValueError('Invalid calendar root')
                calendar_seen = True
            elif component == 'VCALENDAR':
                raise ValueError('Nested calendar')
            if component == 'VEVENT':
                if components != ['VCALENDAR']:
                    raise ValueError('Invalid event nesting')
                event = {}
            components.append(component)
        elif line.startswith('END:'):
            component = line[4:]
            if not components or components.pop() != component:
                raise ValueError('Mismatched calendar component')
            if component == 'VEVENT':
                if not event.get('SUMMARY') or not event.get('DTSTART'):
                    raise ValueError('Incomplete collection event')
                events.append(event)
                event = None
        elif not components:
            raise ValueError('Property outside calendar')
        elif components[-1] == 'VEVENT' and ':' in line:
            name, value = line.split(':', 1)
            event[name.split(';', 1)[0].upper()] = value.replace('\\,', ',').replace('\\;', ';')
    if not calendar_seen or components:
        raise ValueError('Unfinished calendar')
    return events


def _event_date(value):
    """Return the collection day of a DTSTART value: a date, or a local or UTC date-time."""
    if value.endswith('Z'):
        moment = datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt_util.UTC)
        return datetime.combine(dt_util.as_local(moment).date(), datetime.min.time())
    return datetime.strptime(value[:8], '%Y%m%d')
