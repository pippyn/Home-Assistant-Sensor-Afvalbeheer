import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from .const import (
    DOMAIN, CONF_ID, CONF_WASTE_COLLECTOR, CONF_POSTCODE, CONF_STREET_NUMBER, CONF_SUFFIX,
    CONF_RESOURCES, CONF_NAME_PREFIX, CONF_DATE_FORMAT, CONF_UPCOMING, CONF_DATE_ONLY,
    CONF_DATE_OBJECT, CONF_BUILT_IN_ICONS, CONF_BUILT_IN_ICONS_NEW, CONF_DISABLE_ICONS,
    CONF_TRANSLATE_DAYS, CONF_DAY_OF_WEEK, CONF_DAY_OF_WEEK_ONLY, CONF_ALWAYS_SHOW_DAY,
    CONF_STREET_NAME, CONF_CITY_NAME
)
import homeassistant.helpers.config_validation as cv

WASTE_COLLECTORS = [
    "ACV", "Afval3xBeter", "Afvalstoffendienstkalender", "AfvalAlert",
    "Almere", "AlphenAanDenRijn", "AreaReiniging", "Assen", "Avalex", "Avri", "BAR",
    "Berkelland", "Blink", "Circulus", "Cleanprofs", "Cranendonck",
    "Cyclus", "DAR", "DeAfvalApp", "DeFryskeMarren", "DenHaag", "Drimmelen", "GAD",
    "Hellendoorn", "HVC", "Limburg.NET", "Lingewaard", "Meerlanden",
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
                vol.Required(CONF_WASTE_COLLECTOR, default="Blink"): vol.In(WASTE_COLLECTORS),
            }),
            errors=errors,
        )

    async def async_step_address(self, user_input=None):
        errors = {}
        collector = getattr(self, "_collector", "Blink")
        collector_lower = collector.lower()
        show_city = collector_lower == "limburg.net"
        show_street = collector_lower in ["limburg.net", "recycleapp"]

        schema_dict = {
            vol.Required(CONF_POSTCODE): str,
            vol.Required(CONF_STREET_NUMBER): str,
            vol.Optional(CONF_SUFFIX, default=""): str,
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
        available_resources = await self._async_get_available_resources(address)
        if not available_resources:
            errors["base"] = "no_resources"
            available_resources = []
        if user_input is not None:
            data = {**self._address_input, **user_input}
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
                vol.Optional(CONF_NAME, default=""): str,
                vol.Optional(CONF_NAME_PREFIX, default=True): cv.boolean,
                vol.Optional(CONF_DATE_FORMAT, default="%d-%m-%Y"): str,
                vol.Optional(CONF_UPCOMING, default=False): cv.boolean,
                vol.Optional(CONF_DATE_ONLY, default=False): cv.boolean,
                vol.Optional(CONF_DATE_OBJECT, default=False): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS, default=False): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS_NEW, default=False): cv.boolean,
                vol.Optional(CONF_DISABLE_ICONS, default=False): cv.boolean,
                vol.Optional(CONF_TRANSLATE_DAYS, default=False): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK, default=True): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=False): cv.boolean,
                vol.Optional(CONF_ALWAYS_SHOW_DAY, default=False): cv.boolean,
            }),
            errors=errors,
        )

    async def _async_get_available_resources(self, address):
        try:
            from .API import get_wastedata_from_config
        except ImportError:
            return []

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
            if not data or not hasattr(data, "collections"):
                return []
            await data.async_update()
            resources = data.collections.get_available_waste_types()
            return resources
        except Exception:
            return []

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
            vol.Optional(CONF_SUFFIX, default=current.get(CONF_SUFFIX, "")): str,
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
        available_resources = await AfvalbeheerConfigFlow._async_get_available_resources(self, self._address_input)
        if not available_resources:
            available_resources = []

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
                vol.Optional(CONF_NAME, default=current.get(CONF_NAME, "")): str,
                vol.Optional(CONF_NAME_PREFIX, default=current.get(CONF_NAME_PREFIX, True)): cv.boolean,
                vol.Optional(CONF_DATE_FORMAT, default=current.get(CONF_DATE_FORMAT, "%d-%m-%Y")): str,
                vol.Optional(CONF_UPCOMING, default=current.get(CONF_UPCOMING, False)): cv.boolean,
                vol.Optional(CONF_DATE_ONLY, default=current.get(CONF_DATE_ONLY, False)): cv.boolean,
                vol.Optional(CONF_DATE_OBJECT, default=current.get(CONF_DATE_OBJECT, False)): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS, default=current.get(CONF_BUILT_IN_ICONS, False)): cv.boolean,
                vol.Optional(CONF_BUILT_IN_ICONS_NEW, default=current.get(CONF_BUILT_IN_ICONS_NEW, False)): cv.boolean,
                vol.Optional(CONF_DISABLE_ICONS, default=current.get(CONF_DISABLE_ICONS, False)): cv.boolean,
                vol.Optional(CONF_TRANSLATE_DAYS, default=current.get(CONF_TRANSLATE_DAYS, False)): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK, default=current.get(CONF_DAY_OF_WEEK, True)): cv.boolean,
                vol.Optional(CONF_DAY_OF_WEEK_ONLY, default=current.get(CONF_DAY_OF_WEEK_ONLY, False)): cv.boolean,
                vol.Optional(CONF_ALWAYS_SHOW_DAY, default=current.get(CONF_ALWAYS_SHOW_DAY, False)): cv.boolean,
            }),
        )
