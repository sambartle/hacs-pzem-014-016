"""The meter's live measurements."""

from __future__ import annotations

from modbus_connection.model import gauge, uint32

from .model import PzemComponent, alarm_status


class Measurements(PzemComponent):
    """Voltage, current, power, energy, frequency, power factor and alarm.

    Ten consecutive input registers, 0 to 9, read in a single request. The
    three 32-bit values (current, power and energy) send their low word first.
    """

    # Everything the meter serves in this space.
    register_ranges = ((0, 9),)

    voltage = gauge(0, 0.1, signed=False, unit="V")
    current = uint32(1, scale=0.001, word_order="little", unit="A")
    power = uint32(3, scale=0.1, word_order="little", unit="W")
    energy = uint32(5, word_order="little", unit="Wh")
    frequency = gauge(7, 0.1, signed=False, unit="Hz")
    power_factor = gauge(8, 0.01, signed=False)
    power_alarm = alarm_status(9)
    """Whether the active power is above the alarm threshold."""
