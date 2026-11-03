"""The top-level object for a meter."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from modbus_connection.model import Device, Raw

from .measurements import Measurements
from .model import UpdateReport
from .settings import Settings

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# What each kind of poll reads, by attribute name.
READING_COMPONENTS: tuple[str, ...] = ("measurements",)
SETTING_COMPONENTS: tuple[str, ...] = ("settings",)


class PzemMeter(Device):
    """A meter reached through a ``ModbusUnit``."""

    def __init__(self, unit: ModbusUnit, *, timeout: float | None = None) -> None:
        super().__init__(unit)
        unit.require_timeout(timeout)
        self.measurements = Measurements(unit)
        self.settings = Settings(unit)

    @property
    def connected(self) -> bool:
        """Whether the link to the meter is open."""
        return self.modbus_unit.connected

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the meter measures.

        A dead link (``ModbusConnectionError``) raises, and so does a timeout:
        a meter that is not answering has nothing to report. Any other
        failure is listed in the returned report and keeps the previous values.
        """
        return await self.async_poll(READING_COMPONENTS)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh what the meter has been configured to do.

        These registers change only when something writes them, so this is
        for a slow cadence and for reading a write back. It fails like
        ``async_update_readings``.
        """
        return await self.async_poll(SETTING_COMPONENTS)

    async def async_update(self) -> UpdateReport:
        """Refresh the measurements and the settings, in one merged report."""
        report = await self.async_update_readings()
        return await self.async_poll(SETTING_COMPONENTS, report)

    async def async_read_raw(self, names: Iterable[str] | None = None) -> Raw:
        """Every register this meter reads, undecoded, for an issue report.

        Nothing notifies here: a dump is not a poll.
        """
        return await super().async_read_raw(
            (*READING_COMPONENTS, *SETTING_COMPONENTS) if names is None else names
        )
