# tests/test_gateway_selection.py
import json
import os
import shutil
import tempfile
import io
from types import SimpleNamespace

import importlib.util
import types
import pytest

from src import mode_wifi_diag as wifi_diag
from src import ping_check
from src import net_utils
from src import main
from src.error_kinds import CONFIG_MISSING_GATEWAY
from pathlib import Path

from src.main import persist_gateway


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_persist_gateway_does_not_override_existing_gateway(tmp_path):
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        json.dumps(
            {
                "GATEWAY_HOSTNAME": "10.0.0.1",
                "SERVICES": [
                    {"name": "gateway", "hostname": "10.0.0.1", "tags": ["gateway"], "ping": {"enabled": True}},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ok = persist_gateway("10.0.0.2", targets_file_path=str(cfg), targets_module=None, overwrite=False)
    assert ok is True

    data = _read_json(cfg)
    assert data["GATEWAY_HOSTNAME"] == "10.0.0.1"
    assert data["SERVICES"][0]["hostname"] == "10.0.0.1"


def test_persist_gateway_overwrites_when_forced(tmp_path):
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        json.dumps(
            {
                "GATEWAY_HOSTNAME": "10.0.0.1",
                "SERVICES": [
                    {"name": "gateway", "hostname": "10.0.0.1", "tags": ["gateway"], "ping": {"enabled": True}},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ok = persist_gateway("10.0.0.2", targets_file_path=str(cfg), targets_module=None, overwrite=True)
    assert ok is True

    data = _read_json(cfg)
    assert data["GATEWAY_HOSTNAME"] == "10.0.0.2"
    # hostname may remain the old one if explicitly set; in this test it is explicitly set,
    # so we expect it NOT to be overridden (that’s the intended safety behavior).
    assert data["SERVICES"][0]["hostname"] == "10.0.0.1"


def test_persist_gateway_sets_gateway_when_missing(tmp_path):
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        json.dumps(
            {
                "GATEWAY_HOSTNAME": None,
                "SERVICES": [
                    # gateway-tagged service with empty hostname should be populated
                    {"name": "gateway", "hostname": "", "tags": ["gateway"], "ping": {"enabled": True}},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ok = persist_gateway("192.168.1.1", targets_file_path=str(cfg), targets_module=None, overwrite=False)
    assert ok is True

    data = _read_json(cfg)
    assert data["GATEWAY_HOSTNAME"] == "192.168.1.1"
    assert data["SERVICES"][0]["hostname"] == "192.168.1.1"


def test_persist_gateway_does_not_override_service_hostname(tmp_path):
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        json.dumps(
            {
                "GATEWAY_HOSTNAME": None,
                "SERVICES": [
                    # Explicit hostname should not be overridden
                    {"name": "gateway", "hostname": "1.2.3.4", "tags": ["gateway"], "ping": {"enabled": True}},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ok = persist_gateway("9.9.9.9", targets_file_path=str(cfg), targets_module=None, overwrite=False)
    assert ok is True

    data = _read_json(cfg)
    assert data["GATEWAY_HOSTNAME"] == "9.9.9.9"
    # Explicit hostname stays
    assert data["SERVICES"][0]["hostname"] == "1.2.3.4"


def _fake_ping_ok(host, count=1, timeout=1.0):
    return {
        "received": 1,
        "latency_avg_ms": 10.0,
        "error_kind": "ok",
        "error": None,
    }


def test_gateway_override_used(monkeypatch):
    """
    If a gateway_host argument is passed to run_wifi_diag, it must be used
    for the gateway row's hostname.
    """
    monkeypatch.setattr(ping_check, "run_ping", _fake_ping_ok)

    captured = {}

    def fake_append_rows(path, rows):
        captured["rows"] = rows

    monkeypatch.setattr(wifi_diag, "append_rows", fake_append_rows)

    gw_ip = "10.0.33.1"
    wifi_diag.run_wifi_diag(rounds=1, interval=0, gateway_host=gw_ip, external_host="8.8.8.8", log_path=":memory:")

    assert "rows" in captured
    rows = captured["rows"]
    assert len(rows) >= 1
    gw_row = rows[0]
    assert gw_row["service_name"] == "gateway"
    assert gw_row["hostname"] == gw_ip


def test_autodetect_gateway_used(monkeypatch):
    """
    If gateway_host is None and net_utils.get_default_gateway_ip() returns an IP,
    the gateway row must use that IP.
    """
    monkeypatch.setattr(ping_check, "run_ping", _fake_ping_ok)
    monkeypatch.setattr(net_utils, "get_default_gateway_ip", lambda: "192.0.2.100")

    captured = {}

    def fake_append_rows(path, rows):
        captured["rows"] = rows

    monkeypatch.setattr(wifi_diag, "append_rows", fake_append_rows)

    wifi_diag.run_wifi_diag(rounds=1, interval=0, gateway_host=None, external_host="8.8.8.8", log_path=":memory:")

    rows = captured["rows"]
    gw_row = rows[0]
    assert gw_row["service_name"] == "gateway"
    assert gw_row["hostname"] == "192.0.2.100"


def test_missing_gateway_emits_config_missing_gateway(monkeypatch):
    """
    If no gateway is available (autodetect returns None and no override), the gateway
    row must have error_kind == CONFIG_MISSING_GATEWAY and empty hostname.
    """
    monkeypatch.setattr(ping_check, "run_ping", _fake_ping_ok)
    monkeypatch.setattr(net_utils, "get_default_gateway_ip", lambda: None)

    captured = {}

    def fake_append_rows(path, rows):
        captured["rows"] = rows

    monkeypatch.setattr(wifi_diag, "append_rows", fake_append_rows)

    wifi_diag.run_wifi_diag(rounds=1, interval=0, gateway_host=None, external_host="8.8.8.8", log_path=":memory:")

    rows = captured["rows"]
    gw_row = rows[0]
    assert gw_row["service_name"] == "gateway"
    assert gw_row["hostname"] == ""
    assert gw_row["error_kind"] == CONFIG_MISSING_GATEWAY


# tests/test_gateway_persist.py
import os
import shutil
import tempfile
import importlib.util

from src import main


def _load_temp_targets_module(path):
    """Dynamically load a targets_config.py from a path into a module object"""
    spec = importlib.util.spec_from_file_location("tmp_targets_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def test_persist_gateway_updates_memory(tmp_path):
    # prepare temp file and load as module object
    repo_targets = os.path.join("src", "targets_config.py")
    tmp_file = tmp_path / "targets_config.py"
    shutil.copy2(repo_targets, str(tmp_file))

    # load the temp module
    temp_mod = _load_temp_targets_module(str(tmp_file))
    gw = "192.0.2.101"

    # persist and update in-memory temp module
    ok = main.persist_gateway(gw, targets_file_path=str(tmp_file), targets_module=temp_mod)
    assert ok is True

    # module attribute updated
    assert getattr(temp_mod, "GATEWAY_HOSTNAME", None) == gw

    # services in module updated (gateway-tagged entries should have hostname)
    for svc in getattr(temp_mod, "SERVICES", []):
        tags = svc.get("tags", []) or []
        if "gateway" in tags:
            assert svc.get("hostname") == gw
