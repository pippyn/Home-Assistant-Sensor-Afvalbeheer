import logging
from datetime import timedelta

from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util
from homeassistant.components import persistent_notification

from .const import *
from .models import WasteCollectionRepository
from .collectors import (
    XimmioCollector, BurgerportaalCollector, OpzetCollector,
    AfvalAlertCollector, AfvalwijzerCollector, AmsterdamCollector, CirculusCollector, CleanprofsCollector,
    DeAfvalAppCollector, LimburgNetCollector, MontferlandNetCollector, OmrinCollector,
    RD4Collector, RecycleApp, ReinisCollector, ROVACollector, StraatbeeldCollector
)


_LOGGER = logging.getLogger(__name__)


class WasteData(object):
    """
    Manages waste data and schedules updates.
    """

    def __init__(self, hass, waste_collector, city_name, postcode, street_name, street_number, suffix, custom_mapping, address_id, print_waste_type, print_waste_type_slugs, update_interval, customer_id):
        self.hass = hass
        self.waste_collector = waste_collector
        self.city_name = city_name
        self.postcode = postcode
        self.street_name = street_name
        self.street_number = street_number
        self.suffix = suffix
        self.address_id = address_id
        self.print_waste_type = print_waste_type
        self.print_waste_type_slugs = print_waste_type_slugs
        self.collector = None
        self.update_interval = update_interval
        self.customer_id = customer_id
        self.custom_mapping = custom_mapping
        self.__select_collector()

    def __select_collector(self):
        _LOGGER.debug(f"Selecting collector for waste_collector: {self.waste_collector}")
        common_args = [self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix, self.custom_mapping]

        collector_mapping = {
            **{key: (XimmioCollector, common_args + [self.address_id, self.customer_id]) for key in XIMMIO_COLLECTOR_IDS.keys()},
            "mijnafvalwijzer": (AfvalwijzerCollector, common_args),
            "afvalstoffendienstkalender": (AfvalwijzerCollector, common_args),
            "afvalalert": (AfvalAlertCollector, common_args),
            "amsterdam": (AmsterdamCollector, common_args),
            "deafvalapp": (DeAfvalAppCollector, common_args),
            "circulus": (CirculusCollector, common_args),
            "limburg.net": (LimburgNetCollector, common_args + [self.street_name, self.city_name]),
            "montferland": (MontferlandNetCollector, common_args),
            "omrin": (OmrinCollector, common_args),
            "recycleapp": (RecycleApp, common_args + [self.street_name]),
            "reinis": (ReinisCollector, common_args),
            "rd4": (RD4Collector, common_args),
            "cleanprofs": (CleanprofsCollector, common_args),
            "rova": (ROVACollector, common_args),
            "drimmelen": (StraatbeeldCollector, common_args),
            **{key: (BurgerportaalCollector, common_args) for key in BURGERPORTAAL_COLLECTOR_IDS.keys()},
            **{key: (OpzetCollector, common_args) for key in OPZET_COLLECTOR_URLS.keys()},
        }

        collector_class, args = collector_mapping.get(self.waste_collector, (None, None))

        if collector_class:
            self.collector = collector_class(*args)
        else:
            persistent_notification.create(
                self.hass,
                f'Waste collector "{self.waste_collector}" not found!',
                f'Afvalwijzer {self.waste_collector}',
                f'{NOTIFICATION_ID}_collectornotfound_{self.waste_collector}'
            )

    async def schedule_update(self, interval):
        _LOGGER.debug(f"Scheduling update with interval: {interval}")
        nxt = dt_util.utcnow() + interval
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)

    async def async_update(self, *_):
        _LOGGER.debug("Performing async update")
        await self.collector.update()
        if self.update_interval is not None and self.update_interval != 0:
            await self.schedule_update(timedelta(hours=self.update_interval))
        else:
            await self.schedule_update(SCHEDULE_UPDATE_INTERVAL)
        if self.print_waste_type:
            persistent_notification.create(
                self.hass,
                f'Available waste types: {", ".join(self.collector.collections.get_available_waste_types())}',
                f'Afvalwijzer {self.waste_collector}',
                f'{NOTIFICATION_ID}_availablewastetypes_{self.waste_collector}')
            self.print_waste_type = False
        if self.print_waste_type_slugs:
            persistent_notification.create(
                self.hass,
                f'Waste type slugs used by API: {", ".join(self.collector.collections.get_available_waste_type_slugs())}',
                f'Afvalwijzer {self.waste_collector}',
                f'{NOTIFICATION_ID}_availablewastetypeslugs_{self.waste_collector}')
            self.print_waste_type = False

    @property
    def collections(self):
        return self.collector.collections


def get_wastedata_from_config(hass, config):
    _LOGGER.debug("Getting WasteData from config")
    _LOGGER.debug("Get Rest API retriever")
    city_name = config.get(CONF_CITY_NAME)
    postcode = config.get(CONF_POSTCODE)
    street_name = config.get(CONF_STREET_NAME)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX)
    address_id = config.get(CONF_ADDRESS_ID)
    waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
    print_waste_type = config.get(CONF_PRINT_AVAILABLE_WASTE_TYPES)
    print_waste_type_slugs = config.get(CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS)
    update_interval = config.get(CONF_UPDATE_INTERVAL)
    customer_id = config.get(CONF_CUSTOMER_ID)
    custom_mapping = config.get(CONF_CUSTOM_MAPPING)
    config["id"] = _format_id(waste_collector, postcode, street_number)

    if waste_collector in DEPRECATED_AND_NEW_WASTECOLLECTORS:
        persistent_notification.create(
            hass,
            f"Update your config to use {DEPRECATED_AND_NEW_WASTECOLLECTORS[waste_collector]}! You are still using {waste_collector} as a waste collector, which is deprecated. Check your automations and lovelace config, as the sensor names may also be changed!",
            f"Afvalbeheer {waste_collector}",
            f"{NOTIFICATION_ID}_update_config_{waste_collector}",
        )
        waste_collector = DEPRECATED_AND_NEW_WASTECOLLECTORS[waste_collector]

    if waste_collector in ["limburg.net"] and not city_name:
        persistent_notification.create(
            hass,
            f"Config invalid! Cityname is required for {waste_collector}",
            f"Afvalbeheer {waste_collector}",
            f"{NOTIFICATION_ID}_invalid_config_{waste_collector}",
        )
        return

    if waste_collector in ["limburg.net", "recycleapp"] and not street_name:
        persistent_notification.create(
            hass,
            f"Config invalid! Streetname is required for {waste_collector}",
            f"Afvalbeheer {waste_collector}",
            f"{NOTIFICATION_ID}_invalid_config_{waste_collector}",
        )
        return

    return WasteData(
        hass,
        waste_collector,
        city_name,
        postcode,
        street_name,
        street_number,
        suffix,
        custom_mapping,
        address_id,
        print_waste_type,
        print_waste_type_slugs,
        update_interval,
        customer_id,
    )


def _format_id(waste_collector, postcode, house_number):
    _LOGGER.debug(f"Formatting ID for waste_collector: {waste_collector}, postcode: {postcode}, house_number: {house_number}")
    return waste_collector + "-" + postcode + "-" + str(house_number)
