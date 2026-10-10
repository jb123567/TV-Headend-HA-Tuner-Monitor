"""Sensors keyed on stable input name, not session UUID."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TVHeadendCoordinator

# TVHeadend reports signal/SNR with a scale flag: 2 = relative (%), 1 = absolute (dB),
# 0 = unknown (typically an idle tuner).
SCALE_UNITS: dict[int, str] = {2: "%", 1: "dB"}


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


class TVHeadendTunerSensor(CoordinatorEntity, RestoreSensor):
    entity_description: TVHTunerSensorDescription

    def __init__(self, coordinator, entry, key: str, description: TVHTunerSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._key = key
        # Home Assistant long-term statistics cannot cope with a measurement sensor
        # changing unit, so the unit is locked once known and never flipped afterwards.
        self._locked_unit: str | None = None
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

    async def async_added_to_hass(self) -> None:
        """Restore the previously used unit so it stays stable across restarts."""
        await super().async_added_to_hass()
        if self.entity_description.scale_key and (
            last := await self.async_get_last_sensor_data()
        ):
            if last.native_unit_of_measurement in SCALE_UNITS.values():
                self._locked_unit = last.native_unit_of_measurement

    def _reported_unit(self) -> str | None:
        """Unit implied by the scale the tuner is reporting right now."""
        scale = self._tuner.get(self.entity_description.scale_key, 0)
        return SCALE_UNITS.get(scale)

    def _resolve_unit(self) -> str | None:
        """Return the stable unit for a scaled sensor, locking it on first use."""
        if self._locked_unit is None:
            self._locked_unit = self._reported_unit()
        return self._locked_unit

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        raw = self._tuner.get(desc.data_key, 0)
        if desc.scale_key:
            unit = self._resolve_unit()
            if unit is None:
                # Scale not known yet (e.g. tuner idle on first start): report
                # unknown rather than a unitless number that would pin the wrong unit.
                return None
            reported = self._reported_unit()
            if reported is not None and reported != unit:
                # Tuner now reports a different scale; the two cannot be converted.
                return None
            if unit == "%":
                return round(raw / 655.35, 1)
            return round(raw / 1000.0, 1)  # dB
        if desc.key == "bps":
            return round(raw / 1000, 1)
        return raw

    @property
    def native_unit_of_measurement(self) -> str | None:
        desc = self.entity_description
        if desc.key == "bps":
            return "kbps"
        if desc.scale_key:
            return self._resolve_unit()
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

