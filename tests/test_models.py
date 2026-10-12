"""Tests for WasteCollection and WasteCollectionRepository."""
from datetime import datetime, timedelta

from custom_components.afvalbeheer.models.waste_collection import WasteCollection
from custom_components.afvalbeheer.models.waste_repository import WasteCollectionRepository


def _collection(days_from_now, waste_type, waste_type_slug=None):
    date = datetime.now() + timedelta(days=days_from_now)
    return WasteCollection.create(
        date=date,
        waste_type=waste_type,
        waste_type_slug=waste_type_slug or waste_type.lower(),
    )


def test_waste_collection_equality():
    date = datetime.now()
    a = WasteCollection.create(date=date, waste_type="Papier", waste_type_slug="papier")
    b = WasteCollection.create(date=date, waste_type="Papier", waste_type_slug="papier")
    c = WasteCollection.create(date=date, waste_type="Restafval", waste_type_slug="restafval")
    assert a == b
    assert a != c
    assert a != "not a collection"


def test_repository_add_and_len():
    repo = WasteCollectionRepository()
    assert len(repo) == 0
    repo.add(_collection(1, "Papier"))
    repo.add(_collection(2, "Restafval"))
    assert len(repo) == 2
    assert list(repo)[0].waste_type == "Papier"


def test_repository_remove_all():
    repo = WasteCollectionRepository()
    repo.add(_collection(1, "Papier"))
    repo.remove_all()
    assert len(repo) == 0


def test_repository_get_sorted():
    repo = WasteCollectionRepository()
    repo.add(_collection(5, "Restafval"))
    repo.add(_collection(1, "Papier"))
    repo.add(_collection(3, "GFT"))
    sorted_types = [c.waste_type for c in repo.get_sorted()]
    assert sorted_types == ["Papier", "GFT", "Restafval"]


def test_repository_get_upcoming_excludes_past():
    repo = WasteCollectionRepository()
    repo.add(_collection(-1, "Restafval"))  # in the past
    repo.add(_collection(2, "Papier"))
    upcoming_types = [c.waste_type for c in repo.get_upcoming()]
    assert upcoming_types == ["Papier"]


def test_repository_get_first_upcoming_filters_by_type_and_date():
    repo = WasteCollectionRepository()
    repo.add(_collection(1, "Papier"))
    repo.add(_collection(1, "GFT"))
    repo.add(_collection(5, "Restafval"))
    first = repo.get_first_upcoming(waste_types=["papier", "gft"])
    assert {c.waste_type for c in first} == {"Papier", "GFT"}


def test_repository_get_first_upcoming_without_match_returns_empty():
    repo = WasteCollectionRepository()
    repo.add(_collection(1, "Papier"))
    assert repo.get_first_upcoming(waste_types=["restafval"]) == []
    assert repo.get_first_upcoming(waste_types=None) == []


def test_repository_get_upcoming_by_type_is_case_insensitive():
    repo = WasteCollectionRepository()
    repo.add(_collection(1, "Papier"))
    repo.add(_collection(2, "Papier"))
    repo.add(_collection(1, "Restafval"))
    result = repo.get_upcoming_by_type("PAPIER")
    assert len(result) == 2
    assert all(c.waste_type == "Papier" for c in result)


def test_repository_get_first_upcoming_by_type():
    repo = WasteCollectionRepository()
    repo.add(_collection(3, "Papier"))
    repo.add(_collection(1, "Papier"))
    first = repo.get_first_upcoming_by_type("papier")
    assert first is not None
    assert first.date.date() == (datetime.now() + timedelta(days=1)).date()


def test_repository_get_first_upcoming_by_type_none_when_missing():
    repo = WasteCollectionRepository()
    assert repo.get_first_upcoming_by_type("papier") is None


def test_repository_get_by_date_with_and_without_filter():
    target_date = datetime.now() + timedelta(days=4)
    repo = WasteCollectionRepository()
    repo.add(WasteCollection.create(date=target_date, waste_type="Papier", waste_type_slug="papier"))
    repo.add(WasteCollection.create(date=target_date, waste_type="GFT", waste_type_slug="gft"))
    repo.add(_collection(10, "Restafval"))

    all_on_date = repo.get_by_date(target_date)
    assert {c.waste_type for c in all_on_date} == {"Papier", "GFT"}

    filtered = repo.get_by_date(target_date, waste_types=["papier"])
    assert [c.waste_type for c in filtered] == ["Papier"]


def test_repository_get_available_waste_types_and_slugs():
    repo = WasteCollectionRepository()
    repo.add(_collection(1, "Papier", "papier"))
    repo.add(_collection(2, "GFT", "gft"))
    repo.add(_collection(3, "Papier", "papier"))
    assert repo.get_available_waste_types() == ["GFT", "Papier"]
    assert repo.get_available_waste_type_slugs() == ["gft", "papier"]
