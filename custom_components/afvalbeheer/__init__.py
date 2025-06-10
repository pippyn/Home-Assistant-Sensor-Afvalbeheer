"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 6.0.0 20250610
"""

import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import Platform

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.discovery import async_load_platform, load_platform

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID
from .API import get_wastedata_from_config


__version__ = "6.0.0"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.debug("Setup of Afvalbeheer component Rest API retriever")

    config = config.get(DOMAIN, None)

    if config is None:
        return True

    if not isinstance(config, list):
        config = [config]

    for conf in config:

        data = get_wastedata_from_config(hass, conf)

        hass.data.setdefault(DOMAIN, {})[conf[CONF_ID]] = data

        await async_load_platform(
            hass, Platform.SENSOR, DOMAIN, {"config": conf}, conf
        )

        load_platform(
            hass, Platform.CALENDAR, DOMAIN, {"config": conf}, conf
        )

        await data.schedule_update(timedelta())

    return True


async def async_setup_entry(hass, entry):
    config = {**entry.data, **entry.options}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {
        "config": config,
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "calendar"])
    return True


async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "calendar"])

    # Clean up stored data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
