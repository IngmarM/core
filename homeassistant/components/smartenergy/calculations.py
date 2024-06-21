"""Smart Energy calculation functions."""

from datetime import datetime, timedelta
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.const import CONF_NAME

from .const import (
    CHARGING_SCHEDULES,
    CONF_CHARGING_TIME_WINDOW_HOURS,
    CONF_HOURS_TO_CHARGE,
    CONF_INPUT_SOURCE,
    CONF_OUTPUT_SOURCE,
    CONF_OUTPUT_SOURCE_INTEGRATION,
    CONF_SMART_ENERGY_MODE,
    CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE,
    CURRENT_CYCLE_CHARGING_TIME_WINDOW_HOURS,
    CURRENT_CYCLE_HOURS_TO_CHARGE,
    CURRENT_SCHEDULE_END,
    CURRENT_SCHEDULE_START,
    ENABLED,
    SIMPLE,
    START_SCHEDULED_CHARGING,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


def calculate_next_time_window(
    smart_energy_mode: str, charging_time_window_hours: int
) -> datetime | None:
    """Calculate next time window based on the mode (simple/precise).

    Simple mode is scheduled to 7AM. Precise is based on the provided configuration.
    """
    end_date = datetime.now()

    if smart_energy_mode == SIMPLE:
        # 7 AM
        end_date = end_date.replace(hour=7, minute=0, second=0, microsecond=0)
        end_date += timedelta(days=1)
    else:
        if not charging_time_window_hours:
            return None

        end_date += timedelta(hours=charging_time_window_hours)

    return end_date


def calculate_time_window_hours(next_time_window: datetime | None) -> int | None:
    """Transform date into hours."""
    if not next_time_window:
        return None

    current_date = datetime.now()

    return int((next_time_window - current_date).seconds / 3_600)


def get_consumer_config(configured_consumers: list) -> dict:
    """Create object with consumer information.

    - charging schedules - dates and hours
    - charging mode - simple/precise
    - input/output source integrations.
    """

    consumers = {}

    for consumer in configured_consumers:
        name = consumer[0].get(CONF_NAME)
        input_source = consumer[0].get(CONF_INPUT_SOURCE)
        output_source = consumer[0].get(CONF_OUTPUT_SOURCE)
        smart_energy_mode = consumer[0].get(CONF_SMART_ENERGY_MODE)
        hours_to_charge = consumer[0].get(CONF_HOURS_TO_CHARGE)
        charging_time_window_hours = consumer[0].get(CONF_CHARGING_TIME_WINDOW_HOURS)

        next_time_window = calculate_next_time_window(
            smart_energy_mode, charging_time_window_hours
        )

        consumers[name] = {
            ENABLED: True,
            CONF_INPUT_SOURCE: input_source,
            CONF_OUTPUT_SOURCE: output_source,
            CONF_SMART_ENERGY_MODE: smart_energy_mode,
            CURRENT_SCHEDULE_START: None,
            CURRENT_SCHEDULE_END: None,
            CURRENT_CYCLE_HOURS_TO_CHARGE: (
                4 if smart_energy_mode == SIMPLE else hours_to_charge
            ),
            CURRENT_CYCLE_CHARGING_TIME_WINDOW_HOURS: (
                calculate_time_window_hours(next_time_window)
                if smart_energy_mode == SIMPLE
                else charging_time_window_hours
            ),
            CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE: next_time_window,
            START_SCHEDULED_CHARGING: False,
            CHARGING_SCHEDULES: {
                ENABLED: True,
            },
        }

    _LOGGER.debug("Created initial consumers config=%s", consumers)
    return consumers


def create_consumer(config: dict) -> list[list[dict]]:
    """Create a single consumer from the provided configuration."""

    return [
        [
            {
                CONF_INPUT_SOURCE: config[CONF_INPUT_SOURCE],
                CONF_OUTPUT_SOURCE: config[CONF_OUTPUT_SOURCE],
            }
        ]
    ]


def create_consumer_assignment(
    config: MappingProxyType[str, Any] | dict
) -> list[list[dict]]:
    """Create a single consumer assignment from the provided configuration."""

    return [
        [
            {
                CONF_INPUT_SOURCE: config[CONF_INPUT_SOURCE],
                CONF_OUTPUT_SOURCE: config[CONF_OUTPUT_SOURCE_INTEGRATION],
                CONF_NAME: config[CONF_OUTPUT_SOURCE],
                CONF_SMART_ENERGY_MODE: config[CONF_SMART_ENERGY_MODE],
            }
        ]
    ]
