"""Test Smart Energy switch inputs."""

from datetime import datetime, timedelta
from unittest.mock import Mock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartenergy import async_setup
from homeassistant.components.smartenergy.const import (
    CONF_CONSUMERS,
    CURRENT_SCHEDULE_END,
    CURRENT_SCHEDULE_START,
    CURRENT_SCHEDULES,
    DOMAIN,
    DOMAIN_GO_E_CHARGER,
    FORECAST,
    MAIN_COORDINATOR_NAME,
    MARKET_PRICE,
    SCHEDULES,
    SMARTENERGY_AWATTAR,
    START_SCHEDULED_CHARGING,
    START_TIME,
)
from homeassistant.core import HomeAssistant

EXPECTED_MAIN_STATE_1: dict = {
    "consumers": {
        "charger1": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": None,
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_cycle_hours_to_charge": None,
            "current_cycle_charging_time_window_hours": None,
            "current_cycle_charging_time_window_date": None,
            "charging_schedules": {"enabled": True},
        }
    }
}
EXPECTED_MAIN_STATE_2: dict = {
    "consumers": {
        "charger1": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": "precise",
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_cycle_hours_to_charge": 0,
            "current_cycle_charging_time_window_hours": 0,
            "current_cycle_charging_time_window_date": None,
            "charging_schedules": {"enabled": True},
        }
    }
}
EXPECTED_MAIN_STATE_3: dict = {
    "consumers": {
        "charger1": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": "simple",
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_cycle_hours_to_charge": 4,
            "current_cycle_charging_time_window_hours": 19,
            "current_cycle_charging_time_window_date": None,
            "charging_schedules": {"enabled": True},
        }
    }
}


def _set_car_state(hass: HomeAssistant, state: str) -> None:
    """Set car status for the go-eCharger integration."""
    hass.states.async_set(
        f"{SENSOR_DOMAIN}.{DOMAIN_GO_E_CHARGER}_charger1_car_status",
        state,
    )


def _calculate_mock_forecast() -> list:
    """Calculate mock forecast data."""
    current_date = datetime.now()
    forecast = []

    for hour in range(24):
        forecast_date = current_date + timedelta(hours=hour)
        forecast_date = forecast_date.replace(minute=0, second=0, microsecond=0)

        forecast.append(
            {
                MARKET_PRICE: 50 + hour,
                START_TIME: forecast_date.isoformat(),
            }
        )

    return forecast


async def _init_integration(
    hass: HomeAssistant, consumer: dict, state: str
) -> tuple[Mock, Mock]:
    """Initialize the integration, register go-eCharger services and refresh the coordinator."""
    hass.states.async_set(
        f"{SENSOR_DOMAIN}.{SMARTENERGY_AWATTAR}",
        True,
        {FORECAST: _calculate_mock_forecast()},
    )
    assert await async_setup(
        hass,
        {
            DOMAIN: {
                CONF_CONSUMERS: [[consumer]],
            }
        },
    )
    _set_car_state(hass, state)
    mock_start_service = Mock()
    mock_stop_service = Mock()
    hass.services.async_register(
        DOMAIN_GO_E_CHARGER, "start_charging", mock_start_service
    )
    hass.services.async_register(
        DOMAIN_GO_E_CHARGER, "stop_charging", mock_stop_service
    )

    await hass.async_block_till_done()
    await hass.data[DOMAIN][MAIN_COORDINATOR_NAME].async_request_refresh()
    await hass.async_block_till_done()

    return mock_start_service, mock_stop_service


def _assert_start_scheduled_charging_set(hass: HomeAssistant, value: bool) -> None:
    """Assert start_scheduled_charging state value."""
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            START_SCHEDULED_CHARGING
        ]
        is value
    )


def _assert_start_service_called(mock_start_service: Mock) -> None:
    """Assert if the start service was called."""
    mock_start_service.call_args.start_charging.assert_called_with(
        device_name="charger1"
    )


def _assert_stop_service_called(mock_stop_service: Mock) -> None:
    """Assert if the stop service was called."""
    mock_stop_service.call_args.stop_charging.assert_called_with(device_name="charger1")


async def _force_refresh_coordinator(
    hass: HomeAssistant,
    current_schedules_update_hours: int | None = 0,
    current_schedule_update_hours: int | None = 0,
) -> None:
    """Refresh the main coordinator and update dates if desired."""
    data = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data

    if current_schedules_update_hours:
        entity_id = f"{DOMAIN}.charger1_{CURRENT_SCHEDULES}"
        current_forecast = hass.states.get(entity_id).attributes[SCHEDULES]
        current_forecast[0][START_TIME] = current_forecast[0][START_TIME] + timedelta(
            hours=current_schedules_update_hours
        )
        hass.states.async_set(
            entity_id,
            True,
            {SCHEDULES: current_forecast},
        )
        await hass.async_block_till_done()

    if current_schedule_update_hours:
        data[CONF_CONSUMERS]["charger1"][CURRENT_SCHEDULE_START] = data[CONF_CONSUMERS][
            "charger1"
        ][CURRENT_SCHEDULE_START] + timedelta(hours=current_schedule_update_hours)
        data[CONF_CONSUMERS]["charger1"][CURRENT_SCHEDULE_END] = data[CONF_CONSUMERS][
            "charger1"
        ][CURRENT_SCHEDULE_END] + timedelta(hours=current_schedule_update_hours)

    hass.data[DOMAIN][MAIN_COORDINATOR_NAME].async_set_updated_data(data)
    await hass.data[DOMAIN][MAIN_COORDINATOR_NAME].async_request_refresh()
    await hass.async_block_till_done()


async def _assert_start_charging(
    hass: HomeAssistant, mock_start_service: Mock, mock_stop_service: Mock
) -> None:
    """Assert if charging started.

    - assert if the stop service was called
    - set car status to 4
    - assert if start_scheduled_charging is True
    - refresh the coordinator state
    - assert if the start service was called
    - assert if start_scheduled_charging is False.
    """
    # first iteration
    # stop charging
    _assert_stop_service_called(mock_stop_service)
    assert mock_stop_service.call_count == 1
    assert mock_start_service.call_count == 0
    # car status is changed to 4
    _set_car_state(hass, "Charging finished, car can be disconnected")
    # retry is enabled
    _assert_start_scheduled_charging_set(hass, True)

    # second iteration - force coordinator refresh
    await _force_refresh_coordinator(hass)
    # charging started
    _assert_start_service_called(mock_start_service)
    assert mock_start_service.call_count == 1
    assert mock_stop_service.call_count == 1
    _assert_start_scheduled_charging_set(hass, False)


async def test_start_scheduled_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is 4
    - (2) time to charge
    - (2) start charging
    - (2) set retry to FALSE
    - (3) continue charging.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    await _assert_start_charging(hass, mock_start_service, mock_stop_service)

    # third iteration - force coordinator refresh
    await _force_refresh_coordinator(hass)
    assert mock_start_service.call_count == 1
    assert mock_stop_service.call_count == 2
    _assert_start_scheduled_charging_set(hass, False)


async def test_prepare_scheduled_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is 4
    - (2) not yet time to charge
    - (2) keep retry as True.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    # first iteration
    # stop charging
    _assert_stop_service_called(mock_stop_service)
    assert mock_stop_service.call_count == 1
    assert mock_start_service.call_count == 0
    # car status is changed to 4
    _set_car_state(hass, "Charging finished, car can be disconnected")
    # retry is enabled
    _assert_start_scheduled_charging_set(hass, True)

    # second iteration - force coordinator refresh
    await _force_refresh_coordinator(hass, 2)

    # retry is still enabled
    _assert_start_scheduled_charging_set(hass, True)
    # no charging
    assert mock_stop_service.call_count == 1
    assert mock_start_service.call_count == 0


async def test_discard_scheduled_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is NOT 4
    - (2) set retry to FALSE.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    # first iteration
    # stop charging
    _assert_stop_service_called(mock_stop_service)
    assert mock_stop_service.call_count == 1
    assert mock_start_service.call_count == 0
    # retry is enabled
    _assert_start_scheduled_charging_set(hass, True)

    # second iteration - force coordinator refresh
    await _force_refresh_coordinator(hass)

    # don't start charging
    assert mock_start_service.call_count == 0
    assert mock_stop_service.call_count == 1
    _assert_start_scheduled_charging_set(hass, False)


async def test_outdated_scheduled_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is 4
    - (2) start charging
    - (3) car status is 2
    - (3) active schedule is outdated
    - (3) stop charging
    - (3) reset state
    - (4) car status is 4
    - (4) time to charge
    - (4) start charging.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    await _assert_start_charging(hass, mock_start_service, mock_stop_service)

    # third iteration - expired schedule
    # car status is changed to 2
    _set_car_state(hass, "Car is charging")
    await _force_refresh_coordinator(hass, -1, -2)

    # retry is still enabled
    _assert_start_scheduled_charging_set(hass, True)
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_START
        ]
        is None
    )
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_END
        ]
        is None
    )
    # no charging
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 1

    # fourth iteration - start charging
    # car status is changed to 4
    _set_car_state(hass, "Charging finished, car can be disconnected")
    await _force_refresh_coordinator(hass)
    _assert_start_scheduled_charging_set(hass, False)
    _assert_start_service_called(mock_start_service)
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 2


async def test_outdated_prepare_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is 4
    - (2) start charging
    - (3) car status is 2
    - (3) active schedule is outdated
    - (3) stop charging
    - (3) reset state
    - (4) car status is 4
    - (4) not yet time to charge
    - (4) keep retry as True.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    await _assert_start_charging(hass, mock_start_service, mock_stop_service)

    # third iteration - expired schedule
    # car status is changed to 2
    _set_car_state(hass, "Car is charging")
    await _force_refresh_coordinator(hass, 0, -2)

    # retry is still enabled
    _assert_start_scheduled_charging_set(hass, True)
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_START
        ]
        is None
    )
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_END
        ]
        is None
    )
    # no charging
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 1

    # fourth iteration - schedule not ready yet
    # car status is changed to 4
    _set_car_state(hass, "Charging finished, car can be disconnected")
    await _force_refresh_coordinator(hass, 2, 0)
    _assert_start_scheduled_charging_set(hass, True)
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 1


async def test_reset_scheduled_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is 4
    - (2) start charging
    - (3) car status is 2
    - (3) active schedule is outdated
    - (3) stop charging
    - (3) reset state
    - (4) car status is NOT 4
    - (4) set retry to FALSE.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    await _assert_start_charging(hass, mock_start_service, mock_stop_service)

    # third iteration - expired schedule
    # car status is changed to 2
    _set_car_state(hass, "Car is charging")
    await _force_refresh_coordinator(hass, 0, -2)

    # retry is still enabled
    _assert_start_scheduled_charging_set(hass, True)
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_START
        ]
        is None
    )
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_END
        ]
        is None
    )
    # no charging
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 1

    # fourth iteration - schedule not ready yet
    await _force_refresh_coordinator(hass)
    _assert_start_scheduled_charging_set(hass, False)
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 1


async def test_disconnected_scheduled_charging(hass: HomeAssistant, consumer) -> None:
    """Test the flow.

    - (1) car status is 2
    - (1) no active schedule
    - (1) stop charging
    - (2) car status is 4
    - (2) start charging
    - (3) car status is 4
    - (3) active schedule present
    - (3) stop charging
    - (3) reset state.
    """
    mock_start_service, mock_stop_service = await _init_integration(
        hass, consumer, "Car is charging"
    )

    await _assert_start_charging(hass, mock_start_service, mock_stop_service)

    # third iteration - car disconnected
    # car status is changed to 2
    _set_car_state(hass, "Charging finished, car can be disconnected")
    await _force_refresh_coordinator(hass)

    # retry is still enabled
    _assert_start_scheduled_charging_set(hass, False)
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_START
        ]
        is None
    )
    assert (
        hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"][
            CURRENT_SCHEDULE_END
        ]
        is None
    )
    # charging stopped
    _assert_stop_service_called(mock_stop_service)
    assert mock_stop_service.call_count == 2
    assert mock_start_service.call_count == 1
