"""Integration tests for the sensor entity classes in sensor.py.

Exercises WasteTypeSensor, WasteDateSensor and WasteUpcomingSensor end-to-end
with the real `hass` fixture and the built-in demo collector (no network
access required). This guards against regressions in sensor.py's module-level
name resolution (e.g. after replacing `from .const import *` with explicit
imports) as well as basic update()/property behavior.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.const import (
    ATTR_DATA_STALE,
    ATTR_LAST_SUCCESSFUL_UPDATE,
    ATTR_LAST_UPDATE_SUCCESS,
    CONF_ALWAYS_SHOW_DAY,
    CONF_BOLD_ICONS,
    CONF_BUILT_IN_ICONS,
    CONF_BUILT_IN_ICONS_NEW,
    CONF_CUSTOM_MAPPING,
    CONF_CUSTOMER_ID,
    CONF_DATE_FORMAT,
    CONF_DATE_OBJECT,
    CONF_DATE_ONLY,
    CONF_DAY_OF_WEEK,
    CONF_DAY_OF_WEEK_ONLY,
    CONF_DISABLE_ICONS,
    CONF_ENTRY_ID,
    CONF_NAME,
    CONF_NAME_PREFIX,
    CONF_POSTCODE,
    CONF_PRINT_AVAILABLE_WASTE_TYPES,
    CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS,
    CONF_RESOURCES,
    CONF_STREET_NUMBER,
    CONF_UPDATE_INTERVAL,
    CONF_WASTE_COLLECTOR,
)
from custom_components.afvalbeheer.models import WasteCollection, WasteCollectionRepository
from custom_components.afvalbeheer.sensor import (
    WasteDateSensor,
    WasteTypeSensor,
    WasteUpcomingSensor,
)


def _demo_config(**overrides):
    config = {
        CONF_WASTE_COLLECTOR: "demo",
        CONF_POSTCODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_RESOURCES: ["restafval"],
        CONF_CUSTOM_MAPPING: {},
        CONF_PRINT_AVAILABLE_WASTE_TYPES: False,
        CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS: False,
        CONF_UPDATE_INTERVAL: 0,
        CONF_CUSTOMER_ID: "",
        CONF_BUILT_IN_ICONS_NEW: True,
        CONF_BUILT_IN_ICONS: False,
        CONF_DISABLE_ICONS: False,
        CONF_BOLD_ICONS: False,
        CONF_NAME: "",
        CONF_NAME_PREFIX: False,
        CONF_DATE_FORMAT: "%d-%m-%Y",
        CONF_DAY_OF_WEEK: True,
        CONF_DAY_OF_WEEK_ONLY: False,
        CONF_ALWAYS_SHOW_DAY: False,
        CONF_DATE_ONLY: False,
        CONF_DATE_OBJECT: False,
        CONF_ENTRY_ID: "test_entry",
    }
    config.update(overrides)
    return config


async def test_waste_type_sensor_update_cycle(hass):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    await data.collector.update()

    sensor = WasteTypeSensor(data, "restafval", config)
    sensor.update()

    assert sensor.name
    assert isinstance(sensor.extra_state_attributes, dict)


async def test_waste_date_sensor_update_cycle(hass):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    await data.collector.update()

    sensor = WasteDateSensor(data, config, timedelta(days=0))
    sensor.update()

    assert sensor.name
    assert isinstance(sensor.extra_state_attributes, dict)


async def test_waste_upcoming_sensor_update_cycle(hass):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    await data.collector.update()

    sensor = WasteUpcomingSensor(data, config)
    sensor.update()

    assert sensor.name
    assert isinstance(sensor.extra_state_attributes, dict)


async def test_sensor_exposes_failed_refresh_and_recovery(hass):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    sensor = WasteTypeSensor(data, 'restafval', config)
    assert sensor.extra_state_attributes[ATTR_DATA_STALE] is True
    assert sensor.extra_state_attributes[ATTR_LAST_UPDATE_SUCCESS] is None

    await data.collector.update()
    sensor.update()
    timestamp = data.collector.last_successful_update
    state = sensor.state
    assert sensor.extra_state_attributes[ATTR_DATA_STALE] is False
    assert sensor.extra_state_attributes[ATTR_LAST_SUCCESSFUL_UPDATE] == timestamp

    with patch.object(data.collector, '_async_update', new=AsyncMock(return_value=False)):
        await data.collector.update()
    sensor.update()
    assert sensor.state == state
    assert sensor.extra_state_attributes[ATTR_LAST_UPDATE_SUCCESS] is False
    assert sensor.extra_state_attributes[ATTR_DATA_STALE] is True
    assert sensor.extra_state_attributes[ATTR_LAST_SUCCESSFUL_UPDATE] == timestamp

    await data.collector.update()
    assert sensor.extra_state_attributes[ATTR_LAST_UPDATE_SUCCESS] is True
    assert sensor.extra_state_attributes[ATTR_DATA_STALE] is False


@pytest.mark.parametrize('kind', ['today', 'tomorrow', 'upcoming'])
@pytest.mark.parametrize('success', [None, False, True])
async def test_exhausted_calendar_distinguishes_stale_from_empty(hass, kind, success):
    """Yesterday's cached entry must not imply a confirmed empty calendar."""
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    data.collections.add(WasteCollection.create(
        date=datetime.now() - timedelta(days=1),
        waste_type='restafval', waste_type_slug='restafval',
    ))
    data.collector.last_update_success = success
    if kind == 'upcoming':
        sensor = WasteUpcomingSensor(data, config)
    else:
        sensor = WasteDateSensor(data, config, timedelta(days=kind == 'tomorrow'))

    sensor.update()
    if success is True:
        assert sensor.state is not None
    else:
        assert sensor.state is None
    assert sensor.extra_state_attributes[ATTR_DATA_STALE] is (success is not True)


@pytest.mark.parametrize('kind', ['today', 'tomorrow', 'upcoming', 'type'])
async def test_failed_refresh_keeps_matching_cached_dates_visible(hass, kind):
    config = _demo_config()
    data = get_wastedata_from_config(hass, config)
    data.collections.add(WasteCollection.create(
        date=(datetime.now() + timedelta(days=kind != 'today')).replace(
            hour=0, minute=0, second=0, microsecond=0,
        ),
        waste_type='restafval', waste_type_slug='restafval',
    ))
    data.collector.last_update_success = False
    if kind == 'upcoming':
        sensor = WasteUpcomingSensor(data, config)
    elif kind == 'type':
        sensor = WasteTypeSensor(data, 'restafval', config)
    else:
        sensor = WasteDateSensor(data, config, timedelta(days=kind == 'tomorrow'))

    sensor.update()
    assert sensor.state is not None
    assert sensor.extra_state_attributes[ATTR_DATA_STALE] is True


def test_waste_type_sensor_uses_collector_icon_data_by_default():
    icon_data = "data:image/svg+xml;base64,PHN2Zy8+"
    collections = WasteCollectionRepository()
    collections.add(WasteCollection.create(
        date=datetime.now() + timedelta(days=1),
        waste_type="Groente-, fruit- en tuinafval",
        waste_type_slug="Groente-, fruit- en tuinafval",
        icon_data=icon_data,
    ))
    data = SimpleNamespace(collections=collections)
    config = _demo_config(**{
        CONF_BUILT_IN_ICONS_NEW: False,
        CONF_BUILT_IN_ICONS: False,
        CONF_RESOURCES: ["Groente-, fruit- en tuinafval"],
    })

    sensor = WasteTypeSensor(data, "Groente-, fruit- en tuinafval", config)
    sensor.update()

    assert sensor.entity_picture == icon_data


def test_waste_type_sensor_uses_collector_icon_data_for_classic_fraction_by_default():
    collections = WasteCollectionRepository()
    icon_data = "data:image/svg+xml;base64,PHN2Zy8+"
    collections.add(WasteCollection.create(
        date=datetime.now() + timedelta(days=1),
        waste_type="restafval",
        waste_type_slug="restafval",
        icon_data=icon_data,
    ))
    data = SimpleNamespace(collections=collections)
    config = _demo_config(**{CONF_BUILT_IN_ICONS_NEW: False, CONF_BUILT_IN_ICONS: False})

    sensor = WasteTypeSensor(data, "restafval", config)
    sensor.update()

    assert sensor.entity_picture == icon_data


def test_waste_type_sensor_prefers_classic_icon_over_collector_icon_data_when_enabled():
    collections = WasteCollectionRepository()
    collections.add(WasteCollection.create(
        date=datetime.now() + timedelta(days=1),
        waste_type="restafval",
        waste_type_slug="restafval",
        icon_data="data:image/svg+xml;base64,PHN2Zy8+",
    ))
    data = SimpleNamespace(collections=collections)
    config = _demo_config(**{CONF_BUILT_IN_ICONS_NEW: False, CONF_BUILT_IN_ICONS: True})

    sensor = WasteTypeSensor(data, "restafval", config)
    sensor.update()

    assert sensor.entity_picture is None
    assert sensor.icon == "afvalbeheer:restafval"
