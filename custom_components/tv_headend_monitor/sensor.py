"""Sensors keyed on stable input name, not session UUID."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TVHeadendCoordinator


@dataclass(frozen=True)
class TVHTunerSensorDescription(SensorEntityDescription):
    data_key: str = ""
    scale_key: str | None = None


TUNER_SENSORS: tuple[TVHTunerSensorDescription, ...] = (
    TVHTunerSensorDescription(key="signal", name="Signal Strength", icon="mdi:signal",
        state_class=SensorStateClass.MEASUREMENT, data_key="signal", scale_key="signal_scale"),
    TVHTunerSensorDescription(key="snr", name="SNR", icon="mdi:sine-wave",
        state_class=SensorStateClass.MEASUREMENT, data_key="snr", scale_key="snr_scale"),
    TVHTunerSensorDescription(key="ber", name="BER", icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.MEASUREMENT, data_key="ber"),
    TVHTunerSensorDescription(key="unc", name="Uncorrected Blocks", icon="mdi:block-helper",
        state_class=SensorStateClass.MEASUREMENT, data_key="unc"),
    TVHTunerSensorDescription(key="subscriptions", name="Active Subscriptions",
        icon="mdi:television-play", state_class=SensorStateClass.MEASUREMENT, data_key="subscriptions"),
    TVHTunerSensorDescription(key="bps", name="Bitrate", icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT, data_key="bps"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TVHeadendCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for key in coordinator.data["tuners"]:
        for desc in TUNER_SENSORS:
            entities.append(TVHeadendTunerSensor(coordinator, entry, key, desc))
    entities += [
        TVHeadendTotalTunersSensor(coordinator, entry),
        TVHeadendAvailableTunersSensor(coordinator, entry),
        TVHeadendServerVersionSensor(coordinator, entry),
    ]
    async_add_entities(entities, update_before_add=True)


class TVHeadendTunerSensor(CoordinatorEntity, SensorEntity):
    entity_description: TVHTunerSensorDescription

    def __init__(self, coordinator, entry, key: str, description: TVHTunerSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._key = key
        tuner = coordinator.data["tuners"][key]
        self._attr_unique_id = f"{entry.entry_id}_{key}_{description.key}"
        self._attr_name = f"{tuner['name']} {description.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{key}")},
            name=tuner["name"],
            manufacturer="TVHeadend",
            model="DVB / SAT>IP Tuner",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _tuner(self) -> dict:
        return self.coordinator.data["tuners"].get(self._key, {})

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        raw = self._tuner.get(desc.data_key, 0)
        if desc.scale_key:
            scale = self._tuner.get(desc.scale_key, 0)
            if scale == 2:
                return round(raw / 655.35, 1)
            if scale == 1:
                return round(raw / 1000.0, 1)
        if desc.key == "bps":
            return round(raw / 1000, 1)
        return raw

    @property
    def native_unit_of_measurement(self) -> str | None:
        desc = self.entity_description
        if desc.key == "bps":
            return "kbps"
        if desc.scale_key:
            scale = self._tuner.get(desc.scale_key, 0)
            if scale == 2:
                return "%"
            if scale == 1:
                return "dB"
        return None

    @property
    def available(self) -> bool:
        return True  # Always report; values are 0 when idle/gone


class _ServerDeviceMixin:
    def _server_device(self, entry: ConfigEntry) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"TVHeadend ({entry.data.get('host', 'server')})",
            manufacturer="TVHeadend",
        )


class TVHeadendTotalTunersSensor(_ServerDeviceMixin, CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:television-box"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_total_tuners"
        self._attr_name = "TVHeadend Total Tuners"
        self._attr_device_info = self._server_device(entry)

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("tuner_count", 0)


class TVHeadendAvailableTunersSensor(_ServerDeviceMixin, CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:check-network"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_available_tuners"
        self._attr_name = "TVHeadend Available Tuners"
        self._attr_device_info = self._server_device(entry)

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("available_count", 0)


class TVHeadendServerVersionSensor(_ServerDeviceMixin, CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_server_version"
        self._attr_name = "TVHeadend Server Version"
        self._attr_device_info = self._server_device(entry)

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("server_version", "unknown")
