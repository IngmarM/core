"""Platform for Smart Energy sensor integration."""
from collections.abc import Callable, Generator
import logging
from typing import Any, Literal

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .calculations import create_consumer_assignment, get_consumer_config
from .const import (
    CONF_CONSUMERS,
    CONF_INPUT_SOURCE,
    CONF_OUTPUT_SOURCE,
    CONF_SMART_ENERGY_MODE,
    CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE,
    CURRENT_CYCLE_HOURS_TO_CHARGE,
    CURRENT_SCHEDULE_END,
    CURRENT_SCHEDULE_START,
    DOMAIN,
    MAIN_COORDINATOR_NAME,
    MANUFACTURER,
)

POWER_WATT: Literal["W"] = "W"
KILO_WATT_HOUR: Literal["kWh"] = "kWh"

SCHEDULER_SENSORS: list[dict[str, str]] = [
    {"id": CURRENT_SCHEDULE_START, "type": "date"},
    {"id": CURRENT_SCHEDULE_END, "type": "date"},
    {"id": CURRENT_CYCLE_HOURS_TO_CHARGE, "type": "text"},
    {"id": CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE, "type": "date"},
    {"id": CONF_SMART_ENERGY_MODE, "type": "text"},
    {"id": CONF_INPUT_SOURCE, "type": "text"},
    {"id": CONF_OUTPUT_SOURCE, "type": "text"},
]

_LOGGER: logging.Logger = logging.getLogger(__name__)


class SchedulerSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor for consumer assignments."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_id: str,
        name: str,
        attribute: str,
        unit: str,
        state_class: SensorStateClass | None,
        device_class: SensorDeviceClass | None,
        consumer_name: str,
    ) -> None:
        """Initialize the Base sensor."""

        super().__init__(coordinator)
        self.entity_id = entity_id
        self._name = name
        self._attribute = attribute
        self._unit = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._consumer_name = consumer_name

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique_id of the sensor."""
        return f"{self.entity_id}_{self._attribute}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return self._unit

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.entity_id)},
            "name": self.entity_id,
            "manufacturer": MANUFACTURER,
            "model": "",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        attr_name_without_prefix = self._attribute.replace(
            self._consumer_name + "_", ""
        )

        return self.coordinator.data[CONF_CONSUMERS][self._consumer_name][
            attr_name_without_prefix
        ]


def _setup_sensors(
    hass: HomeAssistant,
    sensors_config: dict,
    sensor_class: type,
    coordinator_name: str,
    consumer_name: str | None = None,
) -> list:
    """Set up sensor attributes and instantiate."""

    sensors = []
    for sensor in sensors_config.get("sensors", {}):
        _LOGGER.debug("Adding sensor=%s", sensor)

        sensor_unit = (
            sensors_config.get("units", {}).get(sensor).get("unit")
            if sensors_config.get("units", {}).get(sensor)
            else ""
        )
        sensor_name = (
            sensors_config.get("units", {}).get(sensor).get("name")
            if sensors_config.get("units", {}).get(sensor)
            else sensor
        )
        sensor_state_class = (
            sensors_config.get("state_classes", {})[sensor]
            if sensor in sensors_config.get("state_classes", {})
            else ""
        )
        sensor_device_class = (
            sensors_config.get("device_classes", {})[sensor]
            if sensor in sensors_config.get("device_classes", {})
            else ""
        )

        sensors.append(
            sensor_class(
                hass.data[DOMAIN][coordinator_name],
                f"{SENSOR_DOMAIN}.{DOMAIN}_{sensor}",
                sensor_name,
                sensor,
                sensor_unit,
                sensor_state_class,
                sensor_device_class,
                consumer_name,
            )
        )

    return sensors


def _generate_scheduler_sensors_config(base_sensors: Generator) -> dict:
    """Generate sensor config for scheduler sensors."""

    sensors_config: dict[str, Any] = {
        "sensors": [],
        "units": {},
        "state_classes": {},
        "device_classes": {},
    }

    device_classes_map: dict[str, Any] = {
        "kwh": SensorDeviceClass.ENERGY,
        "date": SensorDeviceClass.DATE,
        "text": "",
    }

    units_map: dict[str, str | None] = {
        "kwh": KILO_WATT_HOUR,
        "date": None,
        "text": None,
    }

    for base_sensor in base_sensors:
        sensors_config["sensors"].append(base_sensor["id"])
        sensors_config["state_classes"][base_sensor["id"]] = None
        sensors_config["device_classes"][base_sensor["id"]] = device_classes_map[
            base_sensor["type"]
        ]
        sensors_config["units"][base_sensor["id"]] = {
            "unit": units_map[base_sensor["type"]],
            "name": base_sensor["id"],
        }

    return sensors_config


def _generate_scheduler_sensors(
    consumer_name: str, scheduler_sensors: list[dict[str, str]]
) -> Generator:
    """Generate base scheduler sensor information."""

    return (
        {
            "id": consumer_name + "_" + scheduler_sensor["id"],
            "type": scheduler_sensor["type"],
        }
        for scheduler_sensor in scheduler_sensors
    )


def setup_entities(
    hass: HomeAssistant,
    async_add_entities: Callable,
    consumers: dict,
) -> None:
    """Initialize all sensors and register in the Home Assistant."""

    for consumer_name in consumers:
        scheduler_sensors = _generate_scheduler_sensors(
            consumer_name, SCHEDULER_SENSORS
        )

        async_add_entities(
            _setup_sensors(
                hass,
                _generate_scheduler_sensors_config(scheduler_sensors),
                SchedulerSensor,
                MAIN_COORDINATOR_NAME,
                consumer_name,
            )
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    entry_id = config_entry.entry_id
    config = hass.data[DOMAIN][entry_id]
    _LOGGER.debug("Setting up the Smart Energy sensor for=%s", entry_id)

    if config_entry.options:
        config.update(config_entry.options)

    configured_consumer = create_consumer_assignment(config_entry.options)
    consumers = get_consumer_config(configured_consumer)

    setup_entities(
        hass,
        async_add_entities,
        consumers,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    _config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up Smart Energy Sensor platform."""
    _LOGGER.debug("Setting up the Smart Energy sensor platform")

    if discovery_info is None:
        _LOGGER.error("Missing discovery_info, skipping setup")
        return

    setup_entities(
        hass,
        async_add_entities,
        discovery_info[CONF_CONSUMERS],
    )
