"""TVHeadend Tuner Monitor integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_SCAN_INTERVAL, DEFAULT_PASSWORD, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_USERNAME, DOMAIN, PLATFORMS
from .coordinator import TVHeadendCoordinator
from .inputs import tuner_device_id, tuner_key_from_device_identifier, tuner_model
from .tvheadend import TVHeadendClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TVHeadend Tuner Monitor from a config entry."""
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    client = TVHeadendClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
        password=entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD),
    )
    coordinator = TVHeadendCoordinator(hass, client, scan_interval)
    # Inputs seen last session (including idle IPTV) are restored before the
    # first poll so their entities exist without waiting for a stream.
    _remember_inputs_from_devices(hass, entry, coordinator)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Create the server device and each tuner device up front. Tuner devices are
    # linked with via_device_id; the DeviceInfo `via_device` tuple is deprecated
    # and raises an error in recent Home Assistant versions. The listener adds
    # a device when an IPTV input appears on a later poll.
    registry = dr.async_get(hass)
    server = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"TVHeadend ({entry.data.get(CONF_HOST, 'server')})",
        manufacturer="TVHeadend",
    )
    created: set[str] = set()

    @callback
    def _ensure_tuner_devices() -> None:
        data = coordinator.data
        if not data:
            return
        for key, tuner in data["tuners"].items():
            if key in created:
                continue
            registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, tuner_device_id(entry.entry_id, key))},
                name=tuner["name"],
                manufacturer="TVHeadend",
                model=tuner_model(tuner["name"]),
                via_device_id=server.id,
            )
            created.add(key)

    entry.async_on_unload(coordinator.async_add_listener(_ensure_tuner_devices))
    _ensure_tuner_devices()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _remember_inputs_from_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: TVHeadendCoordinator,
) -> None:
    """Seed input names from devices created the last time this entry was set up."""
    registry = dr.async_get(hass)
    found: dict[str, str] = {}
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.name:
            continue
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            key = tuner_key_from_device_identifier(entry.entry_id, identifier)
            if key:
                found[key] = device.name
    if found:
        _LOGGER.debug("Restoring %s previously seen TVHeadend inputs", len(found))
    coordinator.remember_inputs(found)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TVHeadendCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()
    return unload_ok
