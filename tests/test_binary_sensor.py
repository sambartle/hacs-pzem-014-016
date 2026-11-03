"""Tests for the PZEM binary sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.pzem_014_016.const import SCAN_INTERVAL

ALARM = "binary_sensor.pzem_power_alarm"


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: object,
) -> None:
    """Test every binary sensor against its snapshot."""
    with patch("custom_components.pzem_014_016.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_alarm_follows_the_meter(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the alarm turns on when the meter sets it, and unknown is unknown."""
    unit = mock_connection.for_unit(1)
    assert hass.states.get(ALARM).state == STATE_OFF

    for register, state in ((0xFFFF, STATE_ON), (0x0001, STATE_UNKNOWN)):
        unit.input[9] = register
        freezer.tick(timedelta(seconds=SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(ALARM).state == state
