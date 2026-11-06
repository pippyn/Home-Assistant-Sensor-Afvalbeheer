"""Shared update contracts and real collector parsing regressions, without HTTP."""
import asyncio
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from custom_components.afvalbeheer.collectors.base import WasteCollector
from custom_components.afvalbeheer.collectors.individual.afval_alert import AfvalAlertCollector
from custom_components.afvalbeheer.collectors.individual.afvalwijzer import AfvalwijzerCollector
from custom_components.afvalbeheer.collectors.individual.amsterdam import AmsterdamCollector
from custom_components.afvalbeheer.collectors.individual.circulus import CirculusCollector
from custom_components.afvalbeheer.collectors.individual.cleanprofs import CleanprofsCollector
from custom_components.afvalbeheer.collectors.individual.deafvalapp import DeAfvalAppCollector
from custom_components.afvalbeheer.collectors.individual.frisse_kliko import FrisseKlikoCollector
from custom_components.afvalbeheer.collectors.individual.irado import IradoCollector
from custom_components.afvalbeheer.collectors.individual.limburg_net import LimburgNetCollector
from custom_components.afvalbeheer.collectors.individual.montferland_net import MontferlandNetCollector
from custom_components.afvalbeheer.collectors.individual.omrin import OmrinCollector
from custom_components.afvalbeheer.collectors.individual.rd4 import RD4Collector
from custom_components.afvalbeheer.collectors.individual.recycle_app import RecycleApp
from custom_components.afvalbeheer.collectors.individual.reinis import ReinisCollector
from custom_components.afvalbeheer.collectors.individual.rova import ROVACollector
from custom_components.afvalbeheer.collectors.individual.straatbeeld import StraatbeeldCollector
from custom_components.afvalbeheer.collectors.shared.burgerportaal import BurgerportaalCollector
from custom_components.afvalbeheer.collectors.shared.klikogroep import KlikogroepCollector
from custom_components.afvalbeheer.collectors.shared.opzet import OpzetCollector
from custom_components.afvalbeheer.collectors.shared.ximmio import XimmioCollector
from custom_components.afvalbeheer.models import WasteCollection, WasteCollectionRepository


class ContractCollector(WasteCollector):
    """Test implementation of the explicit success contract."""

    WASTE_TYPE_MAPPING = {}

    async def _async_update(self):
        self.collections = WasteCollectionRepository()
        return True


def _seed(collector):
    collection = WasteCollection.create(datetime(2099, 1, 1), 'Paper', 'paper')
    collector.collections.add(collection)
    return collector.collections, collection


@pytest.mark.parametrize('failure', [False, None, ValueError, KeyError, TypeError, AttributeError])
async def test_failed_update_preserves_last_success_and_repository(hass, failure):
    collector = ContractCollector(hass, 'test', '1234AB', '1', '', {})
    assert await collector.update() is True
    timestamp = collector.last_successful_update
    repository, collection = _seed(collector)

    async def fail():
        collector.collections = WasteCollectionRepository()
        if isinstance(failure, type):
            raise failure('invalid payload')
        return failure

    with patch.object(collector, '_async_update', side_effect=fail):
        assert await collector.update() is False
    assert collector.collections is repository
    assert list(repository) == [collection]
    assert collector.last_update_success is False
    assert collector.last_successful_update == timestamp
    assert await collector.update() is True
    assert len(collector.collections) == 0
    assert collector.last_update_success is True


async def test_cancellation_preserves_repository(hass):
    collector = ContractCollector(hass, 'test', '1234AB', '1', '', {})
    repository, _ = _seed(collector)
    with patch.object(collector, '_async_update', side_effect=asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await collector.update()
    assert collector.collections is repository
    assert collector.last_update_success is False
    assert collector.last_successful_update is None


# Each response contains a valid item followed by an invalid date. The previous
# repository must survive even when parsing already produced a replacement item.
CASES = [
    (AfvalAlertCollector, {'items': [{'date': '2099-01-02', 'type': 'paper'},
                                   {'date': 'invalid', 'type': 'paper'}]}, {'items': []}),
    (AfvalwijzerCollector, {'ophaaldagen': {'data': [{'date': '2099-01-02', 'type': 'paper'},
                                                 {'date': 'invalid', 'type': 'paper'}]}},
     {'ophaaldagen': {'data': []}}),
    (CirculusCollector, {'customData': {'response': {'garbage': [
        {'code': 'paper', 'dates': ['2099-01-02', 'invalid']}]}}},
     {'customData': {'response': {'garbage': []}}}),
    (CleanprofsCollector, [{'full_date': '2099-01-02', 'product_name': 'paper'},
                          {'full_date': 'invalid', 'product_name': 'paper'}], []),
    (DeAfvalAppCollector, 'paper;02-01-2099;invalid;', 'paper;'),
    (LimburgNetCollector, [{'date': '2099-01-02T00:00:00+0000', 'title': 'paper'},
                          {'date': 'invalid', 'title': 'paper'}], []),
    (MontferlandNetCollector, {'errorCode': 0, 'collections': [
        {'fraction': 0, 'collectionDate': 'invalid'}]}, {'errorCode': 0, 'collections': []}),
    (RD4Collector, [{'date': '2099-01-02', 'type': 'paper'},
                    {'date': 'invalid', 'type': 'paper'}], []),
    (ReinisCollector, [{'ophaaldatum': '2099-01-02', 'afvalstroom_id': 1},
                       {'ophaaldatum': 'invalid', 'afvalstroom_id': 1}], []),
    (ROVACollector, [{'date': '2099-01-02T00:00:00+0000', 'wasteType': {'title': 'paper'}},
                     {'date': 'invalid', 'wasteType': {'title': 'paper'}}], []),
    (BurgerportaalCollector, [{'collectionDate': '2099-01-02', 'fraction': 'paper'},
                             {'collectionDate': 'invalid', 'fraction': 'paper'}], []),
    (KlikogroepCollector, {'calendar': {'2099-01-02': {'paper': {}}, 'invalid': {'paper': {}}}},
     {'calendar': {}}),
    (XimmioCollector, {'dataList': [{'_pickupTypeText': 'paper',
                                   'pickupDates': ['2099-01-02T00:00:00', 'invalid']}]},
     {'dataList': []}),
    (AmsterdamCollector, {'_embedded': {'afvalwijzer': [
        {'afvalwijzerAfvalkalenderFrequentie': '', 'afvalwijzerWaar': 'stoep',
         'afvalwijzerFractieCode': 'paper', 'afvalwijzerOphaaldagen': 'maandag'}, {}]}},
     {'_embedded': {'afvalwijzer': []}}),
    (IradoCollector, {'data': [{'date': '02/01/2099', 'type': 'paper'},
                              {'date': 'invalid', 'type': 'paper'}]}, {'data': []}),
    (OmrinCollector, [{'date': '2099-01-02T00:00:00', 'type': 'paper'},
                      {'date': 'invalid', 'type': 'paper'}], []),
    (RecycleApp, {'items': [{'timestamp': '2099-01-02T00:00:00', 'fraction': {'name': {'nl': 'paper'}}},
                           {'timestamp': 'invalid', 'fraction': {'name': {'nl': 'paper'}}}]}, {'items': []}),
    (StraatbeeldCollector, {'collections': {'1': {'1': [
        {'date': {'formatted': '2099-01-02'}, 'data': [{'name': 'paper'}]},
        {'date': {'formatted': 'invalid'}, 'data': [{'name': 'paper'}]}]}}}, {'collections': {}}),
    (OpzetCollector, [{'menu_title': 'paper', 'ophaaldatum': '2099-01-02'}, None],
     [{'menu_title': 'paper', 'ophaaldatum': None}]),
    (FrisseKlikoCollector, {'clean_dates': ['2099-01-02', 'invalid'], 'clean_containers': ['paper']},
     {'clean_dates': [], 'clean_containers': ['paper']}),
]


RESPONSE_COLLECTORS = (
    AfvalAlertCollector, AfvalwijzerCollector, AmsterdamCollector, CirculusCollector,
    CleanprofsCollector, IradoCollector, OpzetCollector, RecycleApp, ROVACollector,
    StraatbeeldCollector, XimmioCollector,
)


@pytest.fixture(params=CASES, ids=lambda case: case[0].__name__)
def parsing_case(hass, request):
    cls, malformed, empty = request.param
    malformed = deepcopy(malformed)
    # Skip provider constructor side effects: exercise its real parser with
    # cached address/auth state and an executor stub returning synthetic data.
    collector = cls.__new__(cls)
    WasteCollector.__init__(collector, hass, 'test', '1234AB', '1', '', {})
    collector.city_id = collector.street_id = collector.address_id = collector.bagid = 'cached'
    collector.postcode_id = collector.bag_id = 'cached'
    collector.id_token = collector.refresh_token = 'test-token'
    if cls is BurgerportaalCollector:
        collector._BurgerportaalCollector__load_auth_data = AsyncMock()
        collector._BurgerportaalCollector__save_auth_data = AsyncMock()
    if cls is OmrinCollector:
        collector.token = 'test-token'
        collector.email = collector.password = None
        collector._OmrinCollector__load_auth_data = AsyncMock()
        collector._OmrinCollector__save_auth_data = AsyncMock()
    if cls is RecycleApp:
        collector._RecycleApp__load_auth_data = AsyncMock()
        collector._RecycleApp__save_auth_data = AsyncMock()
    if cls is FrisseKlikoCollector:
        collector.async_load_and_init_auth = AsyncMock()
        collector._auth_changed = False
    collector.map_waste_type = lambda name: name
    if cls is MontferlandNetCollector:
        fraction = next(iter(cls.FRACTION_SLUGS))
        malformed['collections'][0]['fraction'] = fraction
    return collector, malformed, empty


def _response(collector, payload):
    if type(collector) in RESPONSE_COLLECTORS:
        return Mock(status_code=200, json=Mock(return_value=payload))
    return payload


def _executor(collector, payload):
    async def execute(function, *args):
        if function.__name__ == '__get_waste_types':
            return [{'id': 1, 'title': 'paper'}]
        if function.__name__ == '__fetch_id_token':
            return None
        if function.__name__ == '__get_calendar_dates':
            return []
        if function.__name__ == '__get_planning':
            return None
        return _response(collector, payload)
    return execute


async def test_real_collector_failure_is_atomic(parsing_case, hass):
    collector, malformed, _ = parsing_case
    repository, collection = _seed(collector)

    with patch.object(hass, 'async_add_executor_job', side_effect=_executor(collector, malformed)):
        assert await collector.update() is False
    assert collector.collections is repository
    assert list(repository) == [collection]
    assert collector.last_update_success is False
    assert collector.last_successful_update is None


async def test_valid_empty_calendar_is_success(parsing_case, hass):
    collector, _, empty = parsing_case
    # Keep a known waste stream/customer, but no pickup dates. A missing
    # response is tested separately and must not erase the previous calendar.
    _seed(collector)

    with patch.object(hass, 'async_add_executor_job', side_effect=_executor(collector, empty)):
        assert await collector.update() is True
    assert len(collector.collections) == 0
    assert collector.last_update_success is True
    assert collector.last_successful_update is not None


@pytest.mark.parametrize('customer, planning, success', [
    ({'clean_dates': [], 'clean_containers': ['paper']}, None, True),
    ({'cleaning_dates': []}, None, True),
    ({'id': 'synthetic'}, {'next_by_bin': {}}, True),
    ({'id': 'synthetic'}, None, False),
    ({'id': 'synthetic'}, {}, False),
    ({'detail': 'Unauthorized', 'clean_dates': []}, None, False),
    ({'clean_dates': []}, {'detail': 'Unavailable'}, False),
    ({'clean_dates': []}, [], False),
    ({'clean_dates': {}}, None, False),
    ({'id': 'synthetic'}, {'next_by_bin': []}, False),
    ({'clean_dates': ['invalid'], 'cleaning_dates': []}, None, False),
    ({'clean_dates': ['2099-01-02'], 'clean_containers': [], 'cleaning_dates': []}, None, False),
])
async def test_frisse_kliko_empty_schedule_requires_explicit_valid_data(hass, customer, planning, success):
    collector = FrisseKlikoCollector.__new__(FrisseKlikoCollector)
    WasteCollector.__init__(collector, hass, 'frissekliko', '1234AB', '1', '', {})
    collector.async_load_and_init_auth = AsyncMock()
    collector._auth_changed = False
    repository, collection = _seed(collector)
    timestamp = datetime(2098, 1, 1)
    collector.last_successful_update = timestamp

    with patch.object(collector, '_FrisseKlikoCollector__get_customer', return_value=customer), patch.object(
        collector, '_FrisseKlikoCollector__get_planning', return_value=planning,
    ):
        assert await collector.update() is success
    assert collector.last_update_success is success
    if success:
        assert len(collector.collections) == 0
        assert collector.last_successful_update != timestamp
    else:
        assert collector.collections is repository
        assert list(repository) == [collection]
        assert collector.last_successful_update == timestamp


@pytest.mark.parametrize('error', [requests.exceptions.Timeout, requests.exceptions.HTTPError, ValueError])
async def test_request_or_decode_failure_preserves_calendar(parsing_case, hass, error):
    collector, _, _ = parsing_case
    repository, collection = _seed(collector)
    with patch.object(hass, 'async_add_executor_job', side_effect=error):
        assert await collector.update() is False
    assert collector.collections is repository
    assert list(repository) == [collection]


async def test_missing_response_preserves_calendar(parsing_case, hass):
    collector, _, _ = parsing_case
    repository, collection = _seed(collector)
    with patch.object(hass, 'async_add_executor_job', side_effect=_executor(collector, None)):
        assert await collector.update() is False
    assert collector.collections is repository
    assert list(repository) == [collection]


async def test_valid_response_replaces_calendar(parsing_case, hass):
    collector, malformed, _ = parsing_case
    payload = deepcopy(malformed)
    if isinstance(collector, AfvalAlertCollector):
        payload['items'] = payload['items'][:1]
    elif isinstance(collector, AfvalwijzerCollector):
        payload['ophaaldagen']['data'] = payload['ophaaldagen']['data'][:1]
    elif isinstance(collector, AmsterdamCollector):
        payload['_embedded']['afvalwijzer'] = payload['_embedded']['afvalwijzer'][:1]
    elif isinstance(collector, CirculusCollector):
        payload['customData']['response']['garbage'][0]['dates'] = ['2099-01-02']
    elif isinstance(collector, DeAfvalAppCollector):
        payload = 'paper;02-01-2099;'
    elif isinstance(collector, MontferlandNetCollector):
        payload['collections'][0]['collectionDate'] = '2099-01-02'
    elif isinstance(collector, KlikogroepCollector):
        payload['calendar'].pop('invalid')
    elif isinstance(collector, XimmioCollector):
        payload['dataList'][0]['pickupDates'] = ['2099-01-02T00:00:00']
    elif isinstance(collector, IradoCollector):
        payload['data'] = payload['data'][:1]
    elif isinstance(collector, RecycleApp):
        payload['items'] = payload['items'][:1]
    elif isinstance(collector, StraatbeeldCollector):
        payload['collections']['1']['1'] = payload['collections']['1']['1'][:1]
    elif isinstance(collector, FrisseKlikoCollector):
        payload['clean_dates'] = ['2099-01-02']
    else:
        payload = payload[:1]

    repository, _ = _seed(collector)
    with patch.object(hass, 'async_add_executor_job', side_effect=_executor(collector, payload)):
        assert await collector.update() is True
    assert collector.collections is not repository
    assert len(collector.collections) > 0
    assert collector.last_update_success is True
    assert collector.last_successful_update is not None


async def test_overlapping_refreshes_are_serialized(hass):
    collector = ContractCollector(hass, 'test', '1234AB', '1', '', {})
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def update():
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return True

    with patch.object(collector, '_async_update', side_effect=update):
        first = asyncio.create_task(collector.update())
        await entered.wait()
        second = asyncio.create_task(collector.update())
        await asyncio.sleep(0)
        assert calls == 1
        release.set()
        assert await first is True
        assert await second is True
        assert calls == 2
