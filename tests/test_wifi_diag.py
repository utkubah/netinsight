# tests/test_mode_wifi_diag.py
import json
from types import SimpleNamespace

from src import mode_wifi_diag
from src import net_utils
from src import csv_log
from src import ping_check


def test_wifi_diag_gateway_missing(monkeypatch):
    # Make get_default_gateway_ip return None
    monkeypatch.setattr(net_utils, "get_default_gateway_ip", lambda: None)

    # fake ping_check.run_ping: for gateway it's not called; for external return a good reply
    def fake_run_ping(target, count=1, timeout=1.0):
        if target == "www.google.com":
            return {"received": 1, "latency_avg_ms": 20.0, "error_kind": "ok"}
        return {"received": 0, "latency_avg_ms": None, "error_kind": "ping_no_reply"}

    monkeypatch.setattr(ping_check, "run_ping", fake_run_ping)

    captured = {}

    def fake_append_rows(path, rows):
        captured["rows"] = rows
        # do nothing else; don't write filesystem

    # <-- patch the function used inside mode_wifi_diag
    monkeypatch.setattr(mode_wifi_diag, "append_rows", fake_append_rows)

    diagnosis = mode_wifi_diag.run_wifi_diag(rounds=1, interval=0, gateway_host=None, external_host=None, log_path=":memory:")
    assert "Gateway not detected" in diagnosis

    # Expect two rows: gateway (with config_missing_gateway) and external
    rows = captured.get("rows") or []
    assert len(rows) == 2
    gw_row = rows[0]
    assert gw_row["service_name"] == "gateway"
    assert gw_row["error_kind"] == "config_missing_gateway"
    ex_row = rows[1]
    assert ex_row["service_name"] == "external"
