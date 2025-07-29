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
from homeassistant.components import persistent_notification

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID, NOTIFICATION_ID, CONF_WASTE_COLLECTOR
from .API import get_wastedata_from_config


__version__ = "6.0.0"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.debug("Setup of Afvalbeheer component Rest API retriever")

    yaml_config = config.get(DOMAIN, None)

    if yaml_config is None:
        return True

    if not isinstance(yaml_config, list):
        yaml_config = [yaml_config]

    # Import YAML configurations to config flow entries
    imported_configs = []
    for conf in yaml_config:
        collector_name = conf.get(CONF_WASTE_COLLECTOR, "Unknown")
        _LOGGER.info("Importing YAML configuration to config flow for %s", collector_name)
        imported_configs.append(collector_name)
        
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=conf,
            )
        )
    
    # Create notification to inform user about YAML import
    if imported_configs:
        notification_message = (
            f"**Afvalbeheer YAML Configuration Import**\n\n"
            f"Your YAML configuration for the following waste collectors has been automatically "
            f"imported to the new Config Flow system:\n\n"
            f"• {', '.join(imported_configs)}\n\n"
            f"**Next Steps:**\n"
            f"1. Go to **Settings > Devices & Services > Afvalbeheer** to manage your configurations\n"
            f"2. Verify the imported settings are correct\n"
            f"3. **Remove the YAML configuration from your `configuration.yaml` file** to avoid duplicates\n"
            f"4. Restart Home Assistant after removing the YAML configuration\n\n"
            f"The Config Flow system provides a better user experience and allows for easier management "
            f"of multiple waste collectors."
        )
        
        persistent_notification.async_create(
            hass,
            notification_message,
            title="Afvalbeheer: YAML Import Complete",
            notification_id=f"{NOTIFICATION_ID}_yaml_import"
        )
        
        _LOGGER.warning(
            "YAML configuration detected and imported to Config Flow. "
            "To avoid duplicate sensors, please remove the YAML configuration from configuration.yaml "
            "and restart Home Assistant."
        )

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
