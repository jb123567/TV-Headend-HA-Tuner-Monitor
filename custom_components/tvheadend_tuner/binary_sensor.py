"""Binary sensors for TVHeadend tuners.

Per tuner:
  1. Available  – ON if the tuner's input name appears in status/inputs.
  2. Streaming  – ON while the tuner has ≥1 active subscription.

Keyed on the stable `input` name string, NOT the session UUID. IPTV inputs
are added when they first appear and kept after the stream stops.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TVHeadendCoordinator
from .inputs import claim_new_tuner_keys, entity_unique_id, tuner_device_id, tuner_model


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TVHeadendCoordinator = hass.data[DOMAIN][entry.entry_id]
    seen: set[str] = set()

    @callback
    def _async_add_new_tuners() -> None:
        """Register binary sensors for inputs that appeared after setup (IPTV)."""
        new_keys = claim_new_tuner_keys(seen, coordinator.data)
        if not new_keys:
            return
        entities: list[BinarySensorEntity] = []
        for key in new_keys:
            entities.append(TVHeadendTunerAvailableSensor(coordinator, entry, key))
            entities.append(TVHeadendTunerStreamingSensor(coordinator, entry, key))
        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_tuners))
    _async_add_new_tuners()


def _device_info(entry: ConfigEntry, tuner: dict) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, tuner_device_id(entry.entry_id, tuner["key"]))},
        name=tuner["name"],
        manufacturer="TVHeadend",
        model=tuner_model(tuner["name"]),
    )


class TVHeadendTunerAvailableSensor(CoordinatorEntity, BinarySensorEntity):
    """ON when the tuner is present in TVHeadend's status/inputs."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:antenna"

    def __init__(self, coordinator: TVHeadendCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        tuner = coordinator.data["tuners"][key]
        self._attr_unique_id = entity_unique_id(entry.entry_id, key, "available")
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
        self._attr_unique_id = entity_unique_id(entry.entry_id, key, "streaming")
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
