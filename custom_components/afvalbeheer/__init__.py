"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 6.4.0 20251117
"""

import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import Platform

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components import persistent_notification

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID, NOTIFICATION_ID, CONF_WASTE_COLLECTOR
from .API import get_wastedata_from_config


__version__ = "6.4.0"

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


async def async_migrate_entry(hass, config_entry):
    """Migrate old config entries to new format."""
    _LOGGER.warning("=== MIGRATION FUNCTION CALLED ===")
    _LOGGER.warning("Migration check: config entry version %s.%s, current version %s.%s", 
                   config_entry.version, config_entry.minor_version, 3, 1)
    
    # For existing entries that might have the wrong unique ID format
    # Check if migration is needed based on entity unique IDs rather than just version
    needs_migration = _check_if_migration_needed(hass, config_entry)
    
    if config_entry.version < 3 or needs_migration:
        _LOGGER.warning("Migrating config entry from version %s.%s to %s.%s", 
                       config_entry.version, config_entry.minor_version, 3, 1)
        return await _migrate_entry_to_v3(hass, config_entry)
    
    _LOGGER.info("No migration needed for config entry %s", config_entry.title)
    return True


def _check_if_migration_needed(hass, config_entry):
    """Check if migration is needed by examining entity unique IDs."""
    from homeassistant.helpers import entity_registry as er
    
    try:
        entity_registry = er.async_get(hass)
        
        # Check if any entities for this config entry have old-style unique IDs
        for entity in entity_registry.entities.values():
            if (entity.domain == "sensor" and 
                entity.platform == DOMAIN and 
                entity.config_entry_id == config_entry.entry_id):
                
                # If unique_id starts with entry_id, it's old format
                if entity.unique_id and entity.unique_id.startswith(config_entry.entry_id):
                    _LOGGER.warning("Found entity with old unique_id format: %s", entity.unique_id)
                    return True
        
        return False
    except Exception as e:
        _LOGGER.error("Error checking migration need: %s", e)
        return False


async def _migrate_entry_to_v3(hass, config_entry):
    """Migrate to version 3 - update entity unique IDs to new consistent format."""
    from homeassistant.helpers import entity_registry as er
    from .const import CONF_WASTE_COLLECTOR, CONF_POSTCODE, CONF_STREET_NUMBER, CONF_NAME
    
    try:
        entity_registry = er.async_get(hass)
        config_data = {**config_entry.data, **config_entry.options}
        
        waste_collector = config_data.get(CONF_WASTE_COLLECTOR, "").lower()
        postcode = config_data.get(CONF_POSTCODE, "")
        street_number = str(config_data.get(CONF_STREET_NUMBER, ""))
        name = config_data.get(CONF_NAME, "")
        
        _LOGGER.info("Migrating entities for waste_collector=%s, postcode=%s, street_number=%s", 
                    waste_collector, postcode, street_number)
        
        migrated_count = 0
        
        # Find entities belonging to this config entry
        for entity in list(entity_registry.entities.values()):
            if (entity.domain == "sensor" and 
                entity.platform == DOMAIN and 
                entity.config_entry_id == config_entry.entry_id):
                
                # Determine the sensor type from the old unique_id or entity_id
                old_unique_id = entity.unique_id
                sensor_type = None
                
                # Try to extract sensor type from old unique_id patterns
                if old_unique_id:
                    # Handle old patterns like "entry_id_sensor_name" or just "sensor_name"
                    parts = old_unique_id.split("_")
                    sensor_type = parts[-1]  # Last part should be the sensor type
                
                if not sensor_type:
                    # Fallback: extract from entity_id
                    entity_name = entity.entity_id.replace("sensor.", "")
                    if "_" in entity_name:
                        sensor_type = entity_name.split("_")[-1]
                    else:
                        sensor_type = entity_name
                
                if sensor_type:
                    # Generate new unique_id using the consistent format
                    if not name:
                        # Simple format like YAML used: just the sensor type  
                        new_unique_id = sensor_type.lower()
                    else:
                        # If custom name is provided, include it for uniqueness
                        parts = [name, sensor_type]
                        new_unique_id = "_".join(parts).replace(" ", "_").replace("-", "_").lower()
                    
                    if new_unique_id != old_unique_id:
                        _LOGGER.info("Migrating entity %s: %s -> %s", 
                                   entity.entity_id, old_unique_id, new_unique_id)
                        
                        entity_registry.async_update_entity(
                            entity.entity_id,
                            new_unique_id=new_unique_id
                        )
                        migrated_count += 1
        
        _LOGGER.info("Migration completed. Updated %d entities.", migrated_count)
        
        # Update config entry version
        hass.config_entries.async_update_entry(
            config_entry,
            version=3,
            minor_version=1
        )
        
        return True
        
    except Exception as e:
        _LOGGER.error("Migration failed: %s", e)
        return False


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
