"""Diagnostics support for PZEM."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusError

from .coordinator import PzemConfigEntry

TO_REDACT = {CONF_DEVICE, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PzemConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.readings.device
    raw = read_error = None
    try:
        raw = await device.async_read_raw()
    except ModbusError as err:
        read_error = type(err).__name__

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "connected": device.connected,
        "read_error": read_error,
        "raw": raw,
    }
