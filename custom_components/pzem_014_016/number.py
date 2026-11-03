"""Support for PZEM numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from modbus_connection import ModbusError

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import PzemConfigEntry, PzemDataUpdateCoordinator
from .entity import PzemEntity
from .helpers import create_unique_id
from .pzem_014_016_modbus import MAX_ADDRESS, MIN_ADDRESS, Settings

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PzemNumberDescription(NumberEntityDescription):
    """Describe a PZEM number."""

    value_fn: Callable[[Settings], int | None]
    set_fn: Callable[[Settings, int], Awaitable[None]]


ALARM_THRESHOLD_DESCRIPTION = PzemNumberDescription(
    key="power_alarm_threshold",
    translation_key="power_alarm_threshold",
    device_class=NumberDeviceClass.POWER,
    entity_category=EntityCategory.CONFIG,
    native_unit_of_measurement=UnitOfPower.WATT,
    native_min_value=0,
    native_max_value=65535,
    native_step=1,
    mode=NumberMode.BOX,
    value_fn=lambda settings: settings.power_alarm_threshold,
    set_fn=lambda settings, value: settings.async_write_power_alarm_threshold(value),
)

MODBUS_ADDRESS_DESCRIPTION = PzemNumberDescription(
    key="modbus_address",
    translation_key="modbus_address",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    native_min_value=MIN_ADDRESS,
    native_max_value=MAX_ADDRESS,
    native_step=1,
    mode=NumberMode.BOX,
    value_fn=lambda settings: settings.modbus_address,
    set_fn=lambda settings, value: settings.async_write_modbus_address(value),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PzemConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PZEM number platform."""
    coordinator = entry.runtime_data.settings
    async_add_entities(
        [
            PzemNumber(coordinator, ALARM_THRESHOLD_DESCRIPTION),
            PzemAddressNumber(coordinator, MODBUS_ADDRESS_DESCRIPTION),
        ]
    )


class PzemNumber(PzemEntity, NumberEntity):
    """Defines a PZEM number."""

    entity_description: PzemNumberDescription

    def __init__(
        self,
        coordinator: PzemDataUpdateCoordinator,
        description: PzemNumberDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, description)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the setting's value."""
        return self.entity_description.value_fn(self.coordinator.device.settings)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the setting to the meter."""
        try:
            await self.entity_description.set_fn(
                self.coordinator.device.settings, int(value)
            )
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err
        await self.coordinator.async_request_refresh()


class PzemAddressNumber(PzemNumber):
    """The meter's own Modbus address, which the config entry has to follow."""

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Move the meter to another address, and the entry with it."""
        entry = self.coordinator.config_entry
        data = {**entry.data, CONF_UNIT_ID: int(value)}
        unique_id = create_unique_id(data)
        other = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, unique_id
        )
        if other is not None and other.entry_id != entry.entry_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="address_in_use",
                translation_placeholders={"address": str(int(value))},
            )

        try:
            await self.entity_description.set_fn(
                self.coordinator.device.settings, int(value)
            )
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err

        # The meter no longer answers on the old address, so the entry follows
        # it and reloads to build a unit for the new one.
        self.hass.config_entries.async_update_entry(
            entry, data=data, unique_id=unique_id
        )
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
