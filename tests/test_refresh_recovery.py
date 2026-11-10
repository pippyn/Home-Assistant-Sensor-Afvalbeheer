"""Recovery after failed refreshes: quick retries and a calendar kept across restarts."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.collectors.individual.demo import DemoCollector
from custom_components.afvalbeheer.const import ATTR_DATA_STALE, CONF_UPDATE_INTERVAL, DOMAIN

from .test_sensor_entities import _demo_config


async def _scheduled_intervals(data, results):
    """Run one refresh per result and return the interval each one scheduled."""
    intervals = []
    with patch.object(data.collector, "update", new=AsyncMock(side_effect=results)), patch.object(
        data, "schedule_update", new=AsyncMock(side_effect=intervals.append),
    ):
        for _ in results:
            await data.async_update()
    return intervals


async def test_failed_refresh_retries_with_backoff(hass):
    data = get_wastedata_from_config(hass, _demo_config(**{CONF_UPDATE_INTERVAL: 24}))
    intervals = await _scheduled_intervals(data, [False] * 6 + [True, False])
    assert intervals == [
        timedelta(minutes=5), timedelta(minutes=15), timedelta(minutes=30),
        timedelta(hours=1), timedelta(hours=1), timedelta(hours=1),
        timedelta(hours=24),
        timedelta(minutes=5),
    ]


async def test_retry_never_waits_longer_than_the_regular_interval(hass):
    data = get_wastedata_from_config(hass, _demo_config(**{CONF_UPDATE_INTERVAL: 0.25}))
    intervals = await _scheduled_intervals(data, [False, False, False])
    assert intervals == [timedelta(minutes=5), timedelta(minutes=15), timedelta(minutes=15)]


async def test_unexpected_error_still_schedules_a_retry(hass):
    data = get_wastedata_from_config(hass, _demo_config(**{CONF_UPDATE_INTERVAL: 24}))
    intervals = []
    with patch.object(data.collector, "update", new=AsyncMock(side_effect=RuntimeError("boom"))), patch.object(
        data, "schedule_update", new=AsyncMock(side_effect=intervals.append),
    ):
        with pytest.raises(RuntimeError):
            await data.async_update()
    assert intervals == [timedelta(minutes=5)]


async def test_stored_calendar_survives_a_failed_first_refresh(hass):
    config = _demo_config()
    first = get_wastedata_from_config(hass, config)
    await first.async_update()
    first.async_stop()
    fetched = [(c.date, c.waste_type, c.waste_type_slug) for c in first.collections]
    assert fetched

    restarted = get_wastedata_from_config(hass, config)
    with patch.object(DemoCollector, "_async_update", new=AsyncMock(return_value=False)):
        await restarted.async_update()
    restarted.async_stop()
    assert [(c.date, c.waste_type, c.waste_type_slug) for c in restarted.collections] == fetched
    assert restarted.collector.last_update_success is False
    assert restarted.collector.last_successful_update == first.collector.last_successful_update


async def test_unreadable_stored_calendar_is_ignored(hass, hass_storage):
    data = get_wastedata_from_config(hass, _demo_config())
    key = data.collector._collections_store_key
    hass_storage[key] = {
        "version": 1, "minor_version": 1, "key": key,
        "data": {"collections": [{"date": "invalid"}], "last_successful_update": None},
    }
    with patch.object(DemoCollector, "_async_update", new=AsyncMock(return_value=False)):
        await data.async_update()
    data.async_stop()
    assert len(data.collections) == 0
    assert data.collector.last_successful_update is None


async def test_sensors_keep_their_dates_when_the_collector_is_down_after_a_restart(hass):
    """A restart while the collector is unreachable must not blank the sensors for a day."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=_demo_config(**{CONF_UPDATE_INTERVAL: 24}), version=3, minor_version=2,
    )
    entry.add_to_hass(hass)
    with patch("custom_components.afvalbeheer._async_register_frontend", new=AsyncMock()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        sensor = next(e for e in hass.states.async_entity_ids("sensor") if e.endswith("_restafval"))
        fetched = hass.states.get(sensor).state
        assert fetched not in ("unknown", "unavailable")

        with patch.object(DemoCollector, "_async_update", new=AsyncMock(return_value=False)) as down:
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            # Past the first sensor poll, which used to replace the restored state.
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
            await hass.async_block_till_done()
            state = hass.states.get(sensor)
            assert state.state == fetched
            assert state.attributes[ATTR_DATA_STALE] is True
            assert down.await_count == 1

        # The collector is reachable again: the retry five minutes later refreshes,
        # and the next sensor poll shows it.
        restarted = hass.data[DOMAIN][entry.entry_id]["waste_data"]
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))
        await hass.async_block_till_done()
        assert restarted.collector.last_update_success is True
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=32))
        await hass.async_block_till_done()
        state = hass.states.get(sensor)
        assert state.state == fetched
        assert state.attributes[ATTR_DATA_STALE] is False
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
