"""Tests for BaseSensor._format_date, the smart date-display logic shared by
all sensor types.

Uses freezegun (via the `freezer` fixture from pytest-freezer) to pin "now" so
relative labels (today/tomorrow/day-of-week/plain date) are deterministic.

Collection dates are always midnight (collectors build them from
`datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)`, see
DemoCollector), while "now" is a later time of day. _format_date's day-diff
calculation (`(collection_date - datetime.now()).days + 1`) depends on that
time-of-day offset, so the frozen "now" is deliberately later than midnight
to match real-world behavior.
"""
from datetime import datetime, timedelta

from custom_components.afvalbeheer.const import (
    CONF_ALWAYS_SHOW_DAY,
    CONF_BOLD_ICONS,
    CONF_BUILT_IN_ICONS,
    CONF_BUILT_IN_ICONS_NEW,
    CONF_DATE_FORMAT,
    CONF_DATE_OBJECT,
    CONF_DATE_ONLY,
    CONF_DAY_OF_WEEK,
    CONF_DAY_OF_WEEK_ONLY,
    CONF_DISABLE_ICONS,
    CONF_ENTRY_ID,
    CONF_LANGUAGE,
    CONF_RESOURCES,
    CONF_WASTE_COLLECTOR,
    LANGUAGE_EN,
    LANGUAGE_NL,
)
from custom_components.afvalbeheer.sensor import BaseSensor

# "Now" is a Monday at 09:00; collection dates are midnight on later days.
FROZEN_NOW = datetime(2026, 10, 12, 9, 0, 0)
MIDNIGHT_TODAY = datetime(2026, 10, 12, 0, 0, 0)


def _date(days_from_today):
    return MIDNIGHT_TODAY + timedelta(days=days_from_today)


def _make_sensor(**overrides):
    config = {
        CONF_WASTE_COLLECTOR: "demo",
        CONF_ENTRY_ID: "test",
        CONF_DATE_FORMAT: "%d-%m-%Y",
        CONF_DATE_OBJECT: False,
        CONF_BUILT_IN_ICONS: False,
        CONF_BUILT_IN_ICONS_NEW: False,
        CONF_DISABLE_ICONS: False,
        CONF_BOLD_ICONS: False,
        CONF_DAY_OF_WEEK: True,
        CONF_DAY_OF_WEEK_ONLY: False,
        CONF_ALWAYS_SHOW_DAY: False,
        CONF_DATE_ONLY: False,
        CONF_RESOURCES: ["restafval"],
        CONF_LANGUAGE: LANGUAGE_NL,
    }
    config.update(overrides)
    return BaseSensor(data=None, config=config)


def test_format_date_today(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor()
    assert sensor._format_date(_date(0)) == "Vandaag, 12-10-2026"


def test_format_date_tomorrow(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor()
    assert sensor._format_date(_date(1)) == "Morgen, 13-10-2026"


def test_format_date_today_day_of_week_only(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_DAY_OF_WEEK_ONLY: True})
    assert sensor._format_date(_date(0)) == "Vandaag"


def test_format_date_tomorrow_day_of_week_only(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_DAY_OF_WEEK_ONLY: True})
    assert sensor._format_date(_date(1)) == "Morgen"


def test_format_date_within_week_shows_day_name(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor()
    # 3 days out: Thursday, within the 8-day "show day" window.
    assert sensor._format_date(_date(3)) == "Donderdag, 15-10-2026"


def test_format_date_far_future_drops_day_name(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor()
    # 10 days out: beyond the 8-day window, so only the plain date shows.
    assert sensor._format_date(_date(10)) == "22-10-2026"


def test_format_date_always_show_day_keeps_day_name_far_future(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_ALWAYS_SHOW_DAY: True})
    assert sensor._format_date(_date(10)) == "Donderdag, 22-10-2026"


def test_format_date_date_only_ignores_today_tomorrow_and_day_name(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_DATE_ONLY: True})
    assert sensor._format_date(_date(1)) == "13-10-2026"
    assert sensor._format_date(_date(3)) == "15-10-2026"


def test_format_date_day_of_week_disabled_shows_plain_date(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_DAY_OF_WEEK: False})
    assert sensor._format_date(_date(3)) == "15-10-2026"


def test_format_date_returns_raw_datetime_when_date_object(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_DATE_OBJECT: True})
    target = _date(1)
    assert sensor._format_date(target) == target


def test_format_date_english_translation(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_LANGUAGE: LANGUAGE_EN})
    assert sensor._format_date(_date(0)) == "Today, 12-10-2026"
    assert sensor._format_date(_date(3)) == "Thursday, 15-10-2026"


def test_format_date_day_name_combines_with_custom_date_format(freezer):
    freezer.move_to(FROZEN_NOW)
    sensor = _make_sensor(**{CONF_DATE_FORMAT: "%Y-%m-%d"})
    assert sensor._format_date(_date(3)) == "Donderdag, 2026-10-15"
