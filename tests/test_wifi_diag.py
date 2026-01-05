# tests/test_wifi_diag.py
from src import mode_wifi_diag


def test_wifi_problem(monkeypatch, tmp_path):
    """
    Gateway latency much higher than external -> Likely Wi-Fi/local problem.
    """
    def fake_ping(target, count=1, timeout=1.0):
        if target == "gw":
            return {"received": 1, "latency_avg_ms": 150.0, "latency_p95_ms": 150.0, "jitter_ms": 20.0, "packet_loss_pct": 0.0, "error_kind": "ok", "error": None}
        return {"received": 1, "latency_avg_ms": 20.0, "latency_p95_ms": 20.0, "jitter_ms": 2.0, "packet_loss_pct": 0.0, "error_kind": "ok", "error": None}

    monkeypatch.setattr(mode_wifi_diag.ping_check, "run_ping", fake_ping)

    diag = mode_wifi_diag.run_wifi_diag(
        rounds=5,
        interval=0,
        gateway_host="gw",
        external_host="ext",
        log_path=str(tmp_path / "wifi.csv"),
    )

    assert "Wi-Fi" in diag or "local network" in diag


def test_isp_problem(monkeypatch, tmp_path):
    """
    Gateway OK, external failing -> Likely ISP / upstream problem.
    """
    def fake_ping(target, count=1, timeout=1.0):
        if target == "gw":
            return {"received": 1, "latency_avg_ms": 10.0, "latency_p95_ms": 10.0, "jitter_ms": 1.0, "packet_loss_pct": 0.0, "error_kind": "ok", "error": None}
        return {"received": 0, "latency_avg_ms": None, "latency_p95_ms": None, "jitter_ms": None, "packet_loss_pct": 100.0, "error_kind": "ping_timeout", "error": "timeout"}

    monkeypatch.setattr(mode_wifi_diag.ping_check, "run_ping", fake_ping)

    diag = mode_wifi_diag.run_wifi_diag(
        rounds=5,
        interval=0,
        gateway_host="gw",
        external_host="ext",
        log_path=str(tmp_path / "wifi.csv"),
    )

    assert "ISP" in diag or "upstream" in diag
