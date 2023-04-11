"""Smart Energy main integration file."""

import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .calculations import create_consumer_assignment, get_consumer_config
from .const import (
    CONF_CHARGING_TIME_WINDOW_HOURS,
    CONF_CONSUMERS,
    CONF_HOURS_TO_CHARGE,
    CONF_INPUT_SOURCE,
    CONF_OUTPUT_SOURCE,
    CONF_SMART_ENERGY_MODE,
    DOMAIN,
    INIT_STATE,
    MAIN_COORDINATOR_NAME,
    UNSUB_OPTIONS_UPDATE_LISTENER,
)
from .entity import remove_entities_and_devices
from .state import StateFetcher, add_to_main_state, init_state, remove_from_main_state

_LOGGER: logging.Logger = logging.getLogger(__name__)

MIN_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)
DEFAULT_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)

PLATFORMS: list[str] = [
    SENSOR_DOMAIN,
]

# Configuration validation
CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_CONSUMERS, default=[]): vol.All(
                    [
                        cv.ensure_list,
                        vol.All(
                            {
                                vol.Required(CONF_NAME): vol.All(cv.string),
                                vol.Required(CONF_INPUT_SOURCE): vol.All(cv.string),
                                vol.Required(CONF_OUTPUT_SOURCE): vol.All(cv.string),
                                vol.Required(CONF_SMART_ENERGY_MODE): vol.All(
                                    cv.string
                                ),
                                vol.Optional(CONF_HOURS_TO_CHARGE): vol.All(
                                    cv.positive_int
                                ),
                                vol.Optional(CONF_CHARGING_TIME_WINDOW_HOURS): vol.All(
                                    cv.positive_int
                                ),
                            },
                            extra=vol.ALLOW_EXTRA,
                        ),
                    ],
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _setup_coordinator(
    hass: HomeAssistant,
    scan_interval: timedelta,
    coordinator_name: str,
    default_state: dict,
) -> DataUpdateCoordinator:
    """Initialize the coordinator with a default state."""
    _LOGGER.debug("Configuring coordinator=%s", coordinator_name)

    state_fetcher: StateFetcher = StateFetcher(hass)
    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=state_fetcher.fetch_states,
        update_interval=scan_interval,
    )
    state_fetcher.coordinator = coordinator
    hass.data[DOMAIN][coordinator_name] = coordinator
    hass.data[DOMAIN][coordinator_name].data = default_state

    return coordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Awattar defined via the UI.

    - state update
    - sensors.
    """
    options = config_entry.options
    data = dict(config_entry.data)
    entry_id = config_entry.entry_id

    _LOGGER.debug(
        "Setting up a dynamic Smart Energy config entry with id=%s %s",
        entry_id,
        options,
    )

    configured_consumer = create_consumer_assignment(options)

    # update state
    add_to_main_state(hass, configured_consumer)
    hass.data[DOMAIN][entry_id] = data

    # register sensors, switches, ...
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    # register cleanup listeners
    unsub_options_update_listener = config_entry.add_update_listener(
        options_update_listener
    )
    hass.data[DOMAIN][INIT_STATE][UNSUB_OPTIONS_UPDATE_LISTENER][
        entry_id
    ] = unsub_options_update_listener

    _LOGGER.debug("Setup for the dynamic Smart Energy config entry completed")

    return True


async def options_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config flow entry."""
    entry_id = config_entry.entry_id
    _LOGGER.debug("Unloading the Smart Energy config entry=%s", entry_id)

    # unregister sensors, switches, ...
    unloaded_platforms = [
        (
            await asyncio.gather(
                *[
                    hass.config_entries.async_forward_entry_unload(
                        config_entry, platform
                    )
                ]
            ),
            platform,
        )
        for platform in PLATFORMS
    ]
    unload_ok = all(unloaded_platforms)

    # remove options_update_listener
    hass.data[DOMAIN][INIT_STATE][UNSUB_OPTIONS_UPDATE_LISTENER][entry_id]()

    if unload_ok:
        consumer_name = hass.data[DOMAIN][entry_id][CONF_OUTPUT_SOURCE]

        # cleanup entities, devices
        remove_entities_and_devices(hass, consumer_name)
        # cleanup state
        remove_from_main_state(hass, consumer_name)
        hass.data[DOMAIN].pop(entry_id)
        hass.data[DOMAIN][INIT_STATE][UNSUB_OPTIONS_UPDATE_LISTENER].pop(entry_id)

    _LOGGER.debug("Unloaded the Smart Energy config entry=%s", entry_id)

    return unload_ok


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Smart Energy platforms and services."""

    _LOGGER.debug("Setting up the Smart Energy integration")

    hass.data[DOMAIN] = hass.data[DOMAIN] if DOMAIN in hass.data else {}
    domain_config = config[DOMAIN] if DOMAIN in config else {}

    scan_interval = DEFAULT_UPDATE_INTERVAL
    init_state(hass)
    consumers = get_consumer_config(domain_config.get(CONF_CONSUMERS, []))
    _setup_coordinator(
        hass,
        scan_interval,
        MAIN_COORDINATOR_NAME,
        {
            CONF_CONSUMERS: consumers,
        },
    )

    # load all platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            async_load_platform(
                hass,
                platform,
                DOMAIN,
                {
                    CONF_CONSUMERS: consumers,
                },
                config,
            )
        )

    _LOGGER.debug("Setup for the Smart Energy integration completed")

    return True
