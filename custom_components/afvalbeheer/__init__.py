import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import Platform

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID
from .API import Get_WasteData_From_Config


__version__ = "4.9.6"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.debug("Setup of Afvalbeheer component Rest API retriever")

    config = config.get(DOMAIN, None)

    if config is None:
        # This should not be nesseceary to keep the 'old' config methode using sensor and platform working.
        # If using sensor there is no DOMAIN entry in config but Platform function will be called from sensor.
        return True

    if not isinstance(config, list):
        config = [config]

    for conf in config:

        data = Get_WasteData_From_Config(hass, conf)

        hass.data.setdefault(DOMAIN, {})[conf[CONF_ID]] = data

        await hass.helpers.discovery.async_load_platform(
            Platform.SENSOR, DOMAIN, {"config": conf}, conf
        )

        # if you add boolean to config you could disable calendar entities from here
        hass.helpers.discovery.load_platform(
            Platform.CALENDAR, DOMAIN, {"config": conf}, conf
        )

        await data.schedule_update(timedelta())

    return True
