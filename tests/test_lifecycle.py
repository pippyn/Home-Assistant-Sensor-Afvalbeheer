"""Regression tests for shared data ownership and polling cleanup."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.afvalbeheer import async_setup_entry, async_unload_entry
from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.calendar import async_setup_entry as setup_calendar
from custom_components.afvalbeheer.const import CONF_UPDATE_INTERVAL, DOMAIN
from custom_components.afvalbeheer.sensor import async_setup_entry as setup_sensors

from .test_sensor_entities import _demo_config


async def test_platforms_share_one_initial_refresh(hass):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    sensors, calendars = [], []

    async def forward(hass_entry, platforms):
        assert hass_entry is entry
        assert platforms == ["sensor", "calendar"]
        await setup_sensors(hass, entry, lambda entities, *args: sensors.extend(entities))
        await setup_calendar(hass, entry, lambda entities, *args: calendars.extend(entities))

    with patch("custom_components.afvalbeheer.get_wastedata_from_config", return_value=data), patch.object(
        data.collector, "update", wraps=data.collector.update,
    ) as refresh, patch("custom_components.afvalbeheer._async_register_frontend", new=AsyncMock()), patch.object(
        hass.config_entries, "async_forward_entry_setups", side_effect=forward,
    ):
        assert await async_setup_entry(hass, entry)
        refresh.assert_awaited_once()
    data = hass.data[DOMAIN][entry.entry_id]["waste_data"]
    assert sensors[0].data is calendars[0].WasteData is data
    assert data.collector.last_update_success is True
    assert data._cancel_update is not None
    data.async_stop()


async def test_rescheduling_replaces_timer_and_stop_prevents_requests(hass):
    data = get_wastedata_from_config(hass, _demo_config())
    now = dt_util.utcnow()
    with patch.object(data.collector, "update", new=AsyncMock(return_value=True)) as update:
        await data.schedule_update(timedelta(hours=1))
        await data.schedule_update(timedelta(hours=2))
        async_fire_time_changed(hass, now + timedelta(hours=1, minutes=1))
        await hass.async_block_till_done()
        update.assert_not_awaited()
        async_fire_time_changed(hass, now + timedelta(hours=2, minutes=1))
        await hass.async_block_till_done()
        update.assert_awaited_once()
        data.async_stop()
        async_fire_time_changed(hass, now + timedelta(days=2))
        await hass.async_block_till_done()
        await data.async_update()
        update.assert_awaited_once()


async def test_stop_during_refresh_does_not_reschedule(hass):
    data = get_wastedata_from_config(hass, _demo_config())
    started, finish = asyncio.Event(), asyncio.Event()

    async def refresh():
        started.set()
        await finish.wait()
        return True

    with patch.object(data.collector, "update", side_effect=refresh):
        task = asyncio.create_task(data.async_update())
        await started.wait()
        data.async_stop()
        finish.set()
        await task
    assert data._cancel_update is None


async def test_repeated_setup_unload_stops_old_sources(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=_demo_config())
    entry.add_to_hass(hass)
    sources = []
    with patch("custom_components.afvalbeheer._async_register_frontend", new=AsyncMock()), patch.object(
        hass.config_entries, "async_forward_entry_setups", new=AsyncMock(),
    ), patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):
        for _ in range(3):
            assert await async_setup_entry(hass, entry)
            data = hass.data[DOMAIN][entry.entry_id]["waste_data"]
            sources.append(data)
            assert data._cancel_update is not None
            assert await async_unload_entry(hass, entry)
            assert data._cancel_update is None
            assert data._stopped
            assert entry.entry_id not in hass.data[DOMAIN]
    assert len({id(source) for source in sources}) == 3


async def test_setup_failure_cancels_polling(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=_demo_config())
    entry.add_to_hass(hass)
    data = get_wastedata_from_config(hass, _demo_config())
    with patch("custom_components.afvalbeheer._async_register_frontend", new=AsyncMock()), patch(
        "custom_components.afvalbeheer.get_wastedata_from_config", return_value=data,
    ), patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=RuntimeError("setup failed")):
        with pytest.raises(RuntimeError, match="setup failed"):
            await async_setup_entry(hass, entry)
    assert data._stopped
    assert data._cancel_update is None
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_failed_unload_keeps_polling(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=_demo_config())
    data = get_wastedata_from_config(hass, _demo_config())
    hass.data[DOMAIN] = {entry.entry_id: {"waste_data": data}}
    await data.schedule_update(timedelta(hours=1))
    with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=False)):
        assert not await async_unload_entry(hass, entry)
    assert hass.data[DOMAIN][entry.entry_id]["waste_data"] is data
    assert data._cancel_update is not None
    assert not data._stopped
    data.async_stop()


async def test_home_assistant_reload_replaces_source_and_listener(hass):
    """Exercise real platform forwarding and config-entry unload callbacks."""
    entry = MockConfigEntry(domain=DOMAIN, data=_demo_config(), version=3, minor_version=2)
    entry.add_to_hass(hass)
    with patch("custom_components.afvalbeheer._async_register_frontend", new=AsyncMock()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        for _ in range(2):
            old = hass.data[DOMAIN][entry.entry_id]["waste_data"]
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            current = hass.data[DOMAIN][entry.entry_id]["waste_data"]
            assert current is not old
            assert old._stopped
            assert old._cancel_update is None
            assert current._cancel_update is not None
            assert len(entry.update_listeners) == 1
        old = current
        hass.config_entries.async_update_entry(entry, options={CONF_UPDATE_INTERVAL: 6})
        await hass.async_block_till_done()
        current = hass.data[DOMAIN][entry.entry_id]["waste_data"]
        assert old._stopped
        assert current is not old
        assert current.update_interval == 6
        assert len(entry.update_listeners) == 1
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert current._stopped
        assert entry.entry_id not in hass.data[DOMAIN]


async def test_overlapping_refreshes_keep_one_timer(hass):
    data = get_wastedata_from_config(hass, _demo_config())
    started, finish = asyncio.Event(), asyncio.Event()
    calls = 0

    async def refresh():
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await finish.wait()
        return True

    with patch.object(data.collector, "update", side_effect=refresh), patch(
        "custom_components.afvalbeheer.API.async_track_point_in_utc_time",
    ) as schedule:
        first = asyncio.create_task(data.async_update())
        await started.wait()
        second = asyncio.create_task(data.async_update())
        finish.set()
        await asyncio.gather(first, second)
        assert calls == 2
        assert schedule.call_count == 2
        schedule.return_value.assert_called_once_with()
        data.async_stop()
