"""Optional sensors exposing connection health without extra API requests."""

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

DESCRIPTIONS = (
    SensorEntityDescription(
        key="health_last_success",
        translation_key="health_last_success",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="health_data_age",
        translation_key="health_data_age",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="health_failures",
        translation_key="health_failures",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


def create_health_sensors(coordinator, identifier, device_info):
    """Create three diagnostics for the existing device."""
    return [
        HealthSensor(coordinator, identifier, device_info, item)
        for item in DESCRIPTIONS
    ]


class HealthSensor(CoordinatorEntity, SensorEntity):
    """Remain available during failed requests so failures stay visible."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, identifier, device_info, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"
        self._attr_device_info = device_info

    @property
    def available(self):
        return not getattr(self.coordinator, "_closed", False)

    @property
    def native_value(self):
        if self.entity_description.key == "health_last_success":
            return self.coordinator.last_success
        if self.entity_description.key == "health_data_age":
            return self.coordinator.data_age_seconds
        return self.coordinator.consecutive_failures

    @property
    def extra_state_attributes(self):
        return {
            "last_failure_kind": self.coordinator.last_failure_kind,
            "last_failure_reason": self.coordinator.last_failure_reason,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Advance data age and repeated failure counts even without a new
        # successful API response. The timer ends when the entity is removed.
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1))
        )

    @callback
    def _async_tick(self, _now):
        self.async_write_ha_state()
