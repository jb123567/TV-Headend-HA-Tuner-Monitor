"""Input discovery behaviour, including the payloads from issue #1.

These tests load ``inputs.py`` directly so they can run without Home Assistant.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "tvheadend_tuner"
    / "inputs.py"
)


def _load_inputs():
    spec = importlib.util.spec_from_file_location("tvh_inputs_under_test", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inputs = _load_inputs()

# Payloads copied from https://github.com/jb123567/TV-Headend-HA-Tuner-Monitor/issues/1
IPTV_ACTIVE = json.loads(
    """
    {"entries":[{"uuid":"2ee6e1da4c08ba40cdeecfaf64c2d0ff","input":"IPTV #1",
    "stream":"1 - Sky Sports Main Event in IPTV #1","subs":1,"weight":150,
    "pids":[0,1,16,17,256,257,4096],"signal":0,"signal_scale":0,"ber":0,"snr":0,
    "snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,
    "tc_block":0}],"totalCount":1}
    """
)
IPTV_IDLE = json.loads('{"entries":[],"totalCount":0}')
DVB_ACTIVE = json.loads(
    """
    {"entries":[
      {"uuid":"dbce082c43e57d57a010594323d9c495","input":"DVB-T #0","stream":"626MHz in DVB-T2","subs":1,"weight":150,"pids":[0,1,16,17,6600,6601,6602,6605,6606],"signal":-50999,"signal_scale":2,"ber":0,"snr":29750,"snr_scale":2,"unc":0,"bps":4812800,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0},
      {"uuid":"6ef1fd1aaf6ba043d20444d3c8de3a4f","input":"DVB-T #1","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0},
      {"uuid":"91bc9881952f118dc95af06ad22e8542","input":"DVB-T #2","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0},
      {"uuid":"b10cb9c4cae67a79e9827cd90a4679ac","input":"DVB-T #3","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0}
    ],"totalCount":4}
    """
)
DVB_IDLE = json.loads(
    """
    {"entries":[
      {"uuid":"159f18d2235c05327a60afd875c426c9","input":"DVB-T #0","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0},
      {"uuid":"6ef1fd1aaf6ba043d20444d3c8de3a4f","input":"DVB-T #1","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0},
      {"uuid":"91bc9881952f118dc95af06ad22e8542","input":"DVB-T #2","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0},
      {"uuid":"b10cb9c4cae67a79e9827cd90a4679ac","input":"DVB-T #3","subs":0,"weight":0,"signal":0,"signal_scale":0,"ber":0,"snr":0,"snr_scale":0,"unc":0,"bps":0,"te":0,"cc":0,"ec_bit":0,"tc_bit":0,"ec_block":0,"tc_block":0}
    ],"totalCount":4}
    """
)

DVB_KEYS = ["dvb-t_#0", "dvb-t_#1", "dvb-t_#2", "dvb-t_#3"]
ENTITY_SUFFIXES = (
    "signal",
    "snr",
    "ber",
    "unc",
    "subscriptions",
    "bps",
    "available",
    "streaming",
)


def _legacy_name_to_key(name: str) -> str:
    """The slug used before this change. Existing entity IDs depend on it."""
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


def test_name_slug_matches_historical_dvb_ids():
    names = [
        "DVB-T #0",
        "DVB-T #1",
        "DVB-T #2",
        "DVB-T #3",
        "SAT>IP DVB-S Tuner #1 (192.168.1.25@UDP)",
        "IPTV #1",
        "IPTV #2",
    ]
    for name in names:
        assert inputs.name_to_key(name) == _legacy_name_to_key(name)

    assert inputs.name_to_key("DVB-T #0") == "dvb-t_#0"
    assert inputs.name_to_key("IPTV #1") == "iptv_#1"
    assert (
        inputs.name_to_key("SAT>IP DVB-S Tuner #1 (192.168.1.25@UDP)")
        == "satip_dvb-s_tuner_#1_192_168_1_25_udp"
    )


def test_entity_and_device_ids_keep_the_historical_format():
    entry_id = "abc123"
    key = "dvb-t_#0"
    assert inputs.tuner_device_id(entry_id, key) == f"{entry_id}_{key}"
    for suffix in ENTITY_SUFFIXES:
        assert inputs.entity_unique_id(entry_id, key, suffix) == f"{entry_id}_{key}_{suffix}"

    iptv_key = inputs.name_to_key("IPTV #1")
    assert inputs.tuner_key_from_device_identifier(
        entry_id, inputs.tuner_device_id(entry_id, iptv_key)
    ) == iptv_key
    # The server device identifier is the entry id itself and is not an input.
    assert inputs.tuner_key_from_device_identifier(entry_id, entry_id) is None
    assert inputs.tuner_key_from_device_identifier(entry_id, "other_iptv_#1") is None


def test_dvb_model_string_is_unchanged_and_iptv_is_distinct():
    assert inputs.DVB_TUNER_MODEL == "DVB / SAT>IP Tuner"
    assert inputs.tuner_model("DVB-T #0") == "DVB / SAT>IP Tuner"
    assert inputs.tuner_model("SAT>IP DVB-S Tuner #1 (192.168.1.25@UDP)") == "DVB / SAT>IP Tuner"
    assert inputs.tuner_model("IPTV #1") == "IPTV Input"
    assert inputs.tuner_model("iptv mux") == "IPTV Input"


def test_dvb_idle_and_active_keep_stable_keys_when_uuid_changes():
    known: dict[str, str] = {}
    active = inputs.merge_status_entries(known, DVB_ACTIVE["entries"])

    assert list(active) == DVB_KEYS
    tuner0 = active["dvb-t_#0"]
    assert tuner0["available"] is True
    assert tuner0["streaming"] is True
    assert tuner0["subscriptions"] == 1
    assert tuner0["stream"] == "626MHz in DVB-T2"
    assert tuner0["signal"] == -50999
    assert tuner0["signal_scale"] == 2
    assert tuner0["snr"] == 29750
    assert tuner0["snr_scale"] == 2
    assert tuner0["bps"] == 4812800
    assert tuner0["uuid"] == "dbce082c43e57d57a010594323d9c495"
    assert active["dvb-t_#1"]["available"] is True
    assert active["dvb-t_#1"]["streaming"] is False
    assert active["dvb-t_#1"]["subscriptions"] == 0
    assert active["dvb-t_#1"]["uuid"] == "6ef1fd1aaf6ba043d20444d3c8de3a4f"

    idle = inputs.merge_status_entries(known, DVB_IDLE["entries"])
    assert list(idle) == DVB_KEYS
    assert idle["dvb-t_#0"]["available"] is True
    assert idle["dvb-t_#0"]["streaming"] is False
    assert idle["dvb-t_#0"]["uuid"] == "159f18d2235c05327a60afd875c426c9"
    assert idle["dvb-t_#1"]["uuid"] == "6ef1fd1aaf6ba043d20444d3c8de3a4f"
    assert all(tuner["available"] is True for tuner in idle.values())


def test_iptv_appears_then_goes_idle_without_being_removed():
    known: dict[str, str] = {}
    live = inputs.merge_status_entries(known, IPTV_ACTIVE["entries"])

    assert list(live) == ["iptv_#1"]
    tuner = live["iptv_#1"]
    assert tuner["name"] == "IPTV #1"
    assert tuner["available"] is True
    assert tuner["streaming"] is True
    assert tuner["subscriptions"] == 1
    assert tuner["weight"] == 150
    assert tuner["stream"] == "1 - Sky Sports Main Event in IPTV #1"
    assert tuner["uuid"] == "2ee6e1da4c08ba40cdeecfaf64c2d0ff"
    # Scale 0 is unknown; the signal sensors report no reading.
    assert tuner["signal"] == 0
    assert tuner["signal_scale"] == 0
    assert tuner["snr"] == 0
    assert tuner["snr_scale"] == 0
    assert tuner["ber"] == 0
    assert tuner["unc"] == 0

    idle = inputs.merge_status_entries(known, IPTV_IDLE["entries"])
    assert list(idle) == ["iptv_#1"]
    assert idle["iptv_#1"]["available"] is False
    assert idle["iptv_#1"]["streaming"] is False
    assert idle["iptv_#1"]["subscriptions"] == 0
    assert idle["iptv_#1"]["stream"] == ""
    assert idle["iptv_#1"]["uuid"] == ""
    assert idle["iptv_#1"]["name"] == "IPTV #1"

    # A later session uses a new uuid and the same input name.
    restarted = inputs.merge_status_entries(
        known,
        [{**IPTV_ACTIVE["entries"][0], "uuid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
    )
    assert list(restarted) == ["iptv_#1"]
    assert restarted["iptv_#1"]["available"] is True
    assert restarted["iptv_#1"]["streaming"] is True
    assert restarted["iptv_#1"]["uuid"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_iptv_leaving_a_mixed_payload_does_not_change_dvb_tuners():
    known: dict[str, str] = {}
    mixed_entries = DVB_ACTIVE["entries"] + IPTV_ACTIVE["entries"]
    mixed = inputs.merge_status_entries(known, mixed_entries)

    assert list(mixed) == DVB_KEYS + ["iptv_#1"]
    assert mixed["dvb-t_#0"]["streaming"] is True
    assert mixed["dvb-t_#0"]["signal"] == -50999
    assert mixed["iptv_#1"]["streaming"] is True
    assert sum(tuner["available"] for tuner in mixed.values()) == 5

    dvb_only = inputs.merge_status_entries(known, DVB_IDLE["entries"])
    assert list(dvb_only) == DVB_KEYS + ["iptv_#1"]
    assert dvb_only["iptv_#1"]["available"] is False
    assert dvb_only["iptv_#1"]["streaming"] is False
    assert all(dvb_only[key]["available"] is True for key in DVB_KEYS)
    assert dvb_only["dvb-t_#0"]["streaming"] is False
    assert dvb_only["dvb-t_#0"]["uuid"] == "159f18d2235c05327a60afd875c426c9"
    assert dvb_only["dvb-t_#1"]["uuid"] == "6ef1fd1aaf6ba043d20444d3c8de3a4f"
    assert sum(tuner["available"] for tuner in dvb_only.values()) == 4


def test_restart_restores_idle_iptv_from_the_saved_name():
    known: dict[str, str] = {}
    inputs.merge_status_entries(known, IPTV_ACTIVE["entries"])

    restored: dict[str, str] = {}
    inputs.retain_known_inputs(restored, dict(known))
    # A stored name must not overwrite a name already learned this session.
    inputs.retain_known_inputs(restored, {"iptv_#1": "renamed by the device ui"})
    assert restored["iptv_#1"] == "IPTV #1"

    idle = inputs.merge_status_entries(restored, [])
    assert idle["iptv_#1"]["available"] is False
    assert idle["iptv_#1"]["name"] == "IPTV #1"

    back = inputs.merge_status_entries(restored, IPTV_ACTIVE["entries"])
    assert back["iptv_#1"]["available"] is True
    assert back["iptv_#1"]["name"] == "IPTV #1"


def test_names_that_slug_to_empty_are_skipped():
    known: dict[str, str] = {}
    merged = inputs.merge_status_entries(
        known,
        [{"input": ">>>", "subs": 1}, {"input": "IPTV #1", "subs": 1, "uuid": "u"}],
    )
    assert list(merged) == ["iptv_#1"]


def test_blank_and_non_dict_entries_are_ignored():
    known: dict[str, str] = {}
    inputs.merge_status_entries(known, DVB_IDLE["entries"])
    merged = inputs.merge_status_entries(
        known,
        [
            *DVB_IDLE["entries"],
            "not-a-dict",
            {"input": None, "subs": 1},
            {"subs": 4},
            {"input": "   ", "subs": 1},
            {"input": "  IPTV #2  ", "subs": 1, "uuid": "u", "stream": "channel"},
        ],
    )
    assert "iptv_#2" in merged
    assert merged["iptv_#2"]["name"] == "IPTV #2"
    assert merged["iptv_#2"]["streaming"] is True
    assert all(merged[key]["available"] is True for key in DVB_KEYS)


def test_duplicate_input_name_keeps_the_busiest_session():
    known: dict[str, str] = {}
    merged = inputs.merge_status_entries(
        known,
        [
            {"input": "IPTV #1", "uuid": "low", "subs": 1, "stream": "first"},
            {"input": "IPTV #1", "uuid": "same", "subs": 1, "stream": "ignored"},
            {"input": "IPTV #1", "uuid": "high", "subs": 3, "stream": "kept"},
        ],
    )
    assert list(merged) == ["iptv_#1"]
    assert merged["iptv_#1"]["uuid"] == "high"
    assert merged["iptv_#1"]["subscriptions"] == 3
    assert merged["iptv_#1"]["stream"] == "kept"


def test_new_tuner_keys_are_claimed_once():
    known: dict[str, str] = {}
    seen: set[str] = set()

    dvb = inputs.merge_status_entries(known, DVB_IDLE["entries"])
    assert inputs.claim_new_tuner_keys(seen, {"tuners": dvb}) == DVB_KEYS

    mixed = inputs.merge_status_entries(known, DVB_IDLE["entries"] + IPTV_ACTIVE["entries"])
    assert inputs.claim_new_tuner_keys(seen, {"tuners": mixed}) == ["iptv_#1"]

    idle = inputs.merge_status_entries(known, DVB_IDLE["entries"])
    assert "iptv_#1" in idle
    assert idle["iptv_#1"]["available"] is False
    assert inputs.claim_new_tuner_keys(seen, {"tuners": idle}) == []

    back = inputs.merge_status_entries(known, DVB_IDLE["entries"] + IPTV_ACTIVE["entries"])
    assert back["iptv_#1"]["available"] is True
    assert inputs.claim_new_tuner_keys(seen, {"tuners": back}) == []
    assert inputs.claim_new_tuner_keys(seen, None) == []
    assert inputs.claim_new_tuner_keys(seen, {}) == []
