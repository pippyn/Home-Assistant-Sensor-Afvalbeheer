"""Tests for the Opzet collector: full calendar with a fallback to the next pickup per waste stream."""
from datetime import date, timedelta

from custom_components.afvalbeheer.API import get_wastedata_from_config
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


def _day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


STREAMS = [
    {"id": 9, "menu_title": "Groente-, fruit- en tuinafval (gft)", "ophaaldatum": _day(3)},
    {"id": 3, "menu_title": "Restafval", "ophaaldatum": _day(10)},
    {"id": 11, "menu_title": "Textiel", "ophaaldatum": None},
]


class _Response:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


class _Session:
    """Answers like the Opzet API: afvalstromen, and a calendar per year."""

    def __init__(self, calendars):
        self.calendars = calendars

    def get(self, url, **kwargs):
        if url.endswith("/afvalstromen"):
            return _Response(STREAMS)
        if "/kalender/" in url:
            year = int(url.rsplit("/", 1)[1])
            if year not in self.calendars:
                return _Response(None, status_code=404)
            return _Response(self.calendars[year])
        raise AssertionError(f"unexpected url {url}")


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


async def _update(hass, calendars):
    data = get_wastedata_from_config(hass, _config())
    collector = data.collector
    collector.bag_id = "0000000000000001"
    collector._session = _Session(calendars)
    await collector.update()
    return collector


def _dates(collector, waste_type):
    return sorted(c.date.date().isoformat() for c in collector.collections if c.waste_type == waste_type)


async def test_opzet_uses_full_calendar(hass):
    this_year = date.today().year
    calendar = [
        {"afvalstroom_id": 9, "ophaaldatum": _day(-4)},
        {"afvalstroom_id": 9, "ophaaldatum": _day(3)},
        {"afvalstroom_id": 9, "ophaaldatum": _day(17)},
        {"afvalstroom_id": 3, "ophaaldatum": _day(10)},
        {"afvalstroom_id": 99, "ophaaldatum": _day(5)},
    ]
    # The next year's calendar can repeat the last dates of this year; they must not be added twice.
    collector = await _update(hass, {this_year: calendar, this_year + 1: [{"afvalstroom_id": 9, "ophaaldatum": _day(17)}]})

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3), _day(17)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]


async def test_opzet_falls_back_to_next_pickup_without_calendar(hass):
    collector = await _update(hass, {})

    assert _dates(collector, WASTE_TYPE_GREEN) == [_day(3)]
    assert _dates(collector, WASTE_TYPE_GREY) == [_day(10)]
