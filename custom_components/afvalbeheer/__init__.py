"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 5.6.1 20250106
20230705 - Added support for Afval3xBeter
20230822 - Fix icon for papier-pmd
20230927 - Fix ZRD API
20231206 - Fix suffix handling for Circulus
20231208 - Fix naming of today and tomorrow sensors
20231219 - Support for new API Assen
20240109 - Add support for Woerden
20240109 - Add support for RWM
20240109 - Change dateobject to date
20240122 - Add support for Montferland API
20240124 - Update RecycleApp X-Secret
20240124 - Add support for Ôffalkalinder
20240201 - Revert change of dateobject
20240201 - Fix for collection days duplicates
20240215 - Better way to fix for collection days duplicates
20240216 - Use correct case for fractions
20240216 - Remove unwanted fractions from upcomming sensor
20240325 - Added support for DeFryskeMarren
20240325 - Fix spelling mistake in "Eerstvolgende"
20240414 - Fix deprecation warning for discovery
20240531 - Sort output of upcomming sensors
20240605 - Fix for RWM API
20240711 - Add mapping for PMD-Rest in Ximmio
20240711 - Fix sensor icons
20240827 - Add support for Cleanprofs
20240827 - Small bug fix with configs
20240829 - Support for new ROVA API
20240906 - New option for custom mapping
20240911 - Fix API url for Cyclus and Montfoort
20240917 - Fix API url for RyclycleApp
20240918 - Add support for Sliedrecht
20241205 - Add support for Saver
20241205 - Refactor sensor.py
20241206 - Fix bugs
20241209 - Fix attributes and date object
20250106 - Added support for Straatbeeld
20250116 - Fix for Burgerportaal

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
from homeassistant.helpers.discovery import async_load_platform, load_platform

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID
from .API import get_wastedata_from_config


__version__ = "5.6.1"


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
