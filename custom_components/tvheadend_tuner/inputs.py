"""Pure helpers for TVHeadend input identity and discovery.

TVHeadend's ``/api/status/inputs`` UUIDs change between subscription
sessions (confirmed for DVB-T adapters in the field). The stable identity
is the ``input`` name, for example ``DVB-T #0`` or ``IPTV #1``. Entity
unique IDs and device identifiers are derived from that name, so the
slug in :func:`name_to_key` must not change.

DVB adapters are always present in the status payload, including when
idle. IPTV inputs are present only while a stream is active. Once a name
has been seen it is retained so the entity can stay registered and report
idle instead of being removed.
"""
from __future__ import annotations

from typing import Any

# Device model strings. The DVB value is part of the existing device registry
# data and must stay byte-for-byte the same.
DVB_TUNER_MODEL = "DVB / SAT>IP Tuner"
IPTV_INPUT_MODEL = "IPTV Input"


def name_to_key(name: str) -> str:
    """Convert an input name to a stable unique-id fragment.

    This is the historical slug used for DVB entity unique IDs. Do not
    change the replacements: existing Home Assistant entities depend on it.
    """
    return (
        name.lower()
        .replace(" ", "_")
        .replace(">", "")
        .replace("(", "")
        .replace(")", "")
        .replace("@", "_")
        .replace(".", "_")
        .replace("/", "_")
    )


def tuner_model(name: str) -> str:
    """Return the device model for an input name.

    IPTV slot names from TVHeadend look like ``IPTV #1``. Anything else keeps
    the original DVB / SAT>IP model so existing devices are unchanged.
    """
    if "iptv" in name.lower():
        return IPTV_INPUT_MODEL
    return DVB_TUNER_MODEL


def tuner_device_id(entry_id: str, key: str) -> str:
    """Device-registry identifier fragment for one input."""
    return f"{entry_id}_{key}"


def entity_unique_id(entry_id: str, key: str, suffix: str) -> str:
    """Entity unique_id for one input sensor. Format is part of the public API."""
    return f"{entry_id}_{key}_{suffix}"


def tuner_key_from_device_identifier(entry_id: str, identifier: str) -> str | None:
    """Recover an input key from a device identifier, ignoring the server device."""
    prefix = f"{entry_id}_"
    if not identifier.startswith(prefix):
        return None
    key = identifier[len(prefix) :]
    return key or None


def retain_known_inputs(known_inputs: dict[str, str], inputs: dict[str, str]) -> None:
    """Remember input names from an earlier session without overriding live names."""
    for key, name in inputs.items():
        if not key or not isinstance(name, str) or not name.strip():
            continue
        known_inputs.setdefault(key, name)


def claim_new_tuner_keys(seen: set[str], data: dict[str, Any] | None) -> list[str]:
    """Return tuner keys that do not have entities yet, and mark them seen.

    Keys stay claimed after an input goes idle and comes back, so a later
    poll updates the existing entities instead of registering duplicates.
    """
    tuners = (data or {}).get("tuners") if isinstance(data, dict) else None
    if not isinstance(tuners, dict):
        return []
    new = [key for key in tuners if key not in seen]
    seen.update(new)
    return new


def build_tuner(key: str, name: str, live: dict[str, Any], *, available: bool) -> dict[str, Any]:
    """Build the coordinator record for one input."""
    subs = live.get("subs", 0)
    return {
        "key": key,
        "name": name,
        "uuid": live.get("uuid", ""),  # informational only — not stable
        "available": available,
        "streaming": available and subs > 0,
        "signal": live.get("signal", 0),
        "signal_scale": live.get("signal_scale", 0),
        "ber": live.get("ber", 0),
        "snr": live.get("snr", 0),
        "snr_scale": live.get("snr_scale", 0),
        "unc": live.get("unc", 0),
        "subscriptions": subs,
        "weight": live.get("weight", 0),
        "bps": live.get("bps", 0),
        "stream": live.get("stream", ""),
        "cc": live.get("cc", 0),
        "raw": live,
    }


def merge_status_entries(
    known_inputs: dict[str, str],
    status_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge a ``/api/status/inputs`` payload into the retained input set.

    ``known_inputs`` is updated in place (stable key -> display name). Inputs
    that disappear from the payload stay in the result with ``available``
    false so their entities can go idle instead of being deleted.
    """
    current: dict[str, dict[str, Any]] = {}
    for entry in status_entries:
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("input")
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name:
            continue
        key = name_to_key(name)
        if not key:
            continue
        # If multiple sessions share a name, keep the one with an active subscription.
        if key not in current or entry.get("subs", 0) > current[key].get("subs", 0):
            current[key] = entry
        known_inputs[key] = name

    tuners: dict[str, dict[str, Any]] = {}
    for key, name in known_inputs.items():
        live = current.get(key)
        tuners[key] = build_tuner(key, name, live or {}, available=live is not None)
    return tuners
