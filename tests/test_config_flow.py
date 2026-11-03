"""Tests for the PZEM config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, _patch, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import (
    IllegalDataAddressError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pzem_014_016.config_flow import (
    STEP_RECONFIGURE_SERIAL,
    STEP_RECONFIGURE_TCP,
)
from custom_components.pzem_014_016.const import (
    CONF_BAUDRATE,
    DEFAULT_NAME,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from custom_components.pzem_014_016.helpers import create_unique_id

from . import (
    MOCK_ENTRY_DATA,
    MOCK_SERIAL_ENTRY_DATA,
    MOCK_SERIAL_INPUT,
    MOCK_TCP_INPUT,
    seed_meter,
)


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "custom_components.pzem_014_016.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


async def _start_flow(hass: HomeAssistant, connection_type: str) -> str:
    """Open the flow, pick a connection type, and return the flow ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == [TYPE_SERIAL, TYPE_TCP]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == connection_type
    assert result["errors"] == {}

    return result["flow_id"]


@pytest.mark.parametrize(
    ("connection_type", "user_input", "expected_params", "expected_data"),
    [
        pytest.param(
            TYPE_TCP,
            {**MOCK_TCP_INPUT, CONF_PORT: 1502},
            ModbusTcpParams(host="192.168.1.100", port=1502),
            {**MOCK_ENTRY_DATA, CONF_PORT: 1502},
            id="tcp",
        ),
        pytest.param(
            TYPE_SERIAL,
            {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200},
            ModbusSerialParams(device="/dev/ttyUSB0", baudrate=19200),
            {**MOCK_SERIAL_ENTRY_DATA, CONF_BAUDRATE: 19200},
            id="serial",
        ),
    ],
)
async def test_user_step_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_connection: MockModbusConnection,
    connection_type: str,
    user_input: dict[str, Any],
    expected_params: ModbusSerialParams | ModbusTcpParams,
    expected_data: dict[str, Any],
) -> None:
    """Test each connection type reads the meter and creates an entry."""
    flow_id = await _start_flow(hass, connection_type)

    with _patch_temporary_unit(mock_connection) as mock_temporary_unit:
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    mock_temporary_unit.assert_called_once_with(hass, expected_params, 1)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == expected_data
    assert result["result"].unique_id == create_unique_id(expected_data)
    assert len(mock_setup_entry.mock_calls) == 1
    # The probe is a single poll of the meter.
    assert len(mock_connection.for_unit(1).read_events) == 1


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test the same meter cannot be set up twice, even at another baud rate."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _seed_unreachable(connection: MockModbusConnection) -> None:
    """No adapter answers, so the link never opens."""
    connection._connect_client = AsyncMock(side_effect=ModbusTimeoutError("stuck"))


def _seed_silent(connection: MockModbusConnection) -> None:
    """The adapter answers, but the meter behind it does not."""
    connection.for_unit(1).fail_requests(ModbusTimeoutError("asleep"))


def _seed_refused(connection: MockModbusConnection) -> None:
    """The meter answers, but refuses its registers."""
    connection.for_unit(1).fail_read(
        0, IllegalDataAddressError(0), register_type="input"
    )


@pytest.mark.parametrize(
    ("seed", "error"),
    [
        pytest.param(_seed_unreachable, "cannot_connect", id="unreachable"),
        pytest.param(_seed_silent, "meter_silent", id="silent"),
        pytest.param(_seed_refused, "cannot_connect", id="refused"),
    ],
)
async def test_user_step_errors_then_recovers(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Any,
    error: str,
) -> None:
    """Test each failure is shown on the form, and the flow completes after it."""
    broken = MockModbusConnection()
    seed_meter(broken.for_unit(1))
    seed(broken)
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(broken):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    healthy = MockModbusConnection()
    seed_meter(healthy.for_unit(1))
    with _patch_temporary_unit(healthy):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_link_conflict(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a HomeAssistantError from the shared connection is shown."""
    flow_id = await _start_flow(hass, TYPE_TCP)

    with patch(
        "custom_components.pzem_014_016.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError("in use at another baud rate"),
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {
        "error": "in use at another baud rate"
    }


async def _start_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, step: str
) -> str:
    """Open the reconfigure flow, pick a link type, and return the flow ID."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result["flow_id"]


async def test_reconfigure_to_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: Any,
) -> None:
    """Test moving a meter to a serial port keeps the entry."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_reconfigure(hass, mock_config_entry, STEP_RECONFIGURE_SERIAL)

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            flow_id, MOCK_SERIAL_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == MOCK_SERIAL_ENTRY_DATA
    assert mock_config_entry.unique_id == create_unique_id(MOCK_SERIAL_ENTRY_DATA)


async def test_reconfigure_error_keeps_the_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: Any,
) -> None:
    """Test a link that cannot reach the meter leaves the entry as it was."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_reconfigure(hass, mock_config_entry, STEP_RECONFIGURE_TCP)
    silent = MockModbusConnection()
    _seed_silent(silent)

    with _patch_temporary_unit(silent):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**MOCK_TCP_INPUT, CONF_PORT: 1502}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "meter_silent"}
    assert mock_config_entry.data == MOCK_ENTRY_DATA


async def test_reconfigure_onto_another_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: Any,
) -> None:
    """Test a meter cannot be moved onto a link another entry already holds."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id=create_unique_id(MOCK_SERIAL_ENTRY_DATA),
        data=MOCK_SERIAL_ENTRY_DATA,
        title=DEFAULT_NAME,
    )
    other.add_to_hass(hass)
    flow_id = await _start_reconfigure(hass, mock_config_entry, STEP_RECONFIGURE_SERIAL)

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            flow_id, MOCK_SERIAL_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == MOCK_ENTRY_DATA


async def test_reconfigure_baud_rate_releases_the_link_first(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: Any,
) -> None:
    """Test a new baud rate on a held link unloads the entry before probing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=create_unique_id(MOCK_SERIAL_ENTRY_DATA),
        data=MOCK_SERIAL_ENTRY_DATA,
        title=DEFAULT_NAME,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    flow_id = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)

    seen: list[config_entries.ConfigEntryState] = []

    def _record_state(*args: Any) -> None:
        seen.append(entry.state)

    with (
        _patch_temporary_unit(mock_connection),
        patch(
            "custom_components.pzem_014_016.config_flow._async_probe",
            side_effect=_record_state,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )

    assert seen == [config_entries.ConfigEntryState.NOT_LOADED]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_DEVICE] == "/dev/ttyUSB0"
    assert entry.data[CONF_BAUDRATE] == 19200


async def test_reconfigure_failure_restores_the_unloaded_entry(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: Any,
) -> None:
    """Test a failed baud rate change sets the entry back up as it was."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=create_unique_id(MOCK_SERIAL_ENTRY_DATA),
        data=MOCK_SERIAL_ENTRY_DATA,
        title=DEFAULT_NAME,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flow_id = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)
    silent = MockModbusConnection()
    _seed_silent(silent)

    with _patch_temporary_unit(silent):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "meter_silent"}
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.data == MOCK_SERIAL_ENTRY_DATA
