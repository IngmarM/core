"""Entity utility functions for Smart Energy."""

import enum
import logging
import re

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_INPUT_SOURCE, CONF_OUTPUT_SOURCE, CONF_SMART_ENERGY_MODE, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)

CONSUMER_PLACEHOLDER_NAME = "CONSUMER_NAME"
ENTITY_NAMES = [
    f"{SENSOR_DOMAIN}.{DOMAIN}_{CONSUMER_PLACEHOLDER_NAME}_current_schedule_start",
    f"{SENSOR_DOMAIN}.{DOMAIN}_{CONSUMER_PLACEHOLDER_NAME}_current_schedule_end",
    f"{SENSOR_DOMAIN}.{DOMAIN}_{CONSUMER_PLACEHOLDER_NAME}_{CONF_SMART_ENERGY_MODE}",
    f"{SENSOR_DOMAIN}.{DOMAIN}_{CONSUMER_PLACEHOLDER_NAME}_{CONF_INPUT_SOURCE}",
    f"{SENSOR_DOMAIN}.{DOMAIN}_{CONSUMER_PLACEHOLDER_NAME}_{CONF_OUTPUT_SOURCE}",
]


def _get_entity_names(e_registry: er.EntityRegistry, integration: str) -> list[str]:
    """Find entities based on the regex.

    For example: sensor.smartenergy_goecharger_charger1_name => charger1.
    """
    matched_entities = []

    for entity in e_registry.entities:
        match = re.match(f".*{integration}_([A-Za-z0-9-]+)", entity)
        if match:
            match_group = match.groups()[0]
            if match_group not in matched_entities:
                matched_entities.append(match_group)

    return matched_entities


def filter_entities_by_integration(
    hass: HomeAssistant, integrations: list[enum.Enum]
) -> tuple[dict, list]:
    """Find normalized names for provided entities and mapping between them."""
    e_registry: er.EntityRegistry = er.async_get(hass)

    normalized_entity_names: list[str] = []
    integration_entity_map: dict = {}

    for registered_output_integration in integrations:
        normalized_entity_names = normalized_entity_names + _get_entity_names(
            e_registry, registered_output_integration.value
        )
        # create a map of registered integrations and normalized entity names
        integration_entity_map[
            registered_output_integration.value
        ] = normalized_entity_names

    return integration_entity_map, normalized_entity_names


def create_entity(hass: HomeAssistant, platform: str, domain: str, name: str) -> None:
    """Create an entity for a given platform and domain."""
    e_registry = er.async_get(hass)
    e_registry.async_get_or_create(platform, domain, name)


def remove_entities_and_devices(hass: HomeAssistant, consumer_name: str) -> None:
    """Remove registered entities (sensor, switch, etc.) and devices."""

    _LOGGER.debug("Removing entities and devices for %s", consumer_name)

    e_registry = er.async_get(hass)
    d_registry = dr.async_get(hass)
    devices = d_registry.devices

    filtered_devices = []

    # device IDs are random strings, not a friendly names, therefore we need to find them
    for device_id in devices:
        device_name = devices[device_id].name or ""
        if consumer_name in device_name:
            filtered_devices.append(device_id)

    # and remove them
    for device_id in filtered_devices:
        d_registry.async_remove_device(device_id)

    for entity_name in ENTITY_NAMES:
        name = entity_name.replace(CONSUMER_PLACEHOLDER_NAME, consumer_name)
        e_registry.async_remove(name)

    _LOGGER.debug("Removed entities and devices for %s", consumer_name)
