"""DataUpdateCoordinator for TVHeadend Tuner Monitor."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .inputs import merge_status_entries, retain_known_inputs
from .tvheadend import TVHeadendClient, TVHeadendConnectionError, TVHeadendAuthError

_LOGGER = logging.getLogger(__name__)


class TVHeadendCoordinator(DataUpdateCoordinator):
    """Fetches and caches data from TVHeadend on a regular schedule.

    Stable identity
    ───────────────
    TVHeadend's status/inputs UUIDs are NOT stable device identifiers — they
    change every time a new subscription session starts.  The only stable
    identifier is the `input` field, e.g.:
        "SAT>IP DVB-S Tuner #1 (192.168.1.25@UDP)"
        "IPTV #1"

    Tuner state is keyed on a slug derived from that name. The UUID is stored
    as an attribute but never used as a key. Platforms listen for new keys and
    register entities without a config-entry reload.

    Availability detection
    ──────────────────────
    A tuner is "available" if its input name appears in the current
    status/inputs response. DVB adapters are always listed (idle ones report
    subs 0). IPTV inputs are listed only while a stream is active. Once a name
    has been seen it stays in _known_inputs; if it later disappears it flips
    to idle rather than being removed. Names from a previous session can be
    restored with remember_inputs() before the first refresh.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: TVHeadendClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.server_version: str = "unknown"
        # Persistent registry: stable_key -> display name. Survives an input
        # dropping out of the API; seeded from the device registry on startup.
        self._known_inputs: dict[str, str] = {}

    def remember_inputs(self, inputs: dict[str, str]) -> None:
        """Remember inputs discovered in a previous session, before the first poll."""
        retain_known_inputs(self._known_inputs, inputs)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data from TVHeadend."""
        try:
            server_info = await self.client.get_server_info()
            self.server_version = server_info.get("sw_version", "unknown")

            status_entries = await self.client.get_status_inputs()
            previously_known = set(self._known_inputs)
            tuners = merge_status_entries(self._known_inputs, status_entries)
            for key, name in self._known_inputs.items():
                if key not in previously_known:
                    _LOGGER.info("Discovered TVHeadend input %s", name)

            return {
                "tuners": tuners,
                "server_version": self.server_version,
                "tuner_count": len(tuners),
                "available_count": sum(1 for t in tuners.values() if t["available"]),
            }

        except TVHeadendAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except TVHeadendConnectionError as err:
            raise UpdateFailed(f"Cannot reach TVHeadend: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err
