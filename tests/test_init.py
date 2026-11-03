"""Tests for the PZEM integration setup and unload."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.pzem_014_016.const import (
    CONF_BAUDRATE,
    DEFAULT_NAME,
    DOMAIN,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from custom_components.pzem_014_016.coordinator import PzemRuntimeData

from . import MOCK_ENTRY_DATA, MOCK_SERIAL_ENTRY_DATA

VOLTAGE = "sensor.pzem_voltage"


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads with runtime_data populated."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, PzemRuntimeData)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("data", "expected_params"),
    [
        pytest.param(
            {**MOCK_ENTRY_DATA, CONF_PORT: 1502},
            ModbusTcpParams(host="192.168.1.100", port=1502),
            id="tcp",
        ),
        pytest.param(
            {**MOCK_SERIAL_ENTRY_DATA, CONF_BAUDRATE: 19200},
            ModbusSerialParams(device="/dev/ttyUSB0", baudrate=19200),
            id="serial",
        ),
    ],
)
async def test_setup_connects_over_the_configured_link(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: MagicMock,
    data: dict[str, Any],
    expected_params: ModbusSerialParams | ModbusTcpParams,
) -> None:
    """Test setup opens the link the entry is configured for."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, title=DEFAULT_NAME)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_get_unit.assert_called_once_with(hass, entry, expected_params, 1)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModbusTimeoutError("asleep"), id="silent"),
        pytest.param(ModbusConnectionError("gone"), id="link_lost"),
    ],
)
async def test_setup_retries_when_the_meter_does_not_answer(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test an unreachable meter leaves the entry to retry."""
    mock_connection.for_unit(1).fail_requests(error)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_sensors_follow_the_meter_through_an_outage(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable while the meter is silent and recover."""
    unit = mock_connection.for_unit(1)
    assert hass.states.get(VOLTAGE).state == "230.1"

    unit.fail_requests(ModbusTimeoutError("asleep"))
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(VOLTAGE).state == STATE_UNAVAILABLE

    unit.fail_requests(None)
    unit.input[0] = 2412
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(VOLTAGE).state == "241.2"


async def test_setup_retries_when_the_meter_refuses_its_registers(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a meter that answers but serves nothing leaves the entry to retry."""
    mock_connection.for_unit(1).fail_read(
        0, IllegalDataAddressError(0), register_type="input"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_settings_failure_does_not_stop_the_measurements(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a meter that refuses its holding registers still reports readings."""
    mock_connection.for_unit(1).fail_read(
        1, IllegalDataAddressError(0), register_type="holding"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(VOLTAGE).state == "230.1"
    assert (
        hass.states.get("number.pzem_power_alarm_threshold").state == STATE_UNAVAILABLE
    )


async def test_settings_are_polled_less_often(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the settings are not read with every measurement."""
    runtime_data = init_integration.runtime_data
    assert runtime_data.readings.update_interval == timedelta(seconds=SCAN_INTERVAL)
    assert runtime_data.settings.update_interval == timedelta(
        seconds=SETTINGS_SCAN_INTERVAL
    )
