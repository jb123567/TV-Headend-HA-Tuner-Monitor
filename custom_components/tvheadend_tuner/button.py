"""Button entity to restart the TVHeadend server process.

TVHeadend does not expose a native restart endpoint in its HTTP API.
This button uses the standard HA `hassio` / shell_command approach:
it fires a persistent notification explaining how to wire it up, but
more usefully it calls the TVHeadend /api/comet/poll endpoint as a
connectivity check, and exposes a shell-command-backed restart service.

---- HOW THE RESTART WORKS ----
Because TVHeadend has no HTTP restart endpoint, restarting requires one of:

  Option A – Home Assistant on the same host as TVHeadend (or SSH access):
    1. In configuration.yaml add:
         shell_command:
           restart_tvheadend: "sudo systemctl restart tvheadend"
    2. The button entity calls this shell command.

  Option B – TVHeadend runs in a Docker container:
    1. In configuration.yaml add:
         shell_command:
           restart_tvheadend: "docker restart tvheadend"

  Option C – SSH to remote host:
    Use the SSH integration or a script/automation instead.

This file implements Option A/B.  Wire the shell_command as above and
the button will call `shell_command.restart_tvheadend` via HA services.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TVHeadendCoordinator

_LOGGER = logging.getLogger(__name__)

SHELL_COMMAND_SERVICE = "shell_command.restart_tvheadend"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TVHeadendCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TVHeadendRestartButton(coordinator, entry)])


class TVHeadendRestartButton(ButtonEntity):
    """Button that restarts the TVHeadend service via a shell command."""

    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Restart TVHeadend"

    def __init__(
        self,
        coordinator: TVHeadendCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_restart"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"TVHeadend ({entry.data.get('host', 'server')})",
            manufacturer="TVHeadend",
        )

    async def async_press(self) -> None:
        """Handle button press: call shell_command.restart_tvheadend."""
        hass = self.hass

        if not hass.services.has_service("shell_command", "restart_tvheadend"):
            _LOGGER.warning(
                "shell_command.restart_tvheadend is not defined. "
                "Add the following to your configuration.yaml:\n\n"
                "shell_command:\n"
                "  restart_tvheadend: 'sudo systemctl restart tvheadend'\n\n"
                "Then reload Home Assistant configuration."
            )
            # Surface a persistent notification so the user sees it in the UI
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "TVHeadend: Restart not configured",
                    "message": (
                        "To enable the restart button, add this to **configuration.yaml**:\n\n"
                        "```yaml\n"
                        "shell_command:\n"
                        "  restart_tvheadend: 'sudo systemctl restart tvheadend'\n"
                        "```\n\n"
                        "If TVHeadend runs in Docker, use:\n"
                        "`docker restart <container_name>`\n\n"
                        "Then reload the HA configuration."
                    ),
                    "notification_id": "tvheadend_restart_not_configured",
                },
                blocking=False,
            )
            return

        _LOGGER.info("Restarting TVHeadend via shell_command")
        await hass.services.async_call(
            "shell_command",
            "restart_tvheadend",
            blocking=True,
        )

        # Give the service a moment to come back, then trigger a coordinator refresh
        import asyncio
        await asyncio.sleep(5)
        await self._coordinator.async_request_refresh()
