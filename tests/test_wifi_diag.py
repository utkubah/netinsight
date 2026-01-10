import json
from types import SimpleNamespace

from src import mode_wifi_diag
from src import net_utils
from src import csv_log
from src import ping_check


def _mk_resp(received, lat):
    return {"received": received, "latency_avg_ms": lat, "error_kind": "ok" if received else "ping_no_reply", "error": None}

def test_wifi_diag_inconclusive_not_isp(monkeypatch):
    # both reachable but external only 3x slower should NOT be labeled ISP
    def fake_ping(host, count=1, timeout=1.0):
        if host == "gateway" or host == "gw":
            return _mk_resp(1, 20.0)
        return _mk_resp(1, 60.0)  
    monkeypatch.setattr(mode_wifi_diag.ping_check, "run_ping", fake_ping)
    # monkeypatch append_rows to avoid file IO
    monkeypatch.setattr(mode_wifi_diag, "append_rows", lambda path, rows: setattr(mode_wifi_diag, "_last_rows", rows))
    diag = mode_wifi_diag.run_wifi_diag(rounds=3, interval=0, gateway_host="gw", external_host="ex", log_path=":memory:")
    assert "ISP" not in diag and "Likely ISP" not in diag

def test_wifi_diag_detects_isp_when_external_large(monkeypatch):
    # external very large (>=4x) and both have good rates
    def fake_ping(host, count=1, timeout=1.0):
        if host == "gw":
            return _mk_resp(1, 20.0)
        return _mk_resp(1, 90.0)  # 4.5x -> should be ISP now
    monkeypatch.setattr(mode_wifi_diag.ping_check, "run_ping", fake_ping)
    monkeypatch.setattr(mode_wifi_diag, "append_rows", lambda path, rows: setattr(mode_wifi_diag, "_last_rows", rows))
    diag = mode_wifi_diag.run_wifi_diag(rounds=3, interval=0, gateway_host="gw", external_host="ex", log_path=":memory:")
    assert "ISP" in diag or "upstream" in diag
