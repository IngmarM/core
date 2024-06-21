"""Output controller for the supported devices for Smart Energy.

Here you can configure which integrations can be used as the output(consumer) source.
"""

from enum import Enum
import logging

from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)


class InputTypes(str, Enum):
    """List of supported input integrations."""

    AWATTAR = "smartenergy_awattar"


class OutputTypes(str, Enum):
    """List of supported output(consumer) devices/integrations."""

    GO_E = "smartenergy_goecharger"


OUTPUT_TYPES = {
    OutputTypes.GO_E: {
        "domain": OutputTypes.GO_E.value,
        "start": "start_charging",
        "stop": "stop_charging",
    }
}

INPUT_TYPES: list[str] = [InputTypes.AWATTAR.value]


async def start_charging(hass: HomeAssistant, output_type: str, data: dict) -> None:
    """Start charging (call a Home Assistant service) of a supported device.

    Currently supported devices:
    - smartenergy_goecharger.
    """

    match output_type:  # noqa: E999
        case OutputTypes.GO_E:
            await hass.services.async_call(
                OUTPUT_TYPES[output_type]["domain"],
                OUTPUT_TYPES[output_type]["start"],
                data,
                blocking=True,
            )
        case _:
            _LOGGER.error(
                "Can't start charging, %s is not a supported device", output_type
            )


async def stop_charging(hass: HomeAssistant, output_type: str, data: dict) -> None:
    """Stop charging (call a Home Assistant service) of a supported device.

    Currently supported devices:
    - smartenergy_goecharger.
    """

    match output_type:  # noqa: E999
        case OutputTypes.GO_E:
            await hass.services.async_call(
                OUTPUT_TYPES[output_type]["domain"],
                OUTPUT_TYPES[output_type]["stop"],
                data,
                blocking=True,
            )
        case _:
            _LOGGER.error(
                "Can't stop charging, %s is not a supported device", output_type
            )
