"""Helpers for the PZEM integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import CONF_BAUDRATE, CONF_UNIT_ID, TYPE_SERIAL


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def create_unique_id(data: Mapping[str, Any]) -> str:
    """
    Name a meter by the link it is reached over and its unit ID.

    The meter reports no serial number, so where it sits on the bus is all
    that identifies it. The link settings that do not move the meter, like the
    baud rate, are left out: two entries differing only in them would fight
    over one device.
    """
    endpoint = "/".join(str(part) for part in create_modbus_params(data).endpoint)
    return f"{endpoint}/{data[CONF_UNIT_ID]}"
