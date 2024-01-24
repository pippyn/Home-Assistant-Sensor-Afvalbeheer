"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 5.2.17 20240124
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
20240124 - Add support for Offalkalinder

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
from .API import get_wastedata_from_config


__version__ = "5.2.17"


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

        await hass.helpers.discovery.async_load_platform(
            Platform.SENSOR, DOMAIN, {"config": conf}, conf
        )

        hass.helpers.discovery.load_platform(
            Platform.CALENDAR, DOMAIN, {"config": conf}, conf
        )

        await data.schedule_update(timedelta())

    return True
