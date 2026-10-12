"""Shared pytest fixtures for the Afvalbeheer test suite."""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom integrations (like afvalbeheer) available during tests.

    Without this, Home Assistant's test harness only loads built-in
    integrations and `custom_components/afvalbeheer` would not be found.
    """
    yield
