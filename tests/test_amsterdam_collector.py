"""Tests for Amsterdam's first-weekday-of-the-month collections."""
from datetime import datetime

import pytest

from custom_components.afvalbeheer.collectors.individual.amsterdam import AmsterdamCollector


@pytest.fixture
def collector(hass):
    """Create a collector without fetching address or collection data."""
    return AmsterdamCollector(hass, "amsterdam", "1234AB", "1", "", {})


@pytest.mark.parametrize("hour", [0, 9, 23])
def test_monthly_collection_includes_today(collector, hour):
    """Keep today's first-Tuesday pickup, even after midnight."""
    item = {
        "afvalwijzerOphaaldagen": "dinsdag",
        "afvalwijzerAfvalkalenderFrequentie": "1evandemaand",
    }

    dates = collector._process_collection_dates(item, datetime(2026, 11, 3, hour))

    assert dates[0] == datetime(2026, 11, 3)
    assert dates[1] == datetime(2026, 12, 1)


def test_monthly_collection_excludes_yesterday(collector):
    """Drop the monthly pickup once its collection day has passed."""
    dates = collector._generate_first_weekday_dates_for_year(2, datetime(2026, 11, 4))

    assert dates[0] == datetime(2026, 12, 1)
    assert len(dates) == 12


@pytest.mark.parametrize("weekday", range(1, 8))
def test_monthly_collection_weekdays_and_year_rollover(collector, weekday):
    """Generate the first matching weekday across the December/January boundary."""
    dates = collector._generate_first_weekday_dates_for_year(weekday, datetime(2026, 12, 1))

    assert len(dates) == 13
    assert (dates[0].year, dates[0].month) == (2026, 12)
    assert (dates[1].year, dates[1].month) == (2027, 1)
    assert (dates[-1].year, dates[-1].month) == (2027, 12)
    assert all(date.isoweekday() == weekday and 1 <= date.day <= 7 for date in dates)
