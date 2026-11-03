"""The component bases the meter's register map builds on."""

from __future__ import annotations

from modbus_connection.model import (
    Component,
    NumberField,
    RegisterSpace,
    UpdateReport,
)

__all__ = ["PzemComponent", "PzemSettingsComponent", "UpdateReport", "alarm_status"]

# What the meter reports in the alarm register: all bits set, or none.
_ALARM = {0x0000: False, 0xFFFF: True}


def alarm_status(address: int) -> NumberField[bool]:
    """A register holding 0xFFFF for an alarm and 0x0000 for none, as ``bool``."""
    return NumberField(address, signed=False, convert=_ALARM)


class PzemComponent(Component):
    """A sub-system of the meter's register map.

    The meter publishes its measurements as input registers (function code 4),
    so a component reads from that space unless it says otherwise.
    """

    register_space: RegisterSpace = "input"


class PzemSettingsComponent(PzemComponent):
    """A sub-system the meter has been configured with.

    Settings are holding registers (function code 3), changed with function
    code 6, so they refresh separately from the measurements.
    """

    register_space: RegisterSpace = "holding"
