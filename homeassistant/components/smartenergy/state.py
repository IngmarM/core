"""Smart Energy state (coordinator) management."""

from datetime import datetime, timedelta
import logging
from operator import itemgetter
from typing import Any

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .calculations import get_consumer_config
from .const import (
    CHARGING_SCHEDULES,
    CONF_CONSUMERS,
    CONF_OUTPUT_SOURCE,
    CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE,
    CURRENT_CYCLE_HOURS_TO_CHARGE,
    CURRENT_SCHEDULE_END,
    CURRENT_SCHEDULE_START,
    CURRENT_SCHEDULES,
    DOMAIN,
    DOMAIN_GO_E_CHARGER,
    ENABLED,
    FORECAST,
    INIT_STATE,
    MAIN_COORDINATOR_NAME,
    MARKET_PRICE,
    SCHEDULES,
    SMARTENERGY_AWATTAR,
    START_SCHEDULED_CHARGING,
    START_TIME,
    UNSUB_OPTIONS_UPDATE_LISTENER,
    VALUE,
)
from .controller import start_charging, stop_charging

_LOGGER: logging.Logger = logging.getLogger(__name__)


def init_state(hass: HomeAssistant) -> None:
    """Initialize the state."""

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][INIT_STATE] = {
        UNSUB_OPTIONS_UPDATE_LISTENER: {},
    }


def add_to_main_state(hass: HomeAssistant, configured_consumer: list) -> None:
    """Add data to the main state.

    - consumers.
    """

    _LOGGER.debug(
        "Updating the main state, current main state is %s",
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data,
    )

    consumers = get_consumer_config(configured_consumer)
    main_state_data = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data

    for consumer_name, consumer_value in consumers.items():
        if consumer_name not in main_state_data[CONF_CONSUMERS]:
            main_state_data[CONF_CONSUMERS] = main_state_data[CONF_CONSUMERS] | {
                consumer_name: consumer_value
            }

    hass.data[DOMAIN][MAIN_COORDINATOR_NAME].async_set_updated_data(main_state_data)

    _LOGGER.debug(
        "Updated the main state to %s",
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data,
    )


def remove_from_main_state(hass: HomeAssistant, consumer_name: str) -> None:
    """Remove data from the main state.

    - consumers.
    """

    _LOGGER.debug(
        "Remove from the main state, current main state is %s",
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data,
    )

    main_state_data = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data
    main_state_data[CONF_CONSUMERS] = {
        key: main_state_data[CONF_CONSUMERS][key]
        for key in main_state_data[CONF_CONSUMERS]
        if key != consumer_name
    }
    hass.data[DOMAIN][MAIN_COORDINATOR_NAME].async_set_updated_data(main_state_data)

    _LOGGER.debug(
        "Removed from the main state to %s",
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data,
    )


class StateFetcher:
    """Representation of the main coordinator state handling.

    Whenever the coordinator is triggered, it will call the consumer APIs/services and
    update the state.
    """

    coordinator: DataUpdateCoordinator

    def __init__(self, hass: HomeAssistant) -> None:
        """Construct state fetcher with hass property."""
        self._hass = hass

    def get_schedules(self, consumer_name: str) -> Any:
        """Get forecast schedules from the state attribute."""
        schedules = self._hass.states.get(
            f"{DOMAIN}.{consumer_name}_{CURRENT_SCHEDULES}"
        )

        if (
            schedules is None
            or not schedules.attributes
            or SCHEDULES not in schedules.attributes
        ):
            return []

        return schedules.attributes[SCHEDULES]

    def set_schedules(self, schedules: list, consumer_name: str) -> None:
        """Set forecast schedules as a state attribute."""
        self._hass.states.async_set(
            f"{DOMAIN}.{consumer_name}_{CURRENT_SCHEDULES}",
            "Unknown",
            {SCHEDULES: schedules},
        )

    def find_forecast_dates(self, end_date: datetime) -> list:
        """Find a forecast for a given time range and sort data to find the lowest value."""
        forecast_data = []
        awattar_prices = self._hass.states.get(f"{SENSOR_DOMAIN}.{SMARTENERGY_AWATTAR}")

        if not awattar_prices or FORECAST not in awattar_prices.attributes:
            return []

        for price in awattar_prices.attributes[FORECAST]:
            start_time = datetime.fromisoformat(price[START_TIME]).replace(tzinfo=None)
            if start_time <= end_date:
                forecast_data.append(
                    {
                        VALUE: price[MARKET_PRICE],
                        START_TIME: start_time,
                    }
                )

        return sorted(forecast_data, key=itemgetter(VALUE, START_TIME))

    def calculate_next_schedules(
        self, car_status: str, scheduler_data: dict, consumer_name: str
    ) -> list:
        """Calculate next best schedules based on the CO2 within a given time range."""
        start_scheduled_charging = scheduler_data[START_SCHEDULED_CHARGING]
        current_cycle_hours_to_charge = scheduler_data[CURRENT_CYCLE_HOURS_TO_CHARGE]
        current_cycle_charging_time_window_date = scheduler_data[
            CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE
        ]

        schedules: list = self.get_schedules(consumer_name)

        if (
            car_status != "Car is charging" and start_scheduled_charging is False
        ) or schedules == []:
            forecast_time_range = self.find_forecast_dates(
                current_cycle_charging_time_window_date
            )
            forecast_portion = forecast_time_range[0:current_cycle_hours_to_charge:]

            schedules = forecast_portion
            self.set_schedules(forecast_portion, consumer_name)

        _LOGGER.debug("Calculated schedules=%s", schedules)
        return schedules

    async def start_scheduled_charging(
        self, scheduler_data: dict, consumer: str, schedules: list
    ) -> None:
        """Set current schedule in the state and start charging."""
        scheduler_data[CURRENT_SCHEDULE_START] = schedules[0][START_TIME]
        scheduler_data[CURRENT_SCHEDULE_END] = scheduler_data[
            CURRENT_SCHEDULE_START
        ] + timedelta(hours=1)

        self.set_schedules(schedules[1 : len(schedules)], consumer)

        await start_charging(
            self._hass, scheduler_data[CONF_OUTPUT_SOURCE], {"device_name": consumer}
        )
        scheduler_data[START_SCHEDULED_CHARGING] = False

    async def stop_scheduled_charging(
        self, scheduler_data: dict, consumer: str
    ) -> None:
        """Stop the charging and set the future start of the charging."""
        await stop_charging(
            self._hass, scheduler_data[CONF_OUTPUT_SOURCE], {"device_name": consumer}
        )
        scheduler_data[START_SCHEDULED_CHARGING] = True

    def reset_current_schedule(self, scheduler_data: dict) -> None:
        """Reset current schedule in the state."""
        scheduler_data[CURRENT_SCHEDULE_START] = None
        scheduler_data[CURRENT_SCHEDULE_END] = None

    async def try_to_start_charging(
        self, car_status: str, scheduler_data: dict, consumer: str, schedules: list
    ) -> None:
        """Check if we can start charging or not.

        In case the next charging is set (start_scheduled_charging=True),
        check if the car charging is stopped (car_status=4). If so,
        check if the next schedule date matches with the current date.
        If it matches, start the charging, otherwise wait for the next
        coordinator refresh. If car_status is NOT 4, disable the next charging
        as it's likely in the incorrect state.
        """
        _LOGGER.debug("Next charging is active")

        # previous iteration stopped charging, therefore the car status should be 4
        if car_status == "Charging finished, car can be disconnected":  # 4
            current_time = datetime.now()
            end_time = schedules[0][START_TIME] + timedelta(hours=1)
            # if the current time is scheduled, we can start charging
            # otherwise we wait for the right time (in the next coordinator updates)
            if end_time > current_time > schedules[0][START_TIME]:
                _LOGGER.debug("Car is ready and schedule is ready, starting to charge")
                await self.start_scheduled_charging(scheduler_data, consumer, schedules)
            else:
                _LOGGER.debug("Car is ready, but schedule is not ready")
        # if car status is not 4, something went wrong and we have to start from scratch
        else:
            _LOGGER.debug(
                "Next charging is active, but car is not ready, canceling next charging"
            )
            scheduler_data[START_SCHEDULED_CHARGING] = False

    async def reset_or_continue_charging(
        self, scheduler_data: dict, consumer: str
    ) -> None:
        """Check if the current schedule is outdated. If so, reset the state and stop charging.

        Otherwise, keep charging.
        """
        # keep charging by default
        current_time = datetime.now()

        if current_time > scheduler_data[CURRENT_SCHEDULE_END]:
            _LOGGER.debug(
                "Car ready, schedule outdated, stopping charging, prepared for next charging"
            )
            await self.stop_scheduled_charging(scheduler_data, consumer)
            self.reset_current_schedule(scheduler_data)
        else:
            _LOGGER.debug("Everything good, continue with charging")

    async def fetch_states(self) -> Any:
        """Start scheduled charging if enabled.

        Scheduled charging is executed in 2 executions to avoid race conditions.
        Firstly it finds out what is the best schedule and if charging is applicable.
        If so, mark it in the state and in the next run start charging if the time is correct.
        """

        data = self.coordinator.data
        _LOGGER.debug("Updating the current coordinator data=%s", data)

        for consumer in data[CONF_CONSUMERS]:
            scheduler_data = data[CONF_CONSUMERS][consumer]

            if scheduler_data[ENABLED] and scheduler_data[CHARGING_SCHEDULES][ENABLED]:
                scheduler_data = data[CONF_CONSUMERS][consumer]
                start_scheduled_charging = scheduler_data[START_SCHEDULED_CHARGING]

                # get car status
                car_state: State | None = self._hass.states.get(
                    f"{SENSOR_DOMAIN}.{DOMAIN_GO_E_CHARGER}_{consumer}_car_status"
                )
                car_status: str = car_state.state if car_state else ""

                _LOGGER.debug("Car status for %s=%s", consumer, car_status)

                # find best charging schedules based on the CO2 intensity
                # generate new schedules only if:
                # - car is not connected - and charging is not planned from the previous iteration
                # - car is connected/schedule is planned, but it's empty
                schedules = self.calculate_next_schedules(
                    car_status, scheduler_data, consumer
                )

                if schedules == []:
                    _LOGGER.debug("No schedules found")
                    break

                # start_scheduled_charging means we are running next iterations of a planned
                # schedule, just waiting for the car to be ready and for the right time
                if start_scheduled_charging:
                    await self.try_to_start_charging(
                        car_status, scheduler_data, consumer, schedules
                    )
                else:
                    # we need the car to be connected - car status is 2
                    if car_status == "Car is charging":  # 2
                        current_schedule_start = scheduler_data[CURRENT_SCHEDULE_START]
                        current_schedule_end = scheduler_data[CURRENT_SCHEDULE_END]

                        # there is no active schedule, we need to stop charging and set a new one
                        if (
                            current_schedule_start is None
                            or current_schedule_end is None
                        ):
                            _LOGGER.debug(
                                "Car ready, no schedule, stopping charging, prepared for charging"
                            )
                            await self.stop_scheduled_charging(scheduler_data, consumer)
                        # some schedule is already active
                        # keep charging by default
                        # otherwise stop charging and reset outdated schedule
                        else:
                            await self.reset_or_continue_charging(
                                scheduler_data, consumer
                            )
                    else:
                        _LOGGER.debug(
                            "Scheduler skipped, incorrect car status=%s",
                            car_status,
                        )
                        # car is disconnected and some schedule is set
                        # stop charging and reset the schedule
                        if (
                            scheduler_data[CURRENT_SCHEDULE_START] is not None
                            or scheduler_data[CURRENT_SCHEDULE_END] is not None
                        ):
                            await stop_charging(
                                self._hass,
                                scheduler_data[CONF_OUTPUT_SOURCE],
                                {"device_name": consumer},
                            )
                            self.reset_current_schedule(scheduler_data)

        _LOGGER.debug("Updated coordinator data=%s", data)

        return data
