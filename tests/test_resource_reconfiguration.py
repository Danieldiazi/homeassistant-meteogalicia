"""Resource changes must update identity and replace only their own entities."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteogalicia import async_setup_entry, config_flow, const


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        title="MeteoGalicia old",
        unique_id="concello_15030",
        data={const.CONF_ID_CONCELLO: "15030"},
        options={const.CONF_FORECAST_INTERVAL: 7200},
    )
    entry.add_to_hass(hass)
    return entry


async def test_options_manager_updates_identity_and_schedules_one_reload(
    hass, enable_custom_integrations, entry
):
    with (
        patch.object(
            hass.config_entries, "async_reload", AsyncMock(return_value=True)
        ) as reload,
        patch.object(
            config_flow,
            "_validated_title",
            AsyncMock(return_value="MeteoGalicia Santiago"),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {config_flow.CONF_CONFIGURATION_METHOD: "manual"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                const.CONF_ID_CONCELLO: "15078",
                const.CONF_OBSERVATION_INTERVAL: 900,
                const.CONF_FORECAST_INTERVAL: 7200,
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert entry.unique_id == "concello_15078"
    assert entry.title == "MeteoGalicia Santiago"
    assert entry.data[const.CONF_ID_CONCELLO] == "15078"
    assert entry.options[const.CONF_ID_CONCELLO] == "15078"
    assert entry.data[const.CONF_RESET_ENTITIES] is True
    reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize("stale_unique_id", [False, True])
async def test_duplicate_resource_is_rejected_without_mutation(
    hass, entry, stale_unique_id
):
    other = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="concello_15009" if stale_unique_id else "concello_15078",
        data={const.CONF_ID_CONCELLO: "15009"},
        options={const.CONF_ID_CONCELLO: "15078"},
    )
    other.add_to_hass(hass)
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    before = (entry.data, entry.options, entry.title, entry.unique_id)
    result = flow._save_options({const.CONF_ID_CONCELLO: "15078"}, "New title")
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert (entry.data, entry.options, entry.title, entry.unique_id) == before


async def test_stale_identity_does_not_reserve_an_unused_resource(hass, entry):
    other = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="concello_15078",
        data={const.CONF_ID_CONCELLO: "15078"},
        options={const.CONF_ID_CONCELLO: "15009"},
    )
    other.add_to_hass(hass)
    previous_resource = (other.data, other.options, other.title)
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    result = flow._save_options({const.CONF_ID_CONCELLO: "15078"}, "Santiago")
    assert result["type"] == "create_entry"
    assert entry.unique_id == "concello_15078"
    assert other.unique_id == "concello_15009"
    assert (other.data, other.options, other.title) == previous_resource


async def test_station_measure_change_replaces_old_measure_in_identity(hass):
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        title="Station",
        unique_id="estacion_10001_TA_AVG_1.5m_",
        data={
            const.CONF_ID_ESTACION: "10001",
            const.CONF_ID_ESTACION_MEDIDA_DAILY: "TA_AVG_1.5m",
        },
    )
    entry.add_to_hass(hass)
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    result = flow._save_options(
        {
            const.CONF_ID_ESTACION: "10001",
            const.CONF_ID_ESTACION_MEDIDA_DAILY: "",
            const.CONF_ID_ESTACION_MEDIDA_LAST10MIN: "DV_AVG_10m",
        },
        "Station wind",
    )
    assert result["type"] == "create_entry"
    assert entry.unique_id == "estacion_10001__DV_AVG_10m"
    assert const.CONF_ID_ESTACION_MEDIDA_DAILY not in entry.data
    assert entry.data[const.CONF_ID_ESTACION_MEDIDA_LAST10MIN] == "DV_AVG_10m"
    assert entry.data[const.CONF_RESET_ENTITIES] is True


@pytest.mark.parametrize("changed_resource", [False, True])
async def test_setup_cleans_changed_resource_and_preserves_other_entries(
    hass, enable_custom_integrations, entry, changed_resource
):
    other = MockConfigEntry(domain=const.DOMAIN, data={const.CONF_ID_CONCELLO: "15078"})
    other.add_to_hass(hass)
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    own_device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(const.DOMAIN, "old")},
        name="Old resource",
    )
    other_device = devices.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={(const.DOMAIN, "other")},
        name="Other resource",
    )
    own_entity = registry.async_get_or_create(
        "sensor", const.DOMAIN, "own", config_entry=entry, device_id=own_device.id
    )
    other_entity = registry.async_get_or_create(
        "sensor", const.DOMAIN, "other", config_entry=other, device_id=other_device.id
    )
    if changed_resource:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, const.CONF_RESET_ENTITIES: True}
        )
    with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
        assert await async_setup_entry(hass, entry)
    assert (registry.async_get(own_entity.entity_id) is None) == changed_resource
    assert (devices.async_get(own_device.id) is None) == changed_resource
    assert registry.async_get(other_entity.entity_id) is not None
    assert devices.async_get(other_device.id) is not None
    assert const.CONF_RESET_ENTITIES not in entry.data
    assert not entry.update_listeners


async def test_invalid_identifier_keeps_existing_resource(hass, entry):
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    with patch.object(config_flow, "_validated_title", AsyncMock(return_value=None)):
        result = await flow.async_step_forecast_manual(
            {
                const.CONF_ID_CONCELLO: "15078",
                const.CONF_OBSERVATION_INTERVAL: 900,
                const.CONF_FORECAST_INTERVAL: 7200,
            }
        )
    assert result["type"] == "form"
    assert entry.unique_id == "concello_15030"
    assert entry.data == {const.CONF_ID_CONCELLO: "15030"}
    assert entry.options == {const.CONF_FORECAST_INTERVAL: 7200}


def test_interval_change_keeps_entities_and_identity(hass, entry):
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    flow._save_options({const.CONF_FORECAST_INTERVAL: 21600})
    assert entry.unique_id == "concello_15030"
    assert const.CONF_RESET_ENTITIES not in entry.data
