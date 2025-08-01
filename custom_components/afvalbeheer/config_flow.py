import logging
import voluptuous as vol
import uuid
import json
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from .const import (
    DOMAIN, CONF_ID, CONF_WASTE_COLLECTOR, CONF_POSTCODE, CONF_STREET_NUMBER, CONF_SUFFIX,
    CONF_RESOURCES, CONF_NAME_PREFIX, CONF_DATE_FORMAT, CONF_UPCOMING, CONF_DATE_ONLY,
    CONF_DATE_OBJECT, CONF_BUILT_IN_ICONS, CONF_BUILT_IN_ICONS_NEW, CONF_DISABLE_ICONS,
    CONF_TRANSLATE_DAYS, CONF_DAY_OF_WEEK, CONF_DAY_OF_WEEK_ONLY, CONF_ALWAYS_SHOW_DAY,
    CONF_STREET_NAME, CONF_CITY_NAME, CONF_ADDRESS_ID, CONF_CUSTOMER_ID, CONF_UPDATE_INTERVAL,
    CONF_CUSTOM_MAPPING, DEFAULT_CONFIG, XIMMIO_COLLECTOR_IDS
)

_LOGGER = logging.getLogger(__name__)

WASTE_COLLECTORS = [
    "ACV", "Afval3xBeter", "Afvalstoffendienstkalender", "AfvalAlert",
    "Almere", "AlphenAanDenRijn", "AreaReiniging", "Assen", "Avalex", "Avri", "BAR",
    "Berkelland", "Blink", "Circulus", "Cleanprofs", "Cranendonck",
    "Cyclus", "DAR", "DeAfvalApp", "DeFryskeMarren", "DenHaag", "Drimmelen", "GAD",
    "Groningen", "Hellendoorn", "HVC", "Limburg.NET", "Lingewaard", "Meerlanden",
    "Middelburg-Vlissingen", "MijnAfvalwijzer", "Mijnafvalzaken", "Montferland",
    "Montfoort", "Omrin", "PeelEnMaas", "PreZero", "Purmerend",
    "RAD", "RecycleApp", "RD4", "RWM", "Reinis", "ROVA", "RMN", "Saver",
    "Schouwen-Duiveland", "Sliedrecht", "Spaarnelanden", "SudwestFryslan",
    "TwenteMilieu", "Venray", "Voorschoten", "Waalre", "Waardlanden", "Westland",
    "Woerden", "ZRD"
]


class AfvalbeheerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    
    VERSION = 3  # Increment this when config structure changes  
    MINOR_VERSION = 1
    

    async def async_step_import(self, import_config):
        """Import a config entry from YAML configuration."""
        _LOGGER.warning("=== YAML IMPORT STARTED ===")
        _LOGGER.warning("Importing YAML configuration for %s", import_config.get(CONF_WASTE_COLLECTOR))
        
        # Check existing config entries
        existing_entries = self._async_current_entries()
        _LOGGER.warning("Found %d existing config entries", len(existing_entries))
        for entry in existing_entries:
            _LOGGER.warning("Existing entry: %s (version %s.%s)", 
                          entry.title, entry.version, entry.minor_version)
        
        # Create a unique entry title
        title = f"{import_config.get(CONF_WASTE_COLLECTOR)} (Imported from YAML)"
        
        # Check if this config already exists
        for entry in self._async_current_entries():
            existing_config = {**entry.data, **entry.options}
            if (existing_config.get(CONF_WASTE_COLLECTOR) == import_config.get(CONF_WASTE_COLLECTOR) and
                existing_config.get(CONF_POSTCODE) == import_config.get(CONF_POSTCODE) and
                existing_config.get(CONF_STREET_NUMBER) == import_config.get(CONF_STREET_NUMBER)):
                _LOGGER.info("Configuration already exists for %s at %s %s, skipping import", 
                           import_config.get(CONF_WASTE_COLLECTOR),
                           import_config.get(CONF_POSTCODE),
                           import_config.get(CONF_STREET_NUMBER))
                return self.async_abort(reason="already_configured")
        
        # Convert YAML config to config flow format
        config_data = {}
        
        # Required fields
        config_data[CONF_WASTE_COLLECTOR] = import_config[CONF_WASTE_COLLECTOR]
        config_data[CONF_POSTCODE] = import_config[CONF_POSTCODE]
        config_data[CONF_STREET_NUMBER] = str(import_config[CONF_STREET_NUMBER])
        
        # Handle case-insensitive resource matching
        yaml_resources = import_config[CONF_RESOURCES]
        try:
            # Try to get available resources to match against
            temp_config = {
                CONF_WASTE_COLLECTOR: import_config[CONF_WASTE_COLLECTOR],
                CONF_POSTCODE: import_config[CONF_POSTCODE],
                CONF_STREET_NUMBER: str(import_config[CONF_STREET_NUMBER]),
                CONF_SUFFIX: import_config.get(CONF_SUFFIX, ""),
                CONF_CITY_NAME: import_config.get(CONF_CITY_NAME, ""),
                CONF_STREET_NAME: import_config.get(CONF_STREET_NAME, ""),
                CONF_RESOURCES: ["restafval"],  # Dummy resource for API call
            }
            
            from .API import get_wastedata_from_config
            data = get_wastedata_from_config(self.hass, temp_config)
            if data and hasattr(data, 'collections'):
                # Get available resources from API
                available_resources = data.collections.get_available_waste_types()
                if available_resources:
                    # Create case-insensitive mapping
                    resource_mapping = {res.lower(): res for res in available_resources}
                    
                    # Map YAML resources to correct case
                    matched_resources = []
                    for yaml_res in yaml_resources:
                        yaml_res_lower = yaml_res.lower()
                        if yaml_res_lower in resource_mapping:
                            matched_resources.append(resource_mapping[yaml_res_lower])
                        else:
                            # Keep original if no match found
                            matched_resources.append(yaml_res)
                    
                    config_data[CONF_RESOURCES] = matched_resources
                    _LOGGER.info("Mapped YAML resources %s to API resources %s", yaml_resources, matched_resources)
                else:
                    config_data[CONF_RESOURCES] = yaml_resources
            else:
                config_data[CONF_RESOURCES] = yaml_resources
        except Exception as e:
            _LOGGER.warning("Could not fetch resources for case matching during import: %s", e)
            config_data[CONF_RESOURCES] = yaml_resources
        
        # Optional fields with defaults
        config_data[CONF_SUFFIX] = import_config.get(CONF_SUFFIX, DEFAULT_CONFIG[CONF_SUFFIX])
        config_data[CONF_CITY_NAME] = import_config.get(CONF_CITY_NAME, "")
        config_data[CONF_STREET_NAME] = import_config.get(CONF_STREET_NAME, "")
        config_data[CONF_NAME] = import_config.get(CONF_NAME, DEFAULT_CONFIG[CONF_NAME])
        config_data[CONF_NAME_PREFIX] = import_config.get(CONF_NAME_PREFIX, DEFAULT_CONFIG[CONF_NAME_PREFIX])
        config_data[CONF_DATE_FORMAT] = import_config.get(CONF_DATE_FORMAT, DEFAULT_CONFIG[CONF_DATE_FORMAT])
        config_data[CONF_UPCOMING] = import_config.get(CONF_UPCOMING, DEFAULT_CONFIG[CONF_UPCOMING])
        config_data[CONF_DATE_ONLY] = import_config.get(CONF_DATE_ONLY, DEFAULT_CONFIG[CONF_DATE_ONLY])
        config_data[CONF_DATE_OBJECT] = import_config.get(CONF_DATE_OBJECT, DEFAULT_CONFIG[CONF_DATE_OBJECT])
        config_data[CONF_BUILT_IN_ICONS] = import_config.get(CONF_BUILT_IN_ICONS, DEFAULT_CONFIG[CONF_BUILT_IN_ICONS])
        config_data[CONF_BUILT_IN_ICONS_NEW] = import_config.get(CONF_BUILT_IN_ICONS_NEW, DEFAULT_CONFIG[CONF_BUILT_IN_ICONS_NEW])
        config_data[CONF_DISABLE_ICONS] = import_config.get(CONF_DISABLE_ICONS, DEFAULT_CONFIG[CONF_DISABLE_ICONS])
        config_data[CONF_TRANSLATE_DAYS] = import_config.get(CONF_TRANSLATE_DAYS, DEFAULT_CONFIG[CONF_TRANSLATE_DAYS])
        config_data[CONF_DAY_OF_WEEK] = import_config.get(CONF_DAY_OF_WEEK, DEFAULT_CONFIG[CONF_DAY_OF_WEEK])
        config_data[CONF_DAY_OF_WEEK_ONLY] = import_config.get(CONF_DAY_OF_WEEK_ONLY, DEFAULT_CONFIG[CONF_DAY_OF_WEEK_ONLY])
        config_data[CONF_ALWAYS_SHOW_DAY] = import_config.get(CONF_ALWAYS_SHOW_DAY, DEFAULT_CONFIG[CONF_ALWAYS_SHOW_DAY])
        
        # Advanced options
        config_data[CONF_ADDRESS_ID] = import_config.get(CONF_ADDRESS_ID, DEFAULT_CONFIG[CONF_ADDRESS_ID])
        config_data[CONF_CUSTOMER_ID] = import_config.get(CONF_CUSTOMER_ID, DEFAULT_CONFIG[CONF_CUSTOMER_ID])
        config_data[CONF_UPDATE_INTERVAL] = import_config.get(CONF_UPDATE_INTERVAL, DEFAULT_CONFIG[CONF_UPDATE_INTERVAL])
        config_data[CONF_CUSTOM_MAPPING] = import_config.get(CONF_CUSTOM_MAPPING, DEFAULT_CONFIG[CONF_CUSTOM_MAPPING])
        
        # Generate unique ID for this configuration entry
        config_data[CONF_ID] = str(uuid.uuid4())
        
        # Clean up old YAML entities before creating new config entry
        await self._cleanup_yaml_entities(import_config)
        
        _LOGGER.warning("Creating config entry with data: postcode=%s, street_number=%s", 
                       config_data.get(CONF_POSTCODE), config_data.get(CONF_STREET_NUMBER))
        
        return self.async_create_entry(title=title, data=config_data)
    
    async def _cleanup_yaml_entities(self, import_config):
        """Remove old YAML entities that don't have a config_entry_id."""
        from homeassistant.helpers import entity_registry as er
        
        entity_registry = er.async_get(self.hass)
        waste_collector = import_config.get(CONF_WASTE_COLLECTOR, "").lower()
        resources = import_config.get(CONF_RESOURCES, [])
        
        _LOGGER.info("Cleaning up old YAML entities for waste collector: %s", waste_collector)
        
        entities_to_remove = []
        
        # Find entities that likely belong to this YAML config but have no config_entry_id
        for entity in entity_registry.entities.values():
            if (entity.domain == "sensor" and 
                entity.platform == DOMAIN and 
                entity.config_entry_id is None):  # Pure YAML entities have no config_entry_id
                
                entity_name = entity.entity_id.replace("sensor.", "")
                
                # Check if entity matches this waste collector's resources
                matches_collector = waste_collector in entity_name.lower()
                matches_resource = any(resource.lower() in entity_name.lower() for resource in resources)
                matches_upcoming = any(keyword in entity_name.lower() for keyword in 
                                     ["today", "tomorrow", "vandaag", "morgen", "eerstvolgende", "first", "upcoming"])
                
                if matches_collector or matches_resource or matches_upcoming:
                    entities_to_remove.append(entity.entity_id)
                    _LOGGER.info("Found YAML entity to remove: %s (unique_id: %s)", 
                               entity.entity_id, entity.unique_id)
        
        # Remove the old YAML entities
        removed_count = 0
        for entity_id in entities_to_remove:
            try:
                _LOGGER.info("Removing YAML entity: %s", entity_id)
                entity_registry.async_remove(entity_id)
                removed_count += 1
            except Exception as e:
                _LOGGER.error("Failed to remove YAML entity %s: %s", entity_id, e)
        
        # Force registry save to ensure entities are fully removed
        if removed_count > 0:
            _LOGGER.info("Forcing entity registry save to ensure cleanup")
            try:
                # Force the registry to save and clear its cache
                await entity_registry.async_load()
                # Small delay to ensure registry is updated
                import asyncio
                await asyncio.sleep(0.1)
            except Exception as e:
                _LOGGER.warning("Could not force registry update: %s", e)
        
        _LOGGER.info("YAML cleanup completed. Removed %d entities", removed_count)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._collector = user_input[CONF_WASTE_COLLECTOR]
            return await self.async_step_address()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_WASTE_COLLECTOR, default=""): vol.In(WASTE_COLLECTORS),
            }),
            errors=errors,
        )

    async def async_step_address(self, user_input=None):
        errors = {}
        collector = getattr(self, "_collector", "")
        collector_lower = collector.lower()
        show_city = collector_lower == "limburg.net"
        show_street = collector_lower in ["limburg.net", "recycleapp"]

        schema_dict = {
            vol.Required(CONF_POSTCODE): str,
            vol.Required(CONF_STREET_NUMBER): str,
            vol.Optional(CONF_SUFFIX, default=DEFAULT_CONFIG[CONF_SUFFIX]): str,
        }
        if show_city:
            schema_dict[vol.Required(CONF_CITY_NAME)] = str
        if show_street:
            schema_dict[vol.Required(CONF_STREET_NAME)] = str

        if user_input is not None:
            self._address_input = {CONF_WASTE_COLLECTOR: self._collector, **user_input}
            return await self.async_step_resources()
        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_resources(self, user_input=None):
        errors = {}
        address = self._address_input
        result = await self._async_get_available_resources(address)
        
        if result["error"]:
            error_map = {
                "import_failed": "import_error",
                "no_data": "connection_error", 
                "invalid_data": "invalid_collector",
                "no_resources": "no_resources",
                "api_error": "connection_error"
            }
            errors["base"] = error_map.get(result["error"], "unknown_error")
        
        available_resources = result["resources"]
        collector_lower = address[CONF_WASTE_COLLECTOR].lower()
        is_ximmio_collector = collector_lower in XIMMIO_COLLECTOR_IDS
        
        if user_input is not None:
            # Validate and parse custom mapping JSON
            if CONF_CUSTOM_MAPPING in user_input:
                try:
                    mapping_str = user_input[CONF_CUSTOM_MAPPING].strip()
                    if mapping_str == "":
                        user_input[CONF_CUSTOM_MAPPING] = {}
                    else:
                        user_input[CONF_CUSTOM_MAPPING] = json.loads(mapping_str)
                except json.JSONDecodeError:
                    errors["base"] = "invalid_custom_mapping"
                    return self.async_show_form(
                        step_id="resources",
                        data_schema=vol.Schema(schema_dict),
                        errors=errors,
                    )
            
            if not errors:
                data = {**self._address_input, **user_input}
                # Generate unique ID for this configuration entry
                data[CONF_ID] = str(uuid.uuid4())
                return self.async_create_entry(
                    title=data.get(CONF_NAME) or data[CONF_WASTE_COLLECTOR],
                    data=data,
                )
        
        # Build schema with conditional fields
        schema_dict = {
            vol.Required(CONF_RESOURCES, default=available_resources): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=available_resources,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_CONFIG[CONF_NAME]): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT
                )
            ),
            vol.Optional(CONF_NAME_PREFIX, default=DEFAULT_CONFIG[CONF_NAME_PREFIX]): selector.BooleanSelector(),
        }
        
        # Date and time settings
        schema_dict.update({
            vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_CONFIG[CONF_DATE_FORMAT]): selector.TextSelector(),
            vol.Optional(CONF_UPCOMING, default=DEFAULT_CONFIG[CONF_UPCOMING]): selector.BooleanSelector(),
            vol.Optional(CONF_DATE_ONLY, default=DEFAULT_CONFIG[CONF_DATE_ONLY]): selector.BooleanSelector(),
            vol.Optional(CONF_DATE_OBJECT, default=DEFAULT_CONFIG[CONF_DATE_OBJECT]): selector.BooleanSelector(),
            vol.Optional(CONF_TRANSLATE_DAYS, default=DEFAULT_CONFIG[CONF_TRANSLATE_DAYS]): selector.BooleanSelector(),
            vol.Optional(CONF_DAY_OF_WEEK, default=DEFAULT_CONFIG[CONF_DAY_OF_WEEK]): selector.BooleanSelector(),
            vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=DEFAULT_CONFIG[CONF_DAY_OF_WEEK_ONLY]): selector.BooleanSelector(),
            vol.Optional(CONF_ALWAYS_SHOW_DAY, default=DEFAULT_CONFIG[CONF_ALWAYS_SHOW_DAY]): selector.BooleanSelector(),
        })
        
        # Icon settings
        schema_dict.update({
            vol.Optional(CONF_BUILT_IN_ICONS, default=DEFAULT_CONFIG[CONF_BUILT_IN_ICONS]): selector.BooleanSelector(),
            vol.Optional(CONF_BUILT_IN_ICONS_NEW, default=DEFAULT_CONFIG[CONF_BUILT_IN_ICONS_NEW]): selector.BooleanSelector(),
            vol.Optional(CONF_DISABLE_ICONS, default=DEFAULT_CONFIG[CONF_DISABLE_ICONS]): selector.BooleanSelector(),
        })
        
        # Advanced settings
        schema_dict.update({
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_CONFIG[CONF_UPDATE_INTERVAL]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=168,  # Max 1 week in hours
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="hours"
                )
            ),
        })
        
        # Add Ximmio-specific fields conditionally
        if is_ximmio_collector:
            schema_dict.update({
                vol.Optional(CONF_ADDRESS_ID, default=DEFAULT_CONFIG[CONF_ADDRESS_ID]): selector.TextSelector(),
                vol.Optional(CONF_CUSTOMER_ID, default=DEFAULT_CONFIG[CONF_CUSTOMER_ID]): selector.TextSelector(),
            })
        
        # Custom mapping - show as textarea for JSON input
        schema_dict[vol.Optional(CONF_CUSTOM_MAPPING, default="{}")] = selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=True,
                type=selector.TextSelectorType.TEXT
            )
        )
        
        return self.async_show_form(
            step_id="resources",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def _async_get_available_resources(self, address):        
        try:
            from .API import get_wastedata_from_config
        except ImportError as e:
            _LOGGER.error("Failed to import API module: %s", e)
            return {"error": "import_failed", "resources": []}

        config = {
            CONF_WASTE_COLLECTOR: address[CONF_WASTE_COLLECTOR],
            CONF_POSTCODE: address[CONF_POSTCODE],
            CONF_STREET_NUMBER: address[CONF_STREET_NUMBER],
            CONF_SUFFIX: address.get(CONF_SUFFIX, ""),
            CONF_RESOURCES: ["restafval"],
        }
        collector_lower = address[CONF_WASTE_COLLECTOR].lower()
        if collector_lower == "limburg.net":
            config[CONF_CITY_NAME] = address.get(CONF_CITY_NAME, "")
        if collector_lower in ["limburg.net", "recycleapp"]:
            config[CONF_STREET_NAME] = address.get(CONF_STREET_NAME, "")
        
        try:
            data = await self.hass.async_add_executor_job(get_wastedata_from_config, self.hass, config)
            if not data:
                _LOGGER.warning("No data returned from waste collector API for %s", address[CONF_WASTE_COLLECTOR])
                return {"error": "no_data", "resources": []}
            if not hasattr(data, "collections"):
                _LOGGER.warning("Data object missing collections attribute for %s", address[CONF_WASTE_COLLECTOR])
                return {"error": "invalid_data", "resources": []}
            
            await data.async_update()
            resources = data.collections.get_available_waste_types()
            if not resources:
                _LOGGER.warning("No waste types found for %s at %s %s", 
                              address[CONF_WASTE_COLLECTOR], address[CONF_POSTCODE], address[CONF_STREET_NUMBER])
                return {"error": "no_resources", "resources": []}
            
            _LOGGER.debug("Found %d waste types for %s: %s", len(resources), address[CONF_WASTE_COLLECTOR], resources)
            return {"error": None, "resources": resources}
            
        except Exception as e:
            _LOGGER.error("Error fetching waste types for %s: %s", address[CONF_WASTE_COLLECTOR], e)
            return {"error": "api_error", "resources": []}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AfvalbeheerOptionsFlowHandler(config_entry)


class AfvalbeheerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._collector = None
        self._address_input = {}

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self._collector = user_input[CONF_WASTE_COLLECTOR]
            return await self.async_step_address()

        # Get current collector and find case-insensitive match
        current_collector = self.config_entry.data.get(CONF_WASTE_COLLECTOR, "")
        default_collector = current_collector
        
        # Find case-insensitive match in WASTE_COLLECTORS
        if current_collector:
            current_lower = current_collector.lower()
            for collector in WASTE_COLLECTORS:
                if collector.lower() == current_lower:
                    default_collector = collector
                    break

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_WASTE_COLLECTOR, default=default_collector): vol.In(WASTE_COLLECTORS),
            }),
        )

    async def async_step_address(self, user_input=None):
        collector = self._collector
        collector_lower = collector.lower()
        show_city = collector_lower == "limburg.net"
        show_street = collector_lower in ["limburg.net", "recycleapp"]

        # Combine current data and options to get all current values
        current = {**self.config_entry.data, **self.config_entry.options}

        schema_dict = {
            vol.Required(CONF_POSTCODE, default=current.get(CONF_POSTCODE)): str,
            vol.Required(CONF_STREET_NUMBER, default=current.get(CONF_STREET_NUMBER)): str,
            vol.Optional(CONF_SUFFIX, default=current.get(CONF_SUFFIX, DEFAULT_CONFIG[CONF_SUFFIX])): str,
        }
        if show_city:
            schema_dict[vol.Required(CONF_CITY_NAME, default=current.get(CONF_CITY_NAME, ""))] = str
        if show_street:
            schema_dict[vol.Required(CONF_STREET_NAME, default=current.get(CONF_STREET_NAME, ""))] = str

        if user_input is not None:
            self._address_input = {CONF_WASTE_COLLECTOR: self._collector, **user_input}
            return await self.async_step_resources()

        return self.async_show_form(step_id="address", data_schema=vol.Schema(schema_dict))

    async def async_step_resources(self, user_input=None):
        errors = {}
        # Create a temporary instance to access the shared helper method
        temp_flow = AfvalbeheerConfigFlow()
        temp_flow.hass = self.hass
        result = await temp_flow._async_get_available_resources(self._address_input)
        
        if result["error"]:
            error_map = {
                "import_failed": "import_error",
                "no_data": "connection_error", 
                "invalid_data": "invalid_collector",
                "no_resources": "no_resources",
                "api_error": "connection_error"
            }
            errors["base"] = error_map.get(result["error"], "unknown_error")
        
        available_resources = result["resources"]
        current = {**self.config_entry.data, **self.config_entry.options}
        collector_lower = self._address_input[CONF_WASTE_COLLECTOR].lower()
        is_ximmio_collector = collector_lower in XIMMIO_COLLECTOR_IDS
        
        # Handle case-insensitive resource matching for current resources
        current_resources = current.get(CONF_RESOURCES, [])
        if available_resources and current_resources:
            # Create case-insensitive mapping
            resource_mapping = {res.lower(): res for res in available_resources}
            
            # Map current resources to correct case
            matched_resources = []
            for current_res in current_resources:
                current_res_lower = current_res.lower()
                if current_res_lower in resource_mapping:
                    matched_resources.append(resource_mapping[current_res_lower])
                else:
                    # Keep original if no match found
                    matched_resources.append(current_res)
            
            current[CONF_RESOURCES] = matched_resources

        if user_input is not None:
            # Validate and parse custom mapping JSON
            if CONF_CUSTOM_MAPPING in user_input:
                try:
                    mapping_str = user_input[CONF_CUSTOM_MAPPING].strip()
                    if mapping_str == "":
                        user_input[CONF_CUSTOM_MAPPING] = {}
                    else:
                        user_input[CONF_CUSTOM_MAPPING] = json.loads(mapping_str)
                except json.JSONDecodeError:
                    errors["base"] = "invalid_custom_mapping"
                    
            if not errors:
                data = {**self._address_input, **user_input}
                return self.async_create_entry(title="", data=data)

        # Build schema with conditional fields
        schema_dict = {
            vol.Required(CONF_RESOURCES, default=current.get(CONF_RESOURCES, available_resources)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=available_resources,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_CONFIG[CONF_NAME])): selector.TextSelector(),
            vol.Optional(CONF_NAME_PREFIX, default=current.get(CONF_NAME_PREFIX, DEFAULT_CONFIG[CONF_NAME_PREFIX])): selector.BooleanSelector(),
        }
        
        # Date and time settings
        schema_dict.update({
            vol.Optional(CONF_DATE_FORMAT, default=current.get(CONF_DATE_FORMAT, DEFAULT_CONFIG[CONF_DATE_FORMAT])): selector.TextSelector(),
            vol.Optional(CONF_UPCOMING, default=current.get(CONF_UPCOMING, DEFAULT_CONFIG[CONF_UPCOMING])): selector.BooleanSelector(),
            vol.Optional(CONF_DATE_ONLY, default=current.get(CONF_DATE_ONLY, DEFAULT_CONFIG[CONF_DATE_ONLY])): selector.BooleanSelector(),
            vol.Optional(CONF_DATE_OBJECT, default=current.get(CONF_DATE_OBJECT, DEFAULT_CONFIG[CONF_DATE_OBJECT])): selector.BooleanSelector(),
            vol.Optional(CONF_TRANSLATE_DAYS, default=current.get(CONF_TRANSLATE_DAYS, DEFAULT_CONFIG[CONF_TRANSLATE_DAYS])): selector.BooleanSelector(),
            vol.Optional(CONF_DAY_OF_WEEK, default=current.get(CONF_DAY_OF_WEEK, DEFAULT_CONFIG[CONF_DAY_OF_WEEK])): selector.BooleanSelector(),
            vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=current.get(CONF_DAY_OF_WEEK_ONLY, DEFAULT_CONFIG[CONF_DAY_OF_WEEK_ONLY])): selector.BooleanSelector(),
            vol.Optional(CONF_ALWAYS_SHOW_DAY, default=current.get(CONF_ALWAYS_SHOW_DAY, DEFAULT_CONFIG[CONF_ALWAYS_SHOW_DAY])): selector.BooleanSelector(),
        })
        
        # Icon settings
        schema_dict.update({
            vol.Optional(CONF_BUILT_IN_ICONS, default=current.get(CONF_BUILT_IN_ICONS, DEFAULT_CONFIG[CONF_BUILT_IN_ICONS])): selector.BooleanSelector(),
            vol.Optional(CONF_BUILT_IN_ICONS_NEW, default=current.get(CONF_BUILT_IN_ICONS_NEW, DEFAULT_CONFIG[CONF_BUILT_IN_ICONS_NEW])): selector.BooleanSelector(),
            vol.Optional(CONF_DISABLE_ICONS, default=current.get(CONF_DISABLE_ICONS, DEFAULT_CONFIG[CONF_DISABLE_ICONS])): selector.BooleanSelector(),
        })
        
        # Advanced settings
        schema_dict.update({
            vol.Optional(CONF_UPDATE_INTERVAL, default=current.get(CONF_UPDATE_INTERVAL, DEFAULT_CONFIG[CONF_UPDATE_INTERVAL])): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=168,  # Max 1 week in hours
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="hours"
                )
            ),
        })
        
        # Add Ximmio-specific fields conditionally
        if is_ximmio_collector:
            schema_dict.update({
                vol.Optional(CONF_ADDRESS_ID, default=current.get(CONF_ADDRESS_ID, DEFAULT_CONFIG[CONF_ADDRESS_ID])): selector.TextSelector(),
                vol.Optional(CONF_CUSTOMER_ID, default=current.get(CONF_CUSTOMER_ID, DEFAULT_CONFIG[CONF_CUSTOMER_ID])): selector.TextSelector(),
            })
        
        # Custom mapping - show as textarea for JSON input
        current_mapping = current.get(CONF_CUSTOM_MAPPING, DEFAULT_CONFIG[CONF_CUSTOM_MAPPING])
        if isinstance(current_mapping, dict):
            current_mapping_str = json.dumps(current_mapping, indent=2) if current_mapping else "{}"
        else:
            current_mapping_str = str(current_mapping)
            
        schema_dict[vol.Optional(CONF_CUSTOM_MAPPING, default=current_mapping_str)] = selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=True,
                type=selector.TextSelectorType.TEXT
            )
        )

        return self.async_show_form(
            step_id="resources",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
