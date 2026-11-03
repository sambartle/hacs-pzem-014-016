"""Support for PZEM sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PzemConfigEntry, PzemDataUpdateCoordinator
from .entity import PzemEntity
from .pzem_014_016_modbus import Measurements

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PzemSensorDescription(SensorEntityDescription):
    """Describe a PZEM sensor."""

    value_fn: Callable[[Measurements], StateType]


SENSOR_DESCRIPTIONS: tuple[PzemSensorDescription, ...] = (
    PzemSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda measurements: measurements.voltage,
    ),
    PzemSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda measurements: measurements.current,
    ),
    PzemSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda measurements: measurements.power,
    ),
    PzemSensorDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda measurements: measurements.energy,
    ),
    PzemSensorDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda measurements: measurements.frequency,
    ),
    PzemSensorDescription(
        key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda measurements: measurements.power_factor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PzemConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PZEM sensor platform."""
    coordinator = entry.runtime_data.readings
    async_add_entities(
        PzemSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class PzemSensor(PzemEntity, SensorEntity):
    """Defines a PZEM sensor."""

    entity_description: PzemSensorDescription

    def __init__(
        self,
        coordinator: PzemDataUpdateCoordinator,
        description: PzemSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor's value."""
        return self.entity_description.value_fn(self.coordinator.device.measurements)
