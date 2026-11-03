"""What the meter has been configured to do."""

from __future__ import annotations

from typing import Any

from modbus_connection.model import integer

from .model import PzemSettingsComponent

# The Modbus-RTU address range the meter accepts; 0 is the broadcast address
# and 0xF8 is reserved for single-slave calibration.
MIN_ADDRESS = 1
MAX_ADDRESS = 0xF7
# One register holds the alarm threshold, in watts.
MAX_ALARM_THRESHOLD = 0xFFFF


def _in_range(low: int, high: int, what: str) -> Any:
    """A write validator rejecting anything outside ``low`` to ``high``."""

    def validate(value: Any) -> int:
        number = int(value)
        if not low <= number <= high:
            raise ValueError(f"{what} must be {low} to {high}, got {value}")
        return number

    return validate


class Settings(PzemSettingsComponent):
    """The power alarm threshold and the meter's own Modbus address."""

    register_ranges = ((1, 2),)

    power_alarm_threshold = integer(
        1,
        signed=False,
        unit="W",
        writable=_in_range(0, MAX_ALARM_THRESHOLD, "the alarm threshold"),
    )
    modbus_address = integer(
        2,
        signed=False,
        writable=_in_range(MIN_ADDRESS, MAX_ADDRESS, "the Modbus address"),
    )

    async def async_write_power_alarm_threshold(self, watts: int) -> None:
        """Set the active power, in watts, above which the meter alarms.

        Raises ``ValueError`` outside 0 to 65535.
        """
        await self.write("power_alarm_threshold", watts)

    async def async_write_modbus_address(self, address: int) -> None:
        """Move the meter to another Modbus address, 1 to 247.

        The meter answers on the new address from then on, so the unit this
        component reads through no longer reaches it: build a new unit for the
        new address. Raises ``ValueError`` outside the range.
        """
        await self.write("modbus_address", address)
