import logging
import voluptuous as vol
import uuid
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from .const import (
    DOMAIN, CONF_ID, CONF_WASTE_COLLECTOR, CONF_POSTCODE, CONF_STREET_NUMBER, CONF_SUFFIX,
    CONF_RESOURCES, CONF_NAME_PREFIX, CONF_DATE_FORMAT, CONF_UPCOMING, CONF_DATE_ONLY,
    CONF_DATE_OBJECT, CONF_BUILT_IN_ICONS, CONF_BUILT_IN_ICONS_NEW, CONF_DISABLE_ICONS,
    CONF_TRANSLATE_DAYS, CONF_DAY_OF_WEEK, CONF_DAY_OF_WEEK_ONLY, CONF_ALWAYS_SHOW_DAY,
    CONF_STREET_NAME, CONF_CITY_NAME, DEFAULT_CONFIG
)
import homeassistant.helpers.config_validation as cv

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
        if user_input is not None:
            data = {**self._address_input, **user_input}
            # Generate unique ID for this configuration entry
            data[CONF_ID] = str(uuid.uuid4())
            return self.async_create_entry(
                title=data.get(CONF_NAME) or data[CONF_WASTE_COLLECTOR],
                data=data,
            )
        return self.async_show_form(
            step_id="resources",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_RESOURCES,
                    default=available_resources
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_resources,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_NAME, default=DEFAULT_CONFIG[CONF_NAME]): str,
                vol.Optional(CONF_NAME_PREFIX, default=DEFAULT_CONFIG[CONF_NAME_PREFIX]): cv.boolean,
                vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_CONFIG[CONF_DATE_FORMAT]): str,
                vol.Optional(CONF_UPCOMING, default=DEFAULT_CONFIG[CONF_UPCOMING]): cv.boolean,
                vol.Optional(CONF_DATE_ONLY, default=DEFAULT_CONFIG[CONF_DATE_ONLY]): cv.boolean,
                vol.Optional(CONF_DATE_OBJECT, default=DEFAULT_CONFIG[CONF_DATE_OBJECT]): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS, default=DEFAULT_CONFIG[CONF_BUILT_IN_ICONS]): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS_NEW, default=DEFAULT_CONFIG[CONF_BUILT_IN_ICONS_NEW]): cv.boolean,
                vol.Optional(CONF_DISABLE_ICONS, default=DEFAULT_CONFIG[CONF_DISABLE_ICONS]): cv.boolean,
                vol.Optional(CONF_TRANSLATE_DAYS, default=DEFAULT_CONFIG[CONF_TRANSLATE_DAYS]): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK, default=DEFAULT_CONFIG[CONF_DAY_OF_WEEK]): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=DEFAULT_CONFIG[CONF_DAY_OF_WEEK_ONLY]): cv.boolean,
                vol.Optional(CONF_ALWAYS_SHOW_DAY, default=DEFAULT_CONFIG[CONF_ALWAYS_SHOW_DAY]): cv.boolean,
            }),
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

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_WASTE_COLLECTOR, default=self.config_entry.data.get(CONF_WASTE_COLLECTOR)): vol.In(WASTE_COLLECTORS),
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

        if user_input is not None:
            data = {**self._address_input, **user_input}
            return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="resources",
            data_schema=vol.Schema({
                vol.Required(CONF_RESOURCES, default=current.get(CONF_RESOURCES, available_resources)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_resources,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_CONFIG[CONF_NAME])): str,
                vol.Optional(CONF_NAME_PREFIX, default=current.get(CONF_NAME_PREFIX, DEFAULT_CONFIG[CONF_NAME_PREFIX])): cv.boolean,
                vol.Optional(CONF_DATE_FORMAT, default=current.get(CONF_DATE_FORMAT, DEFAULT_CONFIG[CONF_DATE_FORMAT])): str,
                vol.Optional(CONF_UPCOMING, default=current.get(CONF_UPCOMING, DEFAULT_CONFIG[CONF_UPCOMING])): cv.boolean,
                vol.Optional(CONF_DATE_ONLY, default=current.get(CONF_DATE_ONLY, DEFAULT_CONFIG[CONF_DATE_ONLY])): cv.boolean,
                vol.Optional(CONF_DATE_OBJECT, default=current.get(CONF_DATE_OBJECT, DEFAULT_CONFIG[CONF_DATE_OBJECT])): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS, default=current.get(CONF_BUILT_IN_ICONS, DEFAULT_CONFIG[CONF_BUILT_IN_ICONS])): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS_NEW, default=current.get(CONF_BUILT_IN_ICONS_NEW, DEFAULT_CONFIG[CONF_BUILT_IN_ICONS_NEW])): cv.boolean,
                vol.Optional(CONF_DISABLE_ICONS, default=current.get(CONF_DISABLE_ICONS, DEFAULT_CONFIG[CONF_DISABLE_ICONS])): cv.boolean,
                vol.Optional(CONF_TRANSLATE_DAYS, default=current.get(CONF_TRANSLATE_DAYS, DEFAULT_CONFIG[CONF_TRANSLATE_DAYS])): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK, default=current.get(CONF_DAY_OF_WEEK, DEFAULT_CONFIG[CONF_DAY_OF_WEEK])): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=current.get(CONF_DAY_OF_WEEK_ONLY, DEFAULT_CONFIG[CONF_DAY_OF_WEEK_ONLY])): cv.boolean,
                vol.Optional(CONF_ALWAYS_SHOW_DAY, default=current.get(CONF_ALWAYS_SHOW_DAY, DEFAULT_CONFIG[CONF_ALWAYS_SHOW_DAY])): cv.boolean,
            }),
            errors=errors,
        )
