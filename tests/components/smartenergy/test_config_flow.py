"""Test the Smart Energy config flow and options flow."""

from typing import Any
from unittest import mock

from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartenergy import async_setup
from homeassistant.components.smartenergy.const import (
    CONF_CONSUMERS,
    CONF_INPUT_SOURCE,
    CONF_OUTPUT_SOURCE,
    CONF_OUTPUT_SOURCE_INTEGRATION,
    CONF_SMART_ENERGY_MODE,
    CURRENT_CYCLE_HOURS_TO_CHARGE,
    CURRENT_SCHEDULE_END,
    CURRENT_SCHEDULE_START,
    DOMAIN,
    INIT_STATE,
    MAIN_COORDINATOR_NAME,
    START_SCHEDULED_CHARGING,
    UNSUB_OPTIONS_UPDATE_LISTENER,
)
from homeassistant.components.smartenergy.controller import InputTypes, OutputTypes
from homeassistant.components.smartenergy.entity import create_entity
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
    FlowResult,
)
from homeassistant.loader import Integration

from tests.common import MockConfigEntry

GET_INTEGRATIONS_MOCK_REFERENCE = (
    f"homeassistant.components.{DOMAIN}.config_flow.async_get_integrations"
)

CONFIG_FLOW_EXPECTED_RESULT = {
    "input_source": "smartenergy_awattar",
    "output_source": "charger1",
    "smart_energy_mode": "simple",
    "output_source_integration": "smartenergy_goecharger",
}

OPTIONS_FLOW_EXPECTED_RESULT = {
    "input_source": "smartenergy_awattar",
    "output_source": "charger2",
    "smart_energy_mode": "simple",
    "output_source_integration": "smartenergy_goecharger",
}

CONFIG_FLOW_EXPECTED_MAIN_STATE = {
    "consumers": {
        "charger1": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": "simple",
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_schedules": [],
            "current_cycle_hours_to_charge": 4,
            "current_cycle_charging_time_window_hours": None,
            "current_cycle_charging_time_window_date": None,
            "start_scheduled_charging": False,
            "charging_schedules": {"enabled": True},
        }
    }
}
EXPECTED_MAIN_STATE = {
    "consumers": {
        "charger1": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": "simple",
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_schedules": [],
            "current_cycle_hours_to_charge": 4,
            "current_cycle_charging_time_window_hours": None,
            "current_cycle_charging_time_window_date": None,
            "start_scheduled_charging": False,
            "charging_schedules": {"enabled": True},
        }
    }
}
CONFIG_FLOW_EXPECTED_MAIN_STATE_MERGE = {
    "consumers": {
        "charger1": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": "simple",
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_schedules": [],
            "current_cycle_hours_to_charge": 4,
            "current_cycle_charging_time_window_hours": None,
            "current_cycle_charging_time_window_date": None,
            "start_scheduled_charging": False,
            "charging_schedules": {"enabled": True},
        }
    }
}
OPTIONS_FLOW_EXPECTED_MAIN_STATE = {
    "consumers": {
        "charger2": {
            "enabled": True,
            "input_source": "smartenergy_awattar",
            "output_source": "smartenergy_goecharger",
            "smart_energy_mode": "simple",
            "current_schedule_start": None,
            "current_schedule_end": None,
            "current_schedules": [],
            "current_cycle_hours_to_charge": 4,
            "current_cycle_charging_time_window_hours": None,
            "current_cycle_charging_time_window_date": None,
            "start_scheduled_charging": False,
            "charging_schedules": {"enabled": True},
        }
    }
}


async def mocked_integration(*args: Any, **kwargs: Any) -> dict[str, Integration]:
    """Mock the external integrations."""
    return {
        OutputTypes.GO_E: Integration(
            args[0], "", "", {"domain": OutputTypes.GO_E.value}
        ),
        InputTypes.AWATTAR: Integration(
            args[0], "", "", {"domain": InputTypes.AWATTAR.value}
        ),
    }


async def _initialize_and_assert_flow(hass: HomeAssistant) -> FlowResult:
    """Initialize the config flow and do the basic checks."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == RESULT_TYPE_FORM
    assert result_init["errors"] is None

    return result_init


async def _initialize_and_assert_options(hass: HomeAssistant, data: dict) -> FlowResult:
    """Create mocked config flow config entry and initialize it."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="added_entry",
        data=data,
        options=data,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result_init = await hass.config_entries.options.async_init(config_entry.entry_id)

    return result_init


def _assert_state(
    hass: HomeAssistant,
    data: dict,
    expected_data: dict,
    listeners_length: int | None = 1,
) -> None:
    """Compare state values to the expected values."""
    assert data[CONF_INPUT_SOURCE] == expected_data[CONF_INPUT_SOURCE]
    assert data[CONF_OUTPUT_SOURCE] == expected_data[CONF_OUTPUT_SOURCE]
    assert data[CONF_SMART_ENERGY_MODE] == expected_data[CONF_SMART_ENERGY_MODE]
    assert data[CURRENT_SCHEDULE_START] == expected_data[CURRENT_SCHEDULE_START]
    assert data[CURRENT_SCHEDULE_END] == expected_data[CURRENT_SCHEDULE_END]
    assert (
        data[CURRENT_CYCLE_HOURS_TO_CHARGE]
        == expected_data[CURRENT_CYCLE_HOURS_TO_CHARGE]
    )
    assert data[START_SCHEDULED_CHARGING] == expected_data[START_SCHEDULED_CHARGING]
    assert (
        len(hass.data[DOMAIN][INIT_STATE][UNSUB_OPTIONS_UPDATE_LISTENER])
        == listeners_length
    )


@mock.patch(
    GET_INTEGRATIONS_MOCK_REFERENCE,
    mock.Mock(side_effect=mocked_integration),
)
async def test_config_flow_init(hass: HomeAssistant, form_data) -> None:
    """Test if we can configure the integration via config flow."""
    create_entity(hass, SENSOR_DOMAIN, OutputTypes.GO_E.value, "charger1_name")
    result_init = await _initialize_and_assert_flow(hass)

    # submit the form
    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        form_data,
    )
    await hass.async_block_till_done()

    assert result_configure["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result_configure["title"] == "charger1"
    assert result_configure["data"] == CONFIG_FLOW_EXPECTED_RESULT

    data = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"]
    expected_data = CONFIG_FLOW_EXPECTED_MAIN_STATE[CONF_CONSUMERS]["charger1"]
    _assert_state(hass, data, expected_data)


@mock.patch(
    GET_INTEGRATIONS_MOCK_REFERENCE,
    mock.Mock(side_effect=mocked_integration),
)
async def test_config_flow_init_merge(
    hass: HomeAssistant, form_data_changed, consumer
) -> None:
    """Config flow configuration is properly merged with the initial configuration."""
    create_entity(hass, SENSOR_DOMAIN, OutputTypes.GO_E.value, "charger1_name")
    create_entity(hass, SENSOR_DOMAIN, OutputTypes.GO_E.value, "charger2_name")

    # create first assignment via main configuration flow (configuration.yaml)
    assert await async_setup(
        hass,
        {
            DOMAIN: {
                CONF_CONSUMERS: [[consumer]],
            }
        },
    )
    await hass.async_block_till_done()

    data = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger1"]
    expected_data = EXPECTED_MAIN_STATE[CONF_CONSUMERS]["charger1"]
    _assert_state(hass, data, expected_data, listeners_length=0)

    # create second assignment via config flow -> data should be correctly merged
    result_init = await _initialize_and_assert_flow(hass)

    # submit the form
    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        form_data_changed,
    )
    await hass.async_block_till_done()

    assert result_configure["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result_configure["title"] == "charger2"
    assert result_configure["data"] == OPTIONS_FLOW_EXPECTED_RESULT

    data2 = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger2"]
    expected_data2 = OPTIONS_FLOW_EXPECTED_MAIN_STATE[CONF_CONSUMERS]["charger2"]
    _assert_state(hass, data2, expected_data2)


@mock.patch(
    GET_INTEGRATIONS_MOCK_REFERENCE,
    mock.Mock(side_effect=mocked_integration),
)
async def test_options_flow_init(
    hass: HomeAssistant,
    form_data,
    form_data_changed,
) -> None:
    """Test if we can re-configure the integration via options flow."""
    create_entity(hass, SENSOR_DOMAIN, OutputTypes.GO_E.value, "charger2_name")
    result_init = await _initialize_and_assert_options(
        hass, form_data | {CONF_OUTPUT_SOURCE_INTEGRATION: OutputTypes.GO_E.value}
    )

    # submit the form
    result_configure = await hass.config_entries.options.async_configure(
        result_init["flow_id"],
        form_data_changed,
    )
    await hass.async_block_till_done()

    assert result_configure["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result_configure["title"] == "charger2"
    assert result_configure["data"] == OPTIONS_FLOW_EXPECTED_RESULT

    # check state
    data = hass.data[DOMAIN][MAIN_COORDINATOR_NAME].data[CONF_CONSUMERS]["charger2"]
    expected_data = OPTIONS_FLOW_EXPECTED_MAIN_STATE[CONF_CONSUMERS]["charger2"]
    _assert_state(hass, data, expected_data)
