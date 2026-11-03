"""Fixtures for the PZEM integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.pzem_014_016.const import DEFAULT_NAME, DOMAIN
from custom_components.pzem_014_016.helpers import create_unique_id

from . import MOCK_ENTRY_DATA, seed_meter


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Snapshot with Home Assistant's extension, whatever order plugins load in."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable the entities that are disabled by default."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.pzem_014_016.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """A fake Modbus connection seeded as a PZEM meter."""
    connection = MockModbusConnection()
    seed_meter(connection.for_unit(1))
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a PZEM config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JZMETER0000000000000PZEM",
        unique_id=create_unique_id(MOCK_ENTRY_DATA),
        data=MOCK_ENTRY_DATA,
        title=DEFAULT_NAME,
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand out units on the mock connection when the entry sets up."""
    with patch(
        "custom_components.pzem_014_016.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the PZEM integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry
