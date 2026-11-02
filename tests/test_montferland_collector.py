"""Tests for the HTTPS Montferland app API (synthetic addresses and payloads)."""
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.afvalbeheer.collectors.individual.montferland_net import (
    MONTFERLAND_API_KEY,
    MONTFERLAND_API_URL,
    MontferlandNetCollector,
)
from custom_components.afvalbeheer.const import (
    DEFAULT_REQUEST_TIMEOUT,
    WASTE_TYPE_GREEN, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES, WASTE_TYPE_PAPER,
)
from custom_components.afvalbeheer.models import WasteCollection


def _response(items):
    return Mock(status_code=200, json=Mock(return_value={'errorCode': 0, 'collections': items}))


@pytest.mark.parametrize('suffix,encoded', [('', ''), (None, ''), ('A/B #', 'A%2FB%20%23')])
async def test_verified_https_and_fraction_mapping(hass, suffix, encoded):
    collector = MontferlandNetCollector(hass, 'montferland', '1234 ab', '1', suffix, {})
    items = [{'fraction': f, 'collectionDate': '2099-01-01T00:00:00'} for f in (1, 2, 3, 10)]
    response = _response(items + items)
    with patch('requests.get', return_value=response) as get:
        await collector.update()
    get.assert_called_once_with(
        f'{MONTFERLAND_API_URL}/api/v1/Garbage/1234AB/1/{encoded}',
        headers={'authToken': MONTFERLAND_API_KEY},
        timeout=DEFAULT_REQUEST_TIMEOUT, allow_redirects=False,
    )
    response.raise_for_status.assert_called_once()
    assert [(c.waste_type, c.waste_type_slug) for c in collector.collections] == [
        (WASTE_TYPE_GREY, 'Rest afval'), (WASTE_TYPE_GREEN, 'GFT'),
        (WASTE_TYPE_PAPER, 'Papier'), (WASTE_TYPE_PACKAGES, 'PMD'),
    ]


async def test_custom_mapping_and_unknown_fraction(hass):
    collector = MontferlandNetCollector(hass, 'montferland', '1234AB', '1', '', {'Rest afval': 'Custom'})
    response = _response([
        {'fraction': 1, 'collectionDate': '2099-01-01T00:00:00'},
        {'fraction': 999, 'collectionDate': '2099-01-02T00:00:00'},
    ])
    with patch('requests.get', return_value=response):
        await collector.update()
    assert [(c.waste_type, c.waste_type_slug) for c in collector.collections] == [('Custom', 'Rest afval')]


@pytest.mark.parametrize('failure', ['tls', 'redirect', 'http', 'json', 'api', 'missing', 'date', 'shape'])
async def test_failure_preserves_data_without_fallback_or_private_logs(hass, caplog, failure):
    collector = MontferlandNetCollector(hass, 'montferland', '1234AB', '1', '', {})
    existing = WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'GFT')
    collector.collections.add(existing)
    response = _response([])
    private = f'1234AB {MONTFERLAND_API_KEY}'
    side_effect = None
    if failure == 'tls':
        side_effect = requests.exceptions.SSLError(private)
    elif failure == 'redirect':
        response.status_code = 302
    elif failure == 'http':
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(private)
    elif failure == 'json':
        response.json.side_effect = ValueError(private)
    elif failure == 'api':
        response.json.return_value = {'errorCode': 2002, 'errorMessage': private}
    elif failure == 'missing':
        response.json.return_value = {'errorCode': 0}
    elif failure == 'date':
        response = _response([{'fraction': 1, 'collectionDate': 'invalid'}])
    elif failure == 'shape':
        response = _response([None])
    with patch('requests.get', return_value=response, side_effect=side_effect) as get:
        assert await collector.update() is False
    get.assert_called_once()
    assert list(collector.collections) == [existing]
    assert '1234AB' not in caplog.text
    assert MONTFERLAND_API_KEY not in caplog.text


async def test_successful_empty_calendar_clears_stale_data(hass):
    collector = MontferlandNetCollector(hass, 'montferland', '1234AB', '1', '', {})
    collector.collections.add(WasteCollection.create(datetime(2099, 1, 1), WASTE_TYPE_GREEN, 'GFT'))
    with patch('requests.get', return_value=_response([])):
        await collector.update()
    assert len(collector.collections) == 0
