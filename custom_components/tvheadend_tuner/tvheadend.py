"""TVHeadend API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    TVH_API_STATUS_INPUTS,
    TVH_API_SERVERINFO,
)

_LOGGER = logging.getLogger(__name__)


class TVHeadendError(Exception):
    """Base error for TVHeadend client."""


class TVHeadendAuthError(TVHeadendError):
    """Authentication error."""


class TVHeadendConnectionError(TVHeadendError):
    """Connection error."""


class TVHeadendClient:
    """Async client for the TVHeadend HTTP API."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._base_url = f"http://{host}:{port}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            auth = None
            if self._username:
                auth = aiohttp.BasicAuth(self._username, self._password)
            self._session = aiohttp.ClientSession(auth=auth)
        return self._session

    async def _get(self, path: str, params: dict | None = None) -> Any:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        try:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 401:
                    raise TVHeadendAuthError("Invalid credentials")
                if resp.status != 200:
                    raise TVHeadendConnectionError(f"HTTP {resp.status} from {url}")
                return await resp.json(content_type=None)
        except aiohttp.ClientConnectorError as err:
            raise TVHeadendConnectionError(f"Cannot connect to {url}: {err}") from err
        except aiohttp.ServerTimeoutError as err:
            raise TVHeadendConnectionError(f"Timeout connecting to {url}") from err

    async def get_server_info(self) -> dict:
        """Fetch server version and basic info."""
        return await self._get(TVH_API_SERVERINFO)

    async def get_status_inputs(self) -> list[dict]:
        """Fetch live input statistics for all tuners via /api/status/inputs.

        TVHeadend returns an entry for every adapter it knows about, even when
        idle (signal/snr/bps will be zero).  A tuner that physically disappears
        (USB unplug, SAT>IP box offline) will be absent from this response.
        """
        data = await self._get(TVH_API_STATUS_INPUTS)
        return data.get("entries", [])

    async def test_connection(self) -> str:
        """Test connectivity and return the server version string."""
        info = await self.get_server_info()
        return info.get("sw_version", "unknown")

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
