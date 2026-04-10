"""DataUpdateCoordinator for TVHeadend Tuner Monitor."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
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

    We therefore key all tuner state on a slug derived from that name string.
    The UUID is stored as an attribute but never used as a key.

    Availability detection
    ──────────────────────
    A tuner is "available" if its input name appears in the current
    status/inputs response.  Once a name has been seen it is added to
    _known_inputs; if it later disappears it flips to unavailable rather
    than vanishing from HA entirely.
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
        # Persistent registry: stable_key -> display name
        self._known_inputs: dict[str, str] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data from TVHeadend."""
        try:
            server_info = await self.client.get_server_info()
            self.server_version = server_info.get("sw_version", "unknown")

            status_entries = await self.client.get_status_inputs()

            # Build lookup keyed by stable input name
            current: dict[str, dict] = {}
            for entry in status_entries:
                name = entry.get("input", "").strip()
                if not name:
                    continue
                key = _name_to_key(name)
                # If multiple sessions share a name (shouldn't happen but be safe)
                # keep the one with an active subscription
                if key not in current or entry.get("subs", 0) > current[key].get("subs", 0):
                    current[key] = entry
                self._known_inputs[key] = name

            # Merge: present tuners + previously-seen-but-now-missing
            tuners: dict[str, dict] = {}
            for key, name in self._known_inputs.items():
                live = current.get(key)
                tuners[key] = _build_tuner(key, name, live or {}, available=live is not None)

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


def _name_to_key(name: str) -> str:
    """Convert an input name to a safe, stable dict key / unique_id fragment."""
    return name.lower().replace(" ", "_").replace(">", "").replace(
        "(", "").replace(")", "").replace("@", "_").replace(".", "_").replace("/", "_")


def _build_tuner(key: str, name: str, live: dict, *, available: bool) -> dict:
    return {
        "key": key,
        "name": name,
        "uuid": live.get("uuid", ""),          # informational only — not stable
        "available": available,
        "streaming": available and live.get("subs", 0) > 0,
        "signal": live.get("signal", 0),
        "signal_scale": live.get("signal_scale", 0),
        "ber": live.get("ber", 0),
        "snr": live.get("snr", 0),
        "snr_scale": live.get("snr_scale", 0),
        "unc": live.get("unc", 0),
        "subscriptions": live.get("subs", 0),
        "weight": live.get("weight", 0),
        "bps": live.get("bps", 0),
        "stream": live.get("stream", ""),
        "cc": live.get("cc", 0),
        "raw": live,
    }
