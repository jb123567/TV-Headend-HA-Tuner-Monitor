"""Binary sensors for TVHeadend tuners.

Per tuner:
  1. Available  – ON if the tuner's input name appears in status/inputs.
  2. Streaming  – ON while the tuner has ≥1 active subscription.

Keyed on the stable `input` name string, NOT the session UUID.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TVHeadendCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TVHeadendCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []
    for key in coordinator.data["tuners"]:
        entities.append(TVHeadendTunerAvailableSensor(coordinator, entry, key))
        entities.append(TVHeadendTunerStreamingSensor(coordinator, entry, key))
    async_add_entities(entities, update_before_add=True)


def _device_info(entry: ConfigEntry, tuner: dict) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{tuner['key']}")},
        name=tuner["name"],
        manufacturer="TVHeadend",
        model="DVB / SAT>IP Tuner",
        via_device=(DOMAIN, entry.entry_id),
    )


class TVHeadendTunerAvailableSensor(CoordinatorEntity, BinarySensorEntity):
    """ON when the tuner is present in TVHeadend's status/inputs."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:antenna"

    def __init__(self, coordinator: TVHeadendCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        tuner = coordinator.data["tuners"][key]
        self._attr_unique_id = f"{entry.entry_id}_{key}_available"
        self._attr_name = f"{tuner['name']} Available"
        self._attr_device_info = _device_info(entry, tuner)

    @property
    def _tuner(self) -> dict:
        return self.coordinator.data["tuners"].get(self._key, {})

    @property
    def is_on(self) -> bool:
        return self._tuner.get("available", False)

    @property
    def extra_state_attributes(self) -> dict:
        t = self._tuner
        return {
            "input_name": t.get("name", ""),
            "current_uuid": t.get("uuid", ""),   # shown for info only
            "stream": t.get("stream", ""),
            "subscriptions": t.get("subscriptions", 0),
            "bitrate_kbps": round(t.get("bps", 0) / 1000, 1),
        }


class TVHeadendTunerStreamingSensor(CoordinatorEntity, BinarySensorEntity):
    """ON while the tuner has at least one active subscription."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:television-play"

    def __init__(self, coordinator: TVHeadendCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        tuner = coordinator.data["tuners"][key]
        self._attr_unique_id = f"{entry.entry_id}_{key}_streaming"
        self._attr_name = f"{tuner['name']} Streaming"
        self._attr_device_info = _device_info(entry, tuner)

    @property
    def _tuner(self) -> dict:
        return self.coordinator.data["tuners"].get(self._key, {})

    @property
    def is_on(self) -> bool:
        return self._tuner.get("streaming", False)

    @property
    def extra_state_attributes(self) -> dict:
        t = self._tuner
        return {
            "input_name": t.get("name", ""),
            "stream": t.get("stream", ""),
            "subscriptions": t.get("subscriptions", 0),
            "bitrate_kbps": round(t.get("bps", 0) / 1000, 1),
            "weight": t.get("weight", 0),
        }
