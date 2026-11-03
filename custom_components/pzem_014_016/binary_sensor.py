"""Support for PZEM binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PzemConfigEntry, PzemDataUpdateCoordinator
from .entity import PzemEntity
from .pzem_014_016_modbus import Measurements

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PzemBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a PZEM binary sensor."""

    value_fn: Callable[[Measurements], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[PzemBinarySensorDescription, ...] = (
    PzemBinarySensorDescription(
        key="power_alarm",
        translation_key="power_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda measurements: measurements.power_alarm,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PzemConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PZEM binary sensor platform."""
    coordinator = entry.runtime_data.readings
    async_add_entities(
        PzemBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class PzemBinarySensor(PzemEntity, BinarySensorEntity):
    """Defines a PZEM binary sensor."""

    entity_description: PzemBinarySensorDescription

    def __init__(
        self,
        coordinator: PzemDataUpdateCoordinator,
        description: PzemBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the meter is alarming."""
        return self.entity_description.value_fn(self.coordinator.device.measurements)
