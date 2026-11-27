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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TVHeadendCoordinator


# TVHeadend signal_status_scale_t (src/streaming.h):
#   0 = unknown (idle tuner), 1 = relative (0..65535 = 0..100 %), 2 = dB * 1000
SCALE_UNKNOWN = 0
SCALE_RELATIVE = 1
SCALE_DECIBEL = 2
SCALE_UNITS = {SCALE_RELATIVE: "%", SCALE_DECIBEL: "dB"}
DEFAULT_SCALED_UNIT = "%"


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
    async_add_entities(entities)


class TVHeadendTunerSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Per-tuner sensor.

    Home Assistant refuses to change the unit of a sensor that has long-term
    statistics, so the unit must never flip between updates. For signal/SNR the
    unit is "sticky": it is taken from the last scale TVHeadend reported (and
    restored across restarts), and is not dropped when the tuner goes idle.
    """

    entity_description: TVHTunerSensorDescription

    def __init__(self, coordinator, entry, key: str, description: TVHTunerSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._key = key
        self._scaled_unit: str = DEFAULT_SCALED_UNIT
        tuner = coordinator.data["tuners"][key]
        self._attr_unique_id = f"{entry.entry_id}_{key}_{description.key}"
        self._attr_name = f"{tuner['name']} {description.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{key}")},
            name=tuner["name"],
            manufacturer="TVHeadend",
            model="DVB / SAT>IP Tuner",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.entity_description.scale_key and (last := await self.async_get_last_state()):
            unit = last.attributes.get("unit_of_measurement")
            if unit in SCALE_UNITS.values():
                self._scaled_unit = unit

    @property
    def _tuner(self) -> dict:
        return self.coordinator.data["tuners"].get(self._key, {})

    @property
    def _scale(self) -> int:
        scale_key = self.entity_description.scale_key
        return self._tuner.get(scale_key, SCALE_UNKNOWN) if scale_key else SCALE_UNKNOWN

    def _handle_coordinator_update(self) -> None:
        # Remember the most recent known unit so it stays stable while idle.
        if self._scale in SCALE_UNITS:
            self._scaled_unit = SCALE_UNITS[self._scale]
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        raw = self._tuner.get(desc.data_key, 0)
        if desc.scale_key:
            scale = self._scale
            if scale == SCALE_RELATIVE:
                return round(raw / 655.35, 1)
            if scale == SCALE_DECIBEL:
                return round(raw / 1000.0, 1)
            return None  # unknown scale (idle tuner): no reading
        if desc.key == "bps":
            return round(raw / 1000, 1)
        return raw

    @property
    def native_unit_of_measurement(self) -> str | None:
        desc = self.entity_description
        if desc.key == "bps":
            return "kbps"
        if desc.scale_key:
            return SCALE_UNITS.get(self._scale, self._scaled_unit)
        return None

    @property
    def available(self) -> bool:
        return True  # Always report; values are 0/unknown when idle/gone


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
