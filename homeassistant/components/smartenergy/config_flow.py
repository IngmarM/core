"""Smart Energy config flow and options flow setup."""

from typing import Any, Literal

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.loader import Integration, async_get_integrations

from .const import (
    CONF_INPUT_SOURCE,
    CONF_OUTPUT_SOURCE,
    CONF_OUTPUT_SOURCE_INTEGRATION,
    CONF_SMART_ENERGY_MODE,
    DOMAIN,
    SIMPLE,
)
from .controller import INPUT_TYPES, OUTPUT_TYPES
from .entity import filter_entities_by_integration

SMART_ENERGY_MODE_OPTIONS: list[str] = [SIMPLE]


async def _get_registered_integrations(
    hass: HomeAssistant, integrations_to_filter: list[Any]
) -> list[Any]:
    """Check Home Assistant if the provided integrations are installed or not.

    Filter out those that are not installed.
    """
    matched_integrations = await async_get_integrations(hass, integrations_to_filter)
    # take only installed integrations
    registered_integrations = list(
        filter(
            lambda integration: (
                integration in matched_integrations
                and isinstance(matched_integrations[integration], Integration)
            ),
            integrations_to_filter,
        )
    )

    return registered_integrations


async def _get_config_schema(
    hass: HomeAssistant, default_values: dict
) -> tuple[dict, vol.Schema]:
    """Get form data schema and entities mapped to the parent integrations."""
    # find installed integrations
    registered_input_integrations = await _get_registered_integrations(
        hass,
        INPUT_TYPES,
    )
    registered_output_integrations = await _get_registered_integrations(
        hass,
        list(OUTPUT_TYPES.keys()),
    )

    # get core entity names for installed integrations and mapping between them. For example:
    # smartenergy_goecharger: charger1
    integration_entity_map, input_options = filter_entities_by_integration(
        hass, registered_output_integrations
    )

    return integration_entity_map, vol.Schema(
        {
            vol.Required(
                CONF_INPUT_SOURCE, default=default_values.get(CONF_INPUT_SOURCE, None)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=registered_input_integrations,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_OUTPUT_SOURCE, default=default_values.get(CONF_OUTPUT_SOURCE, None)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=input_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_SMART_ENERGY_MODE,
                default=default_values.get(CONF_SMART_ENERGY_MODE, None),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SMART_ENERGY_MODE_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class SmartEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Smart Energy component."""

    VERSION: Literal[1] = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return SmartEnergyOptionsFlowHandler(config_entry)

    def extend_user_input_with_meta(
        self, user_input: dict, integration_sensor_map: dict
    ) -> dict:
        """Extend provided form data with meta data.

        - output source integration name - for example: smartenergy_goecharger.
        """

        integration_name = None

        for key, value in integration_sensor_map.items():
            if user_input[CONF_OUTPUT_SOURCE] in value:
                integration_name = key
                break

        return user_input | {CONF_OUTPUT_SOURCE_INTEGRATION: integration_name}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        _, data_schema = await _get_config_schema(self.hass, {})

        if user_input is not None:
            # set default values to the current so the user is still within the same context,
            # otherwise it makes each input empty
            integration_sensor_map, data_schema = await _get_config_schema(
                self.hass, user_input
            )

            return self.async_create_entry(
                title=user_input[CONF_OUTPUT_SOURCE],
                data=self.extend_user_input_with_meta(
                    user_input, integration_sensor_map
                ),
                options=self.extend_user_input_with_meta(
                    user_input, integration_sensor_map
                ),
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=None,
        )


class SmartEnergyOptionsFlowHandler(OptionsFlow):
    """Config flow options handler for Smart Energy."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry: ConfigEntry = config_entry
        self.options: dict[str, Any] = dict(config_entry.options)

    def extend_user_input_with_meta(
        self, user_input: dict, integration_sensor_map: dict
    ) -> dict:
        """Extend provided form data with meta data.

        - output source integration name - for example: smartenergy_goecharger.
        """

        integration_name = None

        for key, value in integration_sensor_map.items():
            if user_input[CONF_OUTPUT_SOURCE] in value:
                integration_name = key
                break

        return user_input | {CONF_OUTPUT_SOURCE_INTEGRATION: integration_name}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        options = self.config_entry.options
        _, data_schema = await _get_config_schema(
            self.hass,
            {
                CONF_INPUT_SOURCE: options.get(CONF_INPUT_SOURCE),
                CONF_OUTPUT_SOURCE: options.get(CONF_OUTPUT_SOURCE),
                CONF_SMART_ENERGY_MODE: options.get(CONF_SMART_ENERGY_MODE),
            },
        )

        if user_input is not None:
            # set default values to the current so the user is still within the same context,
            # otherwise it makes each input empty
            integration_sensor_map, data_schema = await _get_config_schema(
                self.hass, user_input
            )

            return self.async_create_entry(
                title=user_input[CONF_OUTPUT_SOURCE],
                data=self.extend_user_input_with_meta(
                    user_input, integration_sensor_map
                ),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=None,
        )
