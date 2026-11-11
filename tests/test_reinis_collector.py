"""Reinis full-calendar JSON API tests using synthetic addresses and responses."""
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
import requests
from homeassistant.util import dt as dt_util

from custom_components.afvalbeheer.collectors.individual import reinis
from custom_components.afvalbeheer.collectors.individual.reinis import ReinisCollector
from custom_components.afvalbeheer.const import (
    BURGERPORTAAL_USER_AGENT, DEFAULT_REQUEST_TIMEOUT, WASTE_TYPE_GREEN,
    WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER,
)
from custom_components.afvalbeheer.models import WasteCollection

MAIN = 'https://reinis.nl'
ACTION = '40e9e910c92ad2df3a6e7323c73dc0a3658eb0fb12'


def calendar(streams=('gft', 'pmd', 'opk')):
    return {'ok': True, 'data': {'days': [
        {'date': f'2099-01-{index:02}', 'pickups': [
            {'date': f'2099-01-{index:02}', 'streamId': stream},
        ]} for index, stream in enumerate(streams, 1)
    ]}}


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = (json.dumps(body) if not isinstance(body, str) else body).encode()
    return result


class FakeSession:
    def __init__(self):
        self.calls = []
        self.lookup = {'ok': True, 'data': {'addressId': 'synthetic-address'}}
        self.calendar = response(calendar())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        self.calls.append(('get', url, kwargs))
        if url.endswith('/postcode'):
            return response('<script src="/_next/static/chunks/form.js"></script>')
        if url.endswith('/form.js'):
            return response(f'createServerReference("{ACTION}",r.callServer,void 0,r.map,"ensureAnonSessionAction")')
        assert url == MAIN + '/api/proxy/pickups/calendar'
        return self.calendar

    def post(self, url, **kwargs):
        self.calls.append(('post', url, kwargs))
        return response('0:{"a":"$@1"}\n1:' + json.dumps(self.lookup))


@pytest.fixture
def collector(hass):
    return ReinisCollector(hass, 'reinis', '1234AB', '1', 'A', {})


@pytest.fixture
def website(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(reinis.requests, 'Session', Mock(return_value=session))
    return session


async def test_full_calendar_lookup_and_mapping(collector, website):
    today = dt_util.now().date()
    assert await collector.update() is True
    post = next(call for call in website.calls if call[0] == 'post')
    assert post[2]['headers']['Next-Action'] == ACTION
    assert json.loads(post[2]['data']) == [{'postcode': '1234AB', 'huisnummer': '1', 'toev': 'A'}]
    params = website.calls[-1][2]['params']
    assert params == {'addressId': 'synthetic-address', 'from': today.isoformat(),
                      'to': (today + timedelta(days=365)).isoformat()}
    for _, _, kwargs in website.calls:
        assert kwargs['timeout'] == DEFAULT_REQUEST_TIMEOUT
        assert kwargs['headers']['User-Agent'] == BURGERPORTAAL_USER_AGENT
    assert [(c.waste_type, c.waste_type_slug) for c in collector.collections] == [
        (WASTE_TYPE_GREEN, 'gft'), (WASTE_TYPE_PACKAGES, 'pmd'), (WASTE_TYPE_PAPER, 'opk'),
    ]


async def test_each_refresh_establishes_a_new_session(collector, website, monkeypatch):
    factory = Mock(side_effect=[website, FakeSession()])
    monkeypatch.setattr(reinis.requests, 'Session', factory)
    collector.async_load_auth_data = AsyncMock(return_value={'feed_url': 'https://old.invalid/?token=secret'})
    assert await collector.update() is True
    assert await collector.update() is True
    assert factory.call_count == 2
    collector.async_load_auth_data.assert_not_awaited()


@pytest.mark.parametrize('payload', [
    {'ok': False, 'error': {'code': 'FEED_UNAVAILABLE'}},
    {'ok': True}, {'ok': True, 'data': {'days': None}},
    {'ok': True, 'data': {'days': [{'date': 'invalid', 'pickups': []}]}},
    {'ok': True, 'data': {'days': [{'date': '2099-01-01', 'pickups': None}]}},
    {'ok': True, 'data': {'days': [{'date': '2099-01-01', 'pickups': [{}]}]}},
    {'ok': True, 'data': {'days': [{'date': '2099-01-01', 'pickups': [
        {'date': '2099-01-02', 'streamId': 'gft'},
    ]}]}},
    '{"ok":true,"data":',
])
async def test_invalid_calendar_preserves_previous_dates(collector, website, payload):
    website.calendar = response(payload)
    previous = collector.collections
    previous.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'gft'))
    assert await collector.update() is False
    assert collector.collections is previous
    assert len(previous) == 1


@pytest.mark.parametrize('status', [401, 403, 500])
async def test_http_failure_recovers_on_next_refresh(collector, website, status):
    website.calendar = response({}, status)
    assert await collector.update() is False
    website.calendar = response(calendar())
    assert await collector.update() is True


async def test_unknown_address_skips_calendar(collector, website):
    website.lookup = {'ok': False, 'error': 'ADDRESS_NOT_FOUND'}
    assert await collector.update() is False
    assert not any(url.endswith('/calendar') for _, url, _ in website.calls)


async def test_valid_empty_calendar(collector, website):
    website.calendar = response(calendar(()))
    collector.collections.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'gft'))
    assert await collector.update() is True
    assert len(collector.collections) == 0


async def test_custom_mapping_unknown_stream_and_duplicates(collector, website):
    collector.custom_mapping = {'gft': 'Garden'}
    payload = calendar(('gft', 'new-stream'))
    payload['data']['days'][0]['pickups'] *= 2
    website.calendar = response(payload)
    assert await collector.update() is True
    assert [c.waste_type for c in collector.collections] == ['Garden', 'new-stream']
