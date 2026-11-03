"""Tests for the PZEM number platform."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.pzem_014_016.const import CONF_UNIT_ID, DOMAIN
from custom_components.pzem_014_016.helpers import create_unique_id

from . import MOCK_ENTRY_DATA, seed_meter

THRESHOLD = "number.pzem_power_alarm_threshold"
ADDRESS = "number.pzem_modbus_address"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: object,
) -> None:
    """Test every number against its snapshot."""
    with patch("custom_components.pzem_014_016.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_threshold_is_read(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the number shows the meter's alarm threshold."""
    assert hass.states.get(THRESHOLD).state == "2300"


async def test_set_threshold(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test setting the threshold writes the register and reads it back."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: THRESHOLD, ATTR_VALUE: 1500},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_connection.for_unit(1).holding[1] == 1500
    assert hass.states.get(THRESHOLD).state == "1500"


async def test_set_threshold_write_failure(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a failed write is reported, and the value stays as it was."""
    mock_connection.for_unit(1).fail_write(1, ModbusConnectionError("gone"))

    with pytest.raises(HomeAssistantError, match="Failed to write"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: THRESHOLD, ATTR_VALUE: 1500},
            blocking=True,
        )

    assert hass.states.get(THRESHOLD).state == "2300"


async def _enable_address(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Enable the address number, which is off by default, and reload."""
    entity_registry.async_update_entity(ADDRESS, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_address_is_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the number that can move the meter has to be asked for."""
    assert hass.states.get(ADDRESS) is None
    assert (
        entity_registry.async_get(ADDRESS).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_set_address_moves_the_entry(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the meter and the entry both move to the new address."""
    await _enable_address(hass, init_integration, entity_registry)
    assert hass.states.get(ADDRESS).state == "1"

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ADDRESS, ATTR_VALUE: 5},
            blocking=True,
        )

    assert mock_connection.for_unit(1).holding[2] == 5
    assert init_integration.data[CONF_UNIT_ID] == 5
    assert init_integration.unique_id == create_unique_id(
        {**MOCK_ENTRY_DATA, CONF_UNIT_ID: 5}
    )
    reload.assert_called_once_with(init_integration.entry_id)


async def test_set_address_write_failure_leaves_the_entry(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test a meter that refuses the write keeps its address in the entry."""
    await _enable_address(hass, init_integration, entity_registry)
    mock_connection.for_unit(1).fail_write(2, ModbusConnectionError("gone"))

    with pytest.raises(HomeAssistantError, match="Failed to write"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ADDRESS, ATTR_VALUE: 5},
            blocking=True,
        )

    assert init_integration.data[CONF_UNIT_ID] == 1


async def test_set_address_already_in_use(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: MagicMock,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test a meter cannot take an address another entry holds on its link."""
    other_data = {**MOCK_ENTRY_DATA, CONF_UNIT_ID: 5}
    seed_meter(mock_connection.for_unit(5))
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id=create_unique_id(other_data),
        data=other_data,
        title="Other",
    )
    other.add_to_hass(hass)
    await _enable_address(hass, init_integration, entity_registry)

    with pytest.raises(ServiceValidationError, match="already set up"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ADDRESS, ATTR_VALUE: 5},
            blocking=True,
        )

    assert mock_connection.for_unit(1).holding[2] == 1
    assert init_integration.data[CONF_UNIT_ID] == 1
