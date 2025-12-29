"""
wifi_diag tests.

These tests simulate two real-world situations:

1) Wi-Fi problem:
   gateway is bad (high loss/jitter), but google is fine
   → should conclude Wi-Fi/local network problem

2) ISP problem:
   gateway is fine, but google is bad
   → should conclude ISP/upstream problem
"""

import mode_wifi_diag
import targets_config
import ping_check


def _ping_ok():
    return {
        "received": 3,
        "latency_avg_ms": 20.0,
        "latency_p95_ms": 40.0,
        "jitter_ms": 5.0,
        "packet_loss_pct": 0.0,
        "error_kind": "ok",
        "error": None,
    }


def _ping_bad():
    return {
        "received": 0,
        "latency_avg_ms": None,
        "latency_p95_ms": None,
        "jitter_ms": 50.0,
        "packet_loss_pct": 100.0,
        "error_kind": "ping_timeout",
        "error": "timeout",
    }


def test_wifi_problem(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mode_wifi_diag, "ROUNDS", 2)
    monkeypatch.setattr(mode_wifi_diag, "INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(mode_wifi_diag, "LOG_PATH", str(tmp_path / "wifi.csv"))

    # Make config deterministic for the test
    monkeypatch.setattr(targets_config, "SERVICES", [
        {"name": "gateway", "hostname": "GW"},
        {"name": "google", "hostname": "GG"},
    ])

    def fake_ping(target, count, timeout):
        if target == "GW":
            return _ping_bad()
        return _ping_ok()

    monkeypatch.setattr(ping_check, "run_ping", fake_ping)

    mode_wifi_diag.main()
    out = capsys.readouterr().out
    assert "Likely Wi-Fi / local network problem" in out


def test_isp_problem(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mode_wifi_diag, "ROUNDS", 2)
    monkeypatch.setattr(mode_wifi_diag, "INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(mode_wifi_diag, "LOG_PATH", str(tmp_path / "wifi.csv"))

    monkeypatch.setattr(targets_config, "SERVICES", [
        {"name": "gateway", "hostname": "GW"},
        {"name": "google", "hostname": "GG"},
    ])

    def fake_ping(target, count, timeout):
        if target == "GG":
            return _ping_bad()
        return _ping_ok()

    monkeypatch.setattr(ping_check, "run_ping", fake_ping)

    mode_wifi_diag.main()
    out = capsys.readouterr().out
    assert "Likely ISP / upstream problem" in out
