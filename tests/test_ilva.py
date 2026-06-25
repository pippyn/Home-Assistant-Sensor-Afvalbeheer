"""
Unit tests for ILVA waste collector.
Tests the async functionality and error handling of the ILVA collector.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class MockResponse:
    """Mock aiohttp response."""
    def __init__(self, data, status=200):
        self._data = data
        self.status = status

    async def json(self):
        return self._data

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"HTTP {self.status}")


class MockContextManager:
    """Async context manager for mock response."""
    def __init__(self, response):
        self.response = response
    
    async def __aenter__(self):
        return self.response
    
    async def __aexit__(self, exc_type, exc, tb):
        pass


class MockSession:
    """Mock aiohttp session."""
    def __init__(self, mapping):
        self.mapping = mapping  # dict with URL patterns

    def get(self, url, timeout=30):
        """Returns an async context manager (not async itself)."""
        # Match URLs more carefully - check longest matches first
        sorted_keys = sorted(self.mapping.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in url:
                return MockContextManager(MockResponse(self.mapping[key]))
        return MockContextManager(MockResponse({"data": []}))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_ilva_successful_lookup():
    """Test successful street and address lookup."""
    from custom_components.afvalbeheer.collectors.individual.ilva import ILVACollector
    
    streets = {"data": [{"id": 2325, "name": "Hollestraat", "sub_municipality": {"id": 29, "name": "Idegem", "zip": "9506"}}]}
    addresses = {"data": [{"id": 83007, "number": "20"}]}
    days = {"data": [{"id": 66690, "date": "2026-01-06", "waste_type": {"id": 22, "name": "pmd"}}]}

    mapping = {
        "/streets?": streets,
        "/addresses?": addresses,
        "/days": days,
    }

    mock_session = MockSession(mapping)

    def fake_get_clientsession(hass):
        return mock_session

    mock_store = AsyncMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch('custom_components.afvalbeheer.collectors.individual.ilva.async_get_clientsession', fake_get_clientsession), \
         patch('custom_components.afvalbeheer.collectors.individual.ilva.Store', return_value=mock_store):
        
        collector = ILVACollector(None, 'ilva', '9506', '20', '', {}, 'Hollestraat', 'Idegem')
        await collector.update()

        types = collector.collections.get_available_waste_types()
        assert any('pmd' in str(t).lower() for t in types)


@pytest.mark.asyncio
async def test_ilva_wrong_postcode_tries_next():
    """Test postcode matching—prefer street with matching zip code."""
    from custom_components.afvalbeheer.collectors.individual.ilva import ILVACollector
    
    # First street has wrong zip, second has correct
    streets = {"data": [
        {"id": 1, "name": "Hollestraat", "sub_municipality": {"zip": "0000"}},
        {"id": 2325, "name": "Hollestraat", "sub_municipality": {"zip": "9506"}},
    ]}
    addresses = {"data": [{"id": 83007, "number": "20"}]}
    days = {"data": []}

    mapping = {
        "/streets?": streets,
        "/addresses?": addresses,
        "/days": days,
    }

    mock_session = MockSession(mapping)

    def fake_get_clientsession(hass):
        return mock_session

    mock_store = AsyncMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch('custom_components.afvalbeheer.collectors.individual.ilva.async_get_clientsession', fake_get_clientsession), \
         patch('custom_components.afvalbeheer.collectors.individual.ilva.Store', return_value=mock_store):
        
        collector = ILVACollector(None, 'ilva', '9506', '20', '', {}, 'Hollestraat', 'Idegem')
        await collector.update()
        # Check that the correct street_id (2325) was selected
        assert collector._cached_ids.get('street_id') == 2325


@pytest.mark.asyncio
async def test_ilva_unknown_street_no_crash():
    """Test that unknown street doesn't crash collector."""
    from custom_components.afvalbeheer.collectors.individual.ilva import ILVACollector
    
    streets = {"data": []}
    mapping = {"/streets?": streets}
    mock_session = MockSession(mapping)

    def fake_get_clientsession(hass):
        return mock_session

    mock_store = AsyncMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch('custom_components.afvalbeheer.collectors.individual.ilva.async_get_clientsession', fake_get_clientsession), \
         patch('custom_components.afvalbeheer.collectors.individual.ilva.Store', return_value=mock_store):
        
        collector = ILVACollector(None, 'ilva', '9506', '20', '', {}, 'NoSuchStreet', 'Idegem')
        await collector.update()
        assert len(collector.collections.get_available_waste_types()) == 0


@pytest.mark.asyncio
async def test_ilva_unknown_waste_type_fallback():
    """Test that unknown waste types are handled gracefully."""
    from custom_components.afvalbeheer.collectors.individual.ilva import ILVACollector
    
    streets = {"data": [{"id": 2325, "name": "Hollestraat", "sub_municipality": {"zip": "9506"}}]}
    addresses = {"data": [{"id": 83007, "number": "20"}]}
    days = {"data": [{"id": 1, "date": "2026-01-10", "waste_type": {"id": 99, "name": "STRANGE_TYPE"}}]}

    mapping = {
        "/streets?": streets,
        "/addresses?": addresses,
        "/days": days,
    }

    mock_session = MockSession(mapping)

    def fake_get_clientsession(hass):
        return mock_session

    mock_store = AsyncMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch('custom_components.afvalbeheer.collectors.individual.ilva.async_get_clientsession', fake_get_clientsession), \
         patch('custom_components.afvalbeheer.collectors.individual.ilva.Store', return_value=mock_store):
        
        collector = ILVACollector(None, 'ilva', '9506', '20', '', {}, 'Hollestraat', 'Idegem')
        await collector.update()
        types = collector.collections.get_available_waste_types()
        assert any('STRANGE_TYPE' in str(t) for t in types)
