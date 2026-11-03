"""
The PZEM-014/016 integration, with its device library vendored.

For more details about this integration, please refer to
https://github.com/sambartle/hacs-pzem-014-016
"""

from datetime import timedelta

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID, SCAN_INTERVAL, SETTINGS_SCAN_INTERVAL
from .coordinator import PzemConfigEntry, PzemDataUpdateCoordinator, PzemRuntimeData
from .helpers import create_modbus_params
from .pzem_014_016_modbus import PzemMeter

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PzemConfigEntry) -> bool:
    """Set up PZEM from a config entry."""
    unit = async_get_unit(
        hass,
        entry,
        create_modbus_params(entry.data),
        entry.data[CONF_UNIT_ID],
    )
    device = PzemMeter(unit)
    readings = PzemDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    settings = PzemDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    await readings.async_config_entry_first_refresh()
    # A meter that will not serve its settings still reports its measurements.
    await settings.async_refresh()
    entry.runtime_data = PzemRuntimeData(readings, settings)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PzemConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
