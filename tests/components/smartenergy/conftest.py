"""Tests helpers."""

import pytest


@pytest.fixture
def form_data() -> dict[str, str | int]:
    """Smart Energy configuration."""
    return {
        "input_source": "smartenergy_awattar",
        "output_source": "charger1",
        "smart_energy_mode": "simple",
    }


@pytest.fixture
def form_data_changed() -> dict[str, str | int]:
    """Smart Energy configuration."""
    return {
        "input_source": "smartenergy_awattar",
        "output_source": "charger2",
        "smart_energy_mode": "simple",
    }


@pytest.fixture
def consumer() -> dict[str, str | int]:
    """Smart Energy configuration."""
    return {
        "name": "charger1",
        "output_source": "smartenergy_goecharger",
        "input_source": "smartenergy_awattar",
        "smart_energy_mode": "simple",
    }
