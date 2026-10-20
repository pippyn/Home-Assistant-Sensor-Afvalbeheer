"""Tests for the Opzet collector: next pickups from /afvalstromen combined with the full calendar."""
from datetime import date, datetime, timedelta

import pytest
import requests

from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.collectors.shared import opzet as opzet_module
from custom_components.afvalbeheer.const import (
    CONF_CUSTOM_MAPPING,
    CONF_CUSTOMER_ID,
    CONF_POSTCODE,
    CONF_PRINT_AVAILABLE_WASTE_TYPES,
    CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS,
    CONF_RESOURCES,
    CONF_STREET_NUMBER,
    CONF_UPDATE_INTERVAL,
    CONF_WASTE_COLLECTOR,
    WASTE_TYPE_GREEN,
    WASTE_TYPE_GREY,
)
from custom_components.afvalbeheer.models import WasteCollection

GFT = 9
REST = 3


def _day(offset, base=None):
    return ((base or date.today()) + timedelta(days=offset)).isoformat()


def _streams(base=None):
    """What /afvalstromen returns: the next pickup per waste stream."""
    return [
        {"id": GFT, "menu_title": "Groente-, fruit- en tuinafval (gft)", "ophaaldatum": _day(3, base)},
        {"id": REST, "menu_title": "Restafval", "ophaaldatum": _day(10, base)},
        {"id": 11, "menu_title": "Textiel", "ophaaldatum": None},
    ]


class _Response:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


class _Session:
    """Answers like the Opzet API. A calendar value can be a list, an exception to raise, or missing (404)."""

    def __init__(self, calendars, streams=None):
        self.calendars = calendars
        self.streams = streams if streams is not None else _streams()
        self.years = []

    def get(self, url, **kwargs):
        if url.endswith("/afvalstromen"):
            return _Response(self.streams)
        if "/kalender/" in url:
            year = int(url.rsplit("/", 1)[1])
            self.years.append(year)
            calendar = self.calendars.get(year)
            if isinstance(calendar, Exception):
                raise calendar
            if calendar is None:
                return _Response(None, status_code=404)
            return _Response(calendar)
        raise AssertionError(f"unexpected url {url}")


class _FrozenDatetime(datetime):
    moment = None

    @classmethod
    def now(cls, tz=None):
        return cls.moment


def _freeze(monkeypatch, moment):
    _FrozenDatetime.moment = moment
    monkeypatch.setattr(opzet_module, "datetime", _FrozenDatetime)


def _config():
    return {
        CONF_WASTE_COLLECTOR: "lingewaard",
        CONF_POSTCODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_RESOURCES: ["gft", "restafval"],
        CONF_CUSTOM_MAPPING: {},
        CONF_PRINT_AVAILABLE_WASTE_TYPES: False,
        CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS: False,
        CONF_UPDATE_INTERVAL: 0,
        CONF_CUSTOMER_ID: "",
    }


def _collector(hass, session):
    collector = get_wastedata_from_config(hass, _config()).collector
    collector.bag_id = "0000000000000001"
    collector._session = session
    return collector


async def _update(hass, calendars, streams=None):
    collector = _collector(hass, _Session(calendars, streams))
    await collector.update()
    return collector


def _dates(collector, waste_type):
    return sorted(c.date.date().isoformat() for c in collector.collections if c.waste_type == waste_type)


async def test_full_calendar_is_used(hass):
    this_year = date.today().year
    calendar = [
        {"afvalstroom_id": GFT, "ophaaldatum": _day(-4)},
        {"afvalstroom_id": GFT, "ophaaldatum": _day(3)},
        {"afvalstroom_id": GFT, "ophaaldatum": _day(17)},
        {"afvalstroom_id": REST, "ophaaldatum": _day(10)},
        {"afvalstroom_id": 99, "ophaaldatum": _day(5)},
    ]
    # Next year's calendar can repeat the last dates of this year; they must not be added twice.
    collector = await _update(hass, {this_year: calendar, this_year + 1: [{"afvalstroom_id": GFT, "ophaaldatum": _day(17)}]})

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3), _day(17)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]


async def test_next_pickups_without_calendar(hass):
    collector = await _update(hass, {})

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]


async def test_stream_missing_from_calendar_keeps_its_next_pickup(hass):
    calendar = [{"afvalstroom_id": GFT, "ophaaldatum": _day(3)}, {"afvalstroom_id": GFT, "ophaaldatum": _day(17)}]
    collector = await _update(hass, {date.today().year: calendar})

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3), _day(17)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]


@pytest.mark.parametrize("failure", [requests.exceptions.ConnectionError("down"), None])
async def test_one_year_failing_keeps_the_other(hass, failure):
    this_year = date.today().year
    calendars = {this_year: [{"afvalstroom_id": GFT, "ophaaldatum": _day(17)}], this_year + 1: failure}
    collector = await _update(hass, calendars)

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3), _day(17)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]


async def test_malformed_calendar_entries_are_skipped(hass):
    calendar = [
        None,
        "2026-01-01",
        5,
        {"afvalstroom_id": GFT},
        {"afvalstroom_id": GFT, "ophaaldatum": None},
        {"afvalstroom_id": GFT, "ophaaldatum": "2099-99-99"},
        {"afvalstroom_id": GFT, "ophaaldatum": "morgen"},
        {"afvalstroom_id": GFT, "ophaaldatum": _day(17)},
    ]
    collector = await _update(hass, {date.today().year: calendar})

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3), _day(17)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]


async def test_today_is_kept_and_yesterday_is_not(hass, monkeypatch):
    today = date(2026, 6, 15)
    _freeze(monkeypatch, datetime(2026, 6, 15, 23, 30))
    calendar = [
        {"afvalstroom_id": REST, "ophaaldatum": "2026-06-14"},
        {"afvalstroom_id": REST, "ophaaldatum": "2026-06-15"},
    ]
    collector = await _update(hass, {2026: calendar}, _streams(today))

    assert _dates(collector, WASTE_TYPE_GREY) == ["2026-06-15", _day(10, today)]


async def test_year_boundary_uses_next_years_calendar(hass, monkeypatch):
    today = date(2026, 12, 20)
    _freeze(monkeypatch, datetime(2026, 12, 20, 9, 0))
    session = _Session(
        {
            2026: [{"afvalstroom_id": GFT, "ophaaldatum": "2026-12-10"}, {"afvalstroom_id": GFT, "ophaaldatum": "2026-12-28"}],
            2027: [{"afvalstroom_id": GFT, "ophaaldatum": "2026-12-28"}, {"afvalstroom_id": GFT, "ophaaldatum": "2027-01-04"}],
        },
        _streams(today),
    )
    collector = _collector(hass, session)
    await collector.update()

    assert session.years == [2026, 2027]
    assert _dates(collector, WASTE_TYPE_GREEN) == ["2026-12-23", "2026-12-28", "2027-01-04"]


async def test_existing_collections_survive_a_processing_failure(hass, monkeypatch):
    collector = _collector(hass, _Session({date.today().year: [{"afvalstroom_id": GFT, "ophaaldatum": _day(17)}]}))
    existing = WasteCollection.create(date=datetime(2026, 1, 1), waste_type=WASTE_TYPE_GREEN, waste_type_slug="gft")
    collector.collections.add(existing)

    def fails(name):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(collector, "map_waste_type", fails)
    with pytest.raises(RuntimeError):
        await collector.update()

    assert list(collector.collections) == [existing]
