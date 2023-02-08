"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 5.0.15 20230208
20220829 - Major change: Added Calendar support (credits @WouterTuinstra)
20220829 - Give persistant notifications unique id's
20220901 - Code cleanup
20220913 - Fix: translate today and tomorrow sensor
20221010 - Restoring an entity and attributes on Home Assistant Restart
20221015 - Fix Meerlanden
20221018 - Restore entity picture
20221019 - Add new icons
20221021 - Fix for Mijn AfvalWijzer
20221025 - Update RecycleApp token
20221107 - Remove Unit of measurement for better history
20221108 - Fix RecycleApp mapping
20230104 - Remove deprecated DEVICE_CLASS_*
20230123 - Change mapping for Afvalwijzer
20230125 - Only add requested fractions to calendar
20230208 - Add Dutch day abbreviations

Example config:
Configuration.yaml:
afvalbeheer:
    wastecollector: Blink
    resources:
    - restafval
    - gft
    - papier
    - pmd
    postcode: 1111AA
    streetnumber: 1
    upcomingsensor: 0                # (optional)
    dateformat: '%d-%m-%Y'           # (optional)
    dateonly: 0                      # (optional)
    dateobject: 0                    # (optional)
    dayofweek: 1                     # (optional)
    name: ''                         # (optional)
    nameprefix: 1                    # (optional)
    builtinicons: 0                  # (optional)
"""

import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import Platform

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID
from .API import Get_WasteData_From_Config


__version__ = "5.0.15"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.debug("Setup of Afvalbeheer component Rest API retriever")

    config = config.get(DOMAIN, None)

    if config is None:
        return True

    if not isinstance(config, list):
        config = [config]

    for conf in config:

        data = Get_WasteData_From_Config(hass, conf)

        hass.data.setdefault(DOMAIN, {})[conf[CONF_ID]] = data

        await hass.helpers.discovery.async_load_platform(
            Platform.SENSOR, DOMAIN, {"config": conf}, conf
        )

        hass.helpers.discovery.load_platform(
            Platform.CALENDAR, DOMAIN, {"config": conf}, conf
        )

        await data.schedule_update(timedelta())

    return True
