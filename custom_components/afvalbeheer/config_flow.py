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
    CONF_CUSTOM_MAPPING,
)
import uuid
import homeassistant.helpers.config_validation as cv

# Minimal waste collectors and resources for dropdowns
WASTE_COLLECTORS = [
    "ACV", "Afval3xBeter", "Afvalstoffendienstkalender", "AfvalAlert", "Alkmaar",
    "Almere", "AlphenAanDenRijn", "AreaReiniging", "Assen", "Avalex", "Avri", "BAR",
    "Berkelland", "Blink", "Circulus", "Cleanprofs", "Cranendonck", "Cure",
    "Cyclus", "DAR", "DeAfvalApp", "DeFryskeMarren", "DenHaag", "Drimmelen", "GAD",
    "Hellendoorn", "HVC", "Limburg.NET", "Lingewaard", "Meerlanden", "Meppel",
    "Middelburg-Vlissingen", "MijnAfvalwijzer", "Mijnafvalzaken", "Montferland",
    "Montfoort", "Ôffalkalinder", "Omrin", "PeelEnMaas", "PreZero", "Purmerend",
    "RAD", "RecycleApp", "RD4", "RWM", "Reinis", "ROVA", "RMN", "Saver",
    "Schouwen-Duiveland", "Sliedrecht", "Spaarnelanden", "SudwestFryslan",
    "TwenteMilieu", "Venray", "Voorschoten", "Waalre", "Waardlanden", "Westland",
    "Woerden", "ZRD"
]

class AfvalbeheerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Save address info and go to resource selection
            self._address_input = user_input
            return await self.async_step_resources()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_WASTE_COLLECTOR, default="Blink"): vol.In(WASTE_COLLECTORS),
                vol.Required(CONF_POSTCODE): str,
                vol.Required(CONF_STREET_NUMBER): str,
                vol.Optional(CONF_SUFFIX, default=""): str,
            }),
            errors=errors,
        )

    async def async_step_resources(self, user_input=None):
        errors = {}
        address = self._address_input
        available_resources = await self._async_get_available_resources(address)
        if not available_resources:
            errors["base"] = "no_resources"
            available_resources = [
                "restafval", "gft", "papier", "pmd"
            ]
        if user_input is not None:
            # Save all config and finish
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
        # Import here to avoid circular import at HA startup
        try:
            from .API import get_wastedata_from_config
        except ImportError:
            return []
        # Prepare config dict for API
        config = {
            CONF_WASTE_COLLECTOR: address[CONF_WASTE_COLLECTOR],
            CONF_POSTCODE: address[CONF_POSTCODE],
            CONF_STREET_NUMBER: address[CONF_STREET_NUMBER],
            CONF_SUFFIX: address.get(CONF_SUFFIX, ""),
            CONF_RESOURCES: ["restafval"],  # dummy, required by schema
        }
        # Try to get available waste types (fractions) for this address
        try:
            # get_wastedata_from_config is sync, but may call async API, so run in executor
            data = await self.hass.async_add_executor_job(get_wastedata_from_config, self.hass, config)
            if not data or not hasattr(data, "collections"):
                return []
            # Wait for data to update (API call)
            await data.async_update()
            resources = data.collections.get_available_waste_types()
            return resources
        except Exception:
            return []

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry):
    #     # Prevent options flow from being available (disables "Reconfigure" in UI)
    #     return None
