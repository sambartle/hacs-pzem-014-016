"""Data update coordinators for PZEM meters."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError

from .const import DOMAIN
from .pzem_014_016_modbus import PzemMeter, UpdateReport

_LOGGER = logging.getLogger(__name__)


class PzemDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Class to manage fetching one kind of PZEM data."""

    config_entry: PzemConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PzemConfigEntry,
        device: PzemMeter,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )
        return report


@dataclass
class PzemRuntimeData:
    """Class to hold runtime data."""

    readings: PzemDataUpdateCoordinator
    settings: PzemDataUpdateCoordinator


type PzemConfigEntry = ConfigEntry[PzemRuntimeData]
