import logging
from datetime import datetime
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_RESOURCES, Platform

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import *
from .API import Get_WasteData_From_Config


__version__ = '4.9.6'


_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_RESOURCES, default=[]): cv.ensure_list,
                vol.Required(CONF_POSTCODE, default="1111AA"): cv.string,
                vol.Required(CONF_STREET_NUMBER, default="1"): cv.string,
                vol.Optional(CONF_CITY_NAME, default=""): cv.string,
                vol.Optional(CONF_STREET_NAME, default=""): cv.string,
                vol.Optional(CONF_SUFFIX, default=""): cv.string,
                vol.Optional(CONF_ADDRESS_ID, default=""): cv.string,
                vol.Optional(CONF_WASTE_COLLECTOR, default="Cure"): cv.string,
                vol.Optional(CONF_DATE_FORMAT, default="%d-%m-%Y"): cv.string,
                vol.Optional(CONF_TODAY_TOMORROW, default=False): cv.boolean,
                vol.Optional(CONF_DATE_ONLY, default=False): cv.boolean,
                vol.Optional(CONF_DATE_OBJECT, default=False): cv.boolean,
                vol.Optional(CONF_NAME, default=""): cv.string,
                vol.Optional(CONF_NAME_PREFIX, default=True): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS, default=False): cv.boolean,
                vol.Optional(CONF_DISABLE_ICONS, default=False): cv.boolean,
                vol.Optional(CONF_TRANSLATE_DAYS, default=False): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK, default=True): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=False): cv.boolean,
                vol.Optional(CONF_ALWAYS_SHOW_DAY, default=False): cv.boolean,
                vol.Optional(
                    CONF_PRINT_AVAILABLE_WASTE_TYPES, default=False
                ): cv.boolean,
                vol.Optional(CONF_UPDATE_INTERVAL, default=0): cv.positive_int,
                vol.Optional(CONF_CUSTOMER_ID, default=""): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.debug("Setup of Afvalbeheer component Rest API retriever")

    conf = config[DOMAIN]

    data = Get_WasteData_From_Config(hass, conf)

    hass.data.setdefault(DOMAIN, {})[conf["id"]] = data

    await hass.helpers.discovery.async_load_platform(
        Platform.SENSOR, DOMAIN, {"config": conf}, config
    )

    # if you add boolean to config you could disable calendar entities from here
    hass.helpers.discovery.load_platform(
        Platform.CALENDAR, DOMAIN, {"config": conf}, config
    )

    await data.schedule_update(timedelta())

    return True

