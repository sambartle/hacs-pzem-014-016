"""Tests for the PZEM integration."""

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection.mock import MockModbusUnit

from custom_components.pzem_014_016.const import (
    CONF_BAUDRATE,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    TYPE_SERIAL,
    TYPE_TCP,
)

MOCK_TCP_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}
MOCK_ENTRY_DATA = {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT}

MOCK_SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: DEFAULT_BAUDRATE,
    CONF_UNIT_ID: 1,
}
MOCK_SERIAL_ENTRY_DATA = {CONF_TYPE: TYPE_SERIAL, **MOCK_SERIAL_INPUT}


def seed_meter(unit: MockModbusUnit) -> None:
    """Seed a meter reading 230.1 V and 1234.5 W, alarming above 2300 W."""
    unit.input[0] = 2301  # voltage -> 230.1 V
    unit.input[1] = [12345, 0]  # current -> 12.345 A
    unit.input[3] = [12345, 0]  # power -> 1234.5 W
    unit.input[5] = [4464, 1]  # energy -> 70000 Wh
    unit.input[7] = 500  # frequency -> 50.0 Hz
    unit.input[8] = 98  # power factor -> 0.98
    unit.input[9] = 0  # alarm status -> no alarm
    unit.holding[1] = 2300  # power alarm threshold -> 2300 W
    unit.holding[2] = 1  # Modbus address
