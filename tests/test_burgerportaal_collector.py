"""Tests for Burgerportaal request headers, authentication and HTTP failures."""
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
import requests

from custom_components.afvalbeheer.collectors.shared.burgerportaal import BurgerportaalCollector
from custom_components.afvalbeheer.const import (
    BURGERPORTAAL_USER_AGENT,
    DEFAULT_REQUEST_TIMEOUT,
    WASTE_TYPE_GREEN,
)
from custom_components.afvalbeheer.models import WasteCollection


def _response(data=None, status=200, body=None):
    """Build a real requests response with observable JSON parsing."""
    response = requests.Response()
    response.status_code = status
    response._content = (body if body is not None else json.dumps(data)).encode()
    response.json = Mock(wraps=response.json)
    return response


@pytest.fixture
def collector(hass):
    """Create a collector using synthetic address and authentication data."""
    collector = BurgerportaalCollector(hass, 'assen', '1234AB', '1', '', {})
    collector.async_load_auth_data = AsyncMock(return_value=None)
    collector.async_save_auth_data = AsyncMock()
    return collector


@pytest.fixture
def http(monkeypatch):
    """Replace network calls; no real addresses or credentials are used."""
    post = Mock(return_value=_response({'refreshToken': 'refresh', 'idToken': 'token'}))
    get = Mock(side_effect=[
        _response([{'addressId': 'address', 'addition': ''}]),
        _response([{'fraction': 'GFT', 'collectionDate': '2099-01-02T00:00:00'}]),
    ])
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests, 'get', get)
    return post, get


async def test_requests_identify_integration_and_load_collections(collector, http):
    post, get = http
    await collector.update()

    assert post.call_count == 1
    assert get.call_count == 2
    for call in post.call_args_list + get.call_args_list:
        assert call.kwargs['headers']['User-Agent'] == BURGERPORTAAL_USER_AGENT
        assert call.kwargs['timeout'] == DEFAULT_REQUEST_TIMEOUT
    for call in get.call_args_list:
        assert call.kwargs['headers']['authorization'] == 'token'
    collections = list(collector.collections)
    assert len(collections) == 1
    assert collections[0].waste_type == WASTE_TYPE_GREEN
    assert collections[0].date == datetime(2099, 1, 2)
    assert collector.async_save_auth_data.call_args.args[0] == {
        'refresh_token': 'refresh', 'id_token': 'token', 'address_id': 'address',
    }


async def test_cached_auth_and_address_are_reused(collector, http):
    post, get = http
    collector.async_load_auth_data.return_value = {
        'refresh_token': 'stored-refresh', 'id_token': 'old-token', 'address_id': 'stored-address',
    }
    post.return_value = _response({'id_token': 'new-token'})
    get.side_effect = None
    get.return_value = _response([{'fraction': 'GFT', 'collectionDate': '2099-01-02'}])

    await collector.update()
    await collector.update()

    collector.async_load_auth_data.assert_awaited_once()
    assert post.call_count == 2
    assert get.call_count == 2
    for call in post.call_args_list:
        assert 'securetoken.googleapis.com' in call.args[0]
        assert call.kwargs['data']['refresh_token'] == 'stored-refresh'
        assert call.kwargs['headers']['User-Agent'] == BURGERPORTAAL_USER_AGENT
        assert call.kwargs['headers']['Content-Type'] == 'application/x-www-form-urlencoded'
    for call in get.call_args_list:
        assert call.args[0].endswith('/address/stored-address/calendar')
        assert call.kwargs['headers']['authorization'] == 'new-token'


async def test_rejected_refresh_token_obtains_new_credentials(collector, http):
    post, _ = http
    collector.async_load_auth_data.return_value = {'refresh_token': 'expired-refresh'}
    rejected = _response(status=400, body='Rejected')
    post.side_effect = [rejected, _response({'refreshToken': 'refresh', 'idToken': 'token'})]

    await collector.update()

    rejected.json.assert_not_called()
    assert post.call_count == 2
    assert 'securetoken.googleapis.com' in post.call_args_list[0].args[0]
    assert 'signupNewUser' in post.call_args_list[1].args[0]
    assert len(collector.collections) == 1


@pytest.mark.parametrize('stage', ['signup', 'refresh', 'address', 'calendar'])
@pytest.mark.parametrize('status', [403, 500])
async def test_http_errors_are_not_parsed_or_retried(collector, http, caplog, stage, status):
    post, get = http
    existing = WasteCollection.create(
        date=datetime(2099, 1, 1), waste_type=WASTE_TYPE_GREEN, waste_type_slug='gft',
    )
    collector.collections.add(existing)
    failed = _response(status=status, body='Request blocked')
    if stage in ('signup', 'refresh'):
        post.return_value = failed
        if stage == 'refresh':
            collector.async_load_auth_data.return_value = {'refresh_token': 'stored-refresh'}
    elif stage == 'address':
        get.side_effect = [failed]
    else:
        get.side_effect = [_response([{'addressId': 'address'}]), failed]

    assert await collector.update() is False

    failed.json.assert_not_called()
    assert list(collector.collections) == [existing]
    assert post.call_count == 1
    assert get.call_count == {'signup': 0, 'refresh': 0, 'address': 1, 'calendar': 2}[stage]
    assert 'HTTPError' in caplog.text


async def test_missing_signup_tokens_stop_requests(collector, http):
    post, get = http
    post.return_value = _response({'error': 'No credentials'})

    assert await collector.update() is False

    get.assert_not_called()


@pytest.mark.parametrize('status, body', [(204, ''), (200, '[]')])
async def test_missing_address_stops_calendar_request(collector, http, status, body):
    _, get = http
    get.side_effect = [_response(status=status, body=body)]

    assert await collector.update() is False

    assert get.call_count == 1


async def test_invalid_calendar_json_preserves_collections(collector, http):
    _, get = http
    existing = WasteCollection.create(
        date=datetime(2099, 1, 1), waste_type=WASTE_TYPE_GREEN, waste_type_slug='gft',
    )
    collector.collections.add(existing)
    get.side_effect = [_response([{'addressId': 'address'}]), _response(body='Not JSON')]

    assert await collector.update() is False

    assert list(collector.collections) == [existing]
