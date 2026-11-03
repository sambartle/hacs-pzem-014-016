"""Tests for the PZEM diagnostics."""

from homeassistant.core import HomeAssistant
from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot


async def test_diagnostics_meter_unreachable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics still download when the meter stops answering."""
    mock_connection.for_unit(1).fail_requests(ModbusConnectionError("gone"))

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["read_error"] == "ModbusConnectionError"
    assert diag["raw"] is None
