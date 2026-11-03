"""Tests for the PZEM sensor platform."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: object,
) -> None:
    """Test every sensor against its snapshot."""
    with patch("custom_components.pzem_014_016.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test each sensor reports the meter's reading in its own unit."""
    expected = {
        "sensor.pzem_voltage": ("230.1", "V"),
        "sensor.pzem_current": ("12.345", "A"),
        "sensor.pzem_power": ("1234.5", "W"),
        "sensor.pzem_energy": ("70.0", "kWh"),
        "sensor.pzem_frequency": ("50.0", "Hz"),
        "sensor.pzem_power_factor": ("0.98", None),
    }
    for entity_id, (state, unit) in expected.items():
        found = hass.states.get(entity_id)
        assert found is not None, entity_id
        assert found.state == state, entity_id
        assert found.attributes.get("unit_of_measurement") == unit, entity_id
