"""Tests for the Reinis collector on the reinis.nl website of November 2026 (synthetic data, no network)."""
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
import requests

from custom_components.afvalbeheer.collectors.individual import reinis
from custom_components.afvalbeheer.collectors.individual.reinis import ReinisCollector
from custom_components.afvalbeheer.const import (
    BURGERPORTAAL_USER_AGENT, DEFAULT_REQUEST_TIMEOUT, WASTE_TYPE_GREEN, WASTE_TYPE_GREY,
    WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER,
)
from custom_components.afvalbeheer.models import WasteCollection

MAIN = 'https://reinis.nl'
ACTION = '40e9e910c92ad2df3a6e7323c73dc0a3658eb0fb12'
FEED_URL = 'https://feed.invalid/api/proxy/pickups/ical/address?token=secret'
FEED = '\r\n'.join([
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Reinis//Afvalkalender//NL',
    'BEGIN:VEVENT',
    'UID:evreka-2099-01-02-gft-address@feed.invali',
    ' d',
    'DTSTART;VALUE=DATE:20990102',
    'DTEND;VALUE=DATE:20990103',
    'SUMMARY:GFT inzameling',
    'END:VEVENT',
    'BEGIN:VEVENT',
    'DTSTART;VALUE=DATE:20990109',
    'SUMMARY:PMD inzameling',
    'END:VEVENT',
    'BEGIN:VEVENT',
    'DTSTART;VALUE=DATE:20990116',
    'SUMMARY:Restafval inzameling',
    'END:VEVENT',
    'BEGIN:VEVENT',
    'DTSTART;VALUE=DATE:20990123',
    'SUMMARY:OPK inzameling',
    'END:VEVENT',
    'END:VCALENDAR',
    '',
])


def _response(body='', status=200, content_type='text/plain'):
    response = requests.Response()
    response.status_code = status
    response._content = body.encode()
    response.headers['Content-Type'] = content_type
    return response


class FakeSession:
    """Answers the website's requests by URL and records them."""

    def __init__(self, action_result):
        self.calls = []
        self.answers = {
            ('get', f'{MAIN}/postcode'): _response(
                '<script src="/_next/static/chunks/aaa.js"></script>'
                '<script src="/_next/static/chunks/bbb.js"></script>'),
            ('get', f'{MAIN}/_next/static/chunks/aaa.js'): _response('console.log("unrelated")'),
            ('get', f'{MAIN}/_next/static/chunks/bbb.js'): _response(
                f'(0,t.createServerReference)("{ACTION}",r.callServer,void 0,'
                'r.findSourceMapURL,"ensureAnonSessionAction")'),
            ('post', f'{MAIN}/postcode'): _response(
                '0:{"a":"$@1","f":"","b":"build"}\n1:' + json.dumps(action_result) + '\n'),
            ('get', f'{MAIN}/api/proxy/pickups/ical-subscription'): _response(
                json.dumps({'ok': True, 'data': {'url': FEED_URL}}), content_type='application/json'),
        }

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        self.calls.append(('get', url, kwargs))
        return self.answers[('get', url)]

    def post(self, url, **kwargs):
        self.calls.append(('post', url, kwargs))
        return self.answers[('post', url)]


@pytest.fixture
def collector(hass):
    collector = ReinisCollector(hass, 'reinis', '1234AB', '1', 'A', {})
    collector.async_load_auth_data = AsyncMock(return_value=None)
    collector.async_save_auth_data = AsyncMock()
    return collector


@pytest.fixture
def website(monkeypatch):
    session = FakeSession({'ok': True, 'data': {'addressId': 'address'}})
    monkeypatch.setattr(reinis.requests, 'Session', Mock(return_value=session))
    feed = Mock(return_value=_response(FEED, content_type='text/calendar'))
    monkeypatch.setattr(reinis.requests, 'get', feed)
    return session, feed


async def test_lookup_follows_the_website_and_stores_the_link(collector, website):
    session, feed = website
    assert await collector.update() is True

    post = next(call for call in session.calls if call[0] == 'post')
    assert post[2]['headers']['Next-Action'] == ACTION
    assert json.loads(post[2]['data']) == [{'postcode': '1234AB', 'huisnummer': '1', 'toev': 'A'}]
    subscription = session.calls[-1]
    assert subscription[2]['params'] == {'addressId': 'address'}
    for call in session.calls:
        assert call[2]['timeout'] == DEFAULT_REQUEST_TIMEOUT
        assert call[2]['headers']['User-Agent'] == BURGERPORTAAL_USER_AGENT
    collector.async_save_auth_data.assert_awaited_once_with({'feed_url': FEED_URL})
    assert feed.call_args.args == (FEED_URL,)

    assert [(c.date, c.waste_type) for c in collector.collections.get_sorted()] == [
        (datetime(2099, 1, 2), WASTE_TYPE_GREEN),
        (datetime(2099, 1, 9), WASTE_TYPE_PACKAGES),
        (datetime(2099, 1, 16), WASTE_TYPE_GREY),
        (datetime(2099, 1, 23), WASTE_TYPE_PAPER),
    ]


async def test_stored_link_skips_the_lookup(collector, website, monkeypatch):
    session, feed = website
    collector.async_load_auth_data = AsyncMock(return_value={'feed_url': FEED_URL})
    assert await collector.update() is True
    assert session.calls == []
    assert feed.call_args.args == (FEED_URL,)
    assert len(collector.collections) == 4


async def test_unknown_address_fails_without_storing_a_link(collector, website, monkeypatch):
    session = FakeSession({'ok': False, 'error': 'ADDRESS_NOT_FOUND'})
    monkeypatch.setattr(reinis.requests, 'Session', Mock(return_value=session))
    assert await collector.update() is False
    collector.async_save_auth_data.assert_not_awaited()
    assert collector.feed_url is None


async def test_rejected_link_is_forgotten_and_looked_up_again(collector, website, monkeypatch):
    session, _ = website
    collector.async_load_auth_data = AsyncMock(return_value={'feed_url': 'https://feed.invalid/old'})
    rejected = Mock(return_value=_response('', status=404))
    monkeypatch.setattr(reinis.requests, 'get', rejected)
    previous = collector.collections
    previous.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'GFT'))

    assert await collector.update() is False
    assert collector.collections is previous
    assert collector.feed_url is None
    collector.async_save_auth_data.assert_awaited_once_with({})

    monkeypatch.setattr(reinis.requests, 'get', Mock(return_value=_response(FEED, content_type='text/calendar')))
    assert await collector.update() is True
    assert any(call[0] == 'post' for call in session.calls)
    assert collector.feed_url == FEED_URL


@pytest.mark.parametrize('answer', [
    _response(json.dumps({'ok': False, 'error': {'code': 'FEED_UNAVAILABLE'}}), status=503,
              content_type='application/json'),
    _response(json.dumps({'ok': False, 'error': {'code': 'FEED_UNAVAILABLE'}}), content_type='application/json'),
    _response('<html>maintenance</html>', status=502, content_type='text/html'),
])
async def test_no_calendar_keeps_the_previous_one(collector, website, monkeypatch, answer):
    collector.async_load_auth_data = AsyncMock(return_value={'feed_url': FEED_URL})
    monkeypatch.setattr(reinis.requests, 'get', Mock(return_value=answer))
    previous = collector.collections
    previous.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'GFT'))
    assert await collector.update() is False
    assert collector.collections is previous
    assert collector.feed_url == FEED_URL


async def test_utc_start_time_is_read_as_the_local_day(hass):
    await hass.config.async_set_time_zone('Europe/Amsterdam')
    assert reinis._event_date('20991231T230000Z') == datetime(2100, 1, 1)
    assert reinis._event_date('20990102') == datetime(2099, 1, 2)
    assert reinis._event_date('20990102T070000') == datetime(2099, 1, 2)


@pytest.mark.parametrize('feed', [
    'BEGIN:VCALENDAR\r\n',
    'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20990102\r\n',
    FEED.replace('END:VCALENDAR\r\n', ''),
    FEED.replace('END:VEVENT', 'END:VTODO', 1),
    FEED.replace('SUMMARY:GFT inzameling\r\n', '', 1),
])
async def test_incomplete_calendar_preserves_previous_dates(collector, website, monkeypatch, feed):
    collector.async_load_auth_data = AsyncMock(return_value={'feed_url': FEED_URL})
    monkeypatch.setattr(reinis.requests, 'get', Mock(return_value=_response(feed)))
    previous = collector.collections
    previous.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'GFT'))
    assert await collector.update() is False
    assert collector.collections is previous
    assert len(collector.collections) == 1


async def test_valid_empty_calendar_replaces_previous_dates(collector, website, monkeypatch):
    collector.async_load_auth_data = AsyncMock(return_value={'feed_url': FEED_URL})
    monkeypatch.setattr(reinis.requests, 'get', Mock(return_value=_response(
        'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n',
    )))
    collector.collections.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'GFT'))
    assert await collector.update() is True
    assert len(collector.collections) == 0


def test_alarm_properties_do_not_replace_collection_properties():
    feed = FEED.replace('END:VEVENT', (
        'BEGIN:VALARM\r\nSUMMARY:Reminder\r\nEND:VALARM\r\nEND:VEVENT'
    ), 1)
    assert reinis._parse_events(feed)[0]['SUMMARY'] == 'GFT inzameling'
