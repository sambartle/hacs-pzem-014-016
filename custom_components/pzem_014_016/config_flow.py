"""Config flow for PZEM meters."""

import logging
from collections.abc import Mapping
from typing import Any, override

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from modbus_connection import ModbusError, ModbusTimeoutError

from .const import (
    CONF_BAUDRATE,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params, create_unique_id
from .pzem_014_016_modbus import PzemMeter

_LOGGER = logging.getLogger(__name__)

STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)

STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
            NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)


class _MeterSilentError(Exception):
    """The adapter is reachable, but the meter behind it is not answering."""


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Connect to the meter and read it once, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        try:
            report = await PzemMeter(unit).async_update_readings()
        except ModbusTimeoutError as err:
            if unit.connected:
                raise _MeterSilentError from err
            raise
    if not report.updated:
        raise ExceptionGroup(
            "the meter refused its registers", list(report.failed.values())
        )


class PzemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a PZEM config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the meter is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_SERIAL, TYPE_TCP]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a meter reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a meter reached over a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then read the meter behind them."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            await self.async_set_unique_id(create_unique_id(data))
            self._abort_if_unique_id_configured()
            errors, description_placeholders = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        return self.async_show_form(
            step_id=connection_type,
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the meter is reached from now on."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL],
        )

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this meter over the network from now on."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this meter over a serial port from now on."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_reconfigure_link(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then read the meter behind them."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            unique_id = create_unique_id(data)
            other = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            if other is not None and other.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")

            # One connection cannot carry two sets of link settings, so the
            # entry lets go of its own before the new ones are tried.
            relinking = False
            if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
                current = create_modbus_params(entry.data)
                new = create_modbus_params(data)
                if new.endpoint == current.endpoint and new != current:
                    relinking = await self.hass.config_entries.async_unload(
                        entry.entry_id
                    )

            errors, description_placeholders = await self._async_validate(data)
            if errors and relinking:
                await self.hass.config_entries.async_setup(entry.entry_id)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data=data
                )

        suggested = user_input or (
            entry.data
            if entry.data.get(CONF_TYPE) == connection_type
            else {CONF_UNIT_ID: entry.data[CONF_UNIT_ID]}
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Read the meter, returning the errors to show if it cannot be read."""
        try:
            await _async_probe(self.hass, data)
        except _MeterSilentError:
            return {"base": "meter_silent"}, {}
        except (ModbusError, HomeAssistantError, ExceptionGroup) as err:
            return {"base": "cannot_connect"}, {"error": str(err)}
        return {}, {}
