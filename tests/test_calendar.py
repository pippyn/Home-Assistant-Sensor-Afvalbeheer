"""Calendar range and cross-platform stale-data regression tests."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.calendar import AfvalbeheerCalendar
from custom_components.afvalbeheer.models import WasteCollection, WasteCollectionRepository
from custom_components.afvalbeheer.sensor import WasteTypeSensor

from .test_sensor_entities import _demo_config


@pytest.mark.parametrize("day", ["2026-03-29", "2026-10-25"])
async def test_all_day_overlap_uses_local_timezone_and_exclusive_end(hass, day):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    local = ZoneInfo("Europe/Amsterdam")
    start = datetime.fromisoformat(day).replace(tzinfo=local)
    data.collections.add(WasteCollection.create(
        date=start.replace(tzinfo=None), waste_type="restafval", waste_type_slug="restafval",
    ))
    calendar = AfvalbeheerCalendar(data, config)
    with patch("custom_components.afvalbeheer.calendar.dt_util.DEFAULT_TIME_ZONE", local):
        # A UTC query within the local all-day event must still include it.
        events = await calendar.async_get_events(hass, start.astimezone(timezone.utc),
                                                (start + timedelta(days=1)).astimezone(timezone.utc))
        assert len(events) == 1
        assert events[0].start == start.date()
        assert events[0].end == (start + timedelta(days=1)).date()
        assert await calendar.async_get_events(hass, start - timedelta(days=1), start) == []
        assert await calendar.async_get_events(hass, start + timedelta(days=1), start + timedelta(days=2)) == []
        assert len(await calendar.async_get_events(hass, start + timedelta(hours=12),
                                                  start + timedelta(hours=13))) == 1
        assert await calendar.async_get_events(hass, start + timedelta(hours=12),
                                               start + timedelta(hours=12)) == []


async def test_failed_refresh_preserves_calendar_and_sensor_together(hass):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    await data.collector.update()
    sensor = WasteTypeSensor(data, "restafval", config)
    calendar = AfvalbeheerCalendar(data, config)
    sensor.update()
    state, event, repository = sensor.state, calendar.event, data.collections

    async def fail_after_replacing_data():
        data.collector.collections = WasteCollectionRepository()
        return False

    with patch.object(data.collector, "_async_update", new=AsyncMock(side_effect=fail_after_replacing_data)):
        await data.async_update()
    sensor.update()
    assert data.collections is repository
    assert sensor.state == state
    assert calendar.event == event
    data.async_stop()
