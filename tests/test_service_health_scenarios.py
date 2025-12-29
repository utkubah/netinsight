# tests/test_service_health_scenarios.py
import os

import ping_check
import dns_check
import http_check
import mode_wifi_diag
import mode_service_health


def _make_bad_ping(received=0, jitter=30.0, loss=100.0):
    return {
        "received": received,
        "latency_avg_ms": None if received == 0 else 100.0,
        "latency_p95_ms": None if received == 0 else 250.0,
        "jitter_ms": jitter,
        "latencies_ms": [] if received == 0 else [100.0, 250.0],
        "packet_loss_pct": loss,
        "error_kind": "ping_timeout" if received == 0 else "ok",
    }


def _make_ok_ping():
    return {
        "received": 3,
        "latency_avg_ms": 20.0,
        "latency_p95_ms": 40.0,
        "jitter_ms": 5.0,
        "latencies_ms": [18.0, 22.0, 20.0],
        "packet_loss_pct": 0.0,
        "error_kind": "ok",
    }


def test_wifi_diag_detects_wifi_suspect(monkeypatch, tmp_path, capsys):
    """
    If gateway has high jitter/loss, wifi_diag should conclude Wi-Fi/local issue.
    """
    monkeypatch.setattr(mode_wifi_diag, "ROUNDS", 3)
    monkeypatch.setattr(mode_wifi_diag, "INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(mode_wifi_diag, "PING_COUNT", 3)
    monkeypatch.setattr(mode_wifi_diag, "LOG_PATH", str(tmp_path / "wifi_diag.csv"))

    def fake_run_ping(host, count, timeout):
        if "192.168" in host or host.startswith("127.") or "gateway" in host:
            return _make_bad_ping(received=0, jitter=30.0, loss=100.0)
        else:
            return _make_ok_ping()

    monkeypatch.setattr(ping_check, "run_ping", fake_run_ping)

    mode_wifi_diag.main()
    out = capsys.readouterr().out
    assert "Wi-Fi / local network likely unstable" in out


def test_wifi_diag_detects_isp_suspect(monkeypatch, tmp_path, capsys):
    """
    If gateway looks OK but google has high jitter/loss, point at ISP.
    """
    monkeypatch.setattr(mode_wifi_diag, "ROUNDS", 3)
    monkeypatch.setattr(mode_wifi_diag, "INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(mode_wifi_diag, "PING_COUNT", 3)
    monkeypatch.setattr(mode_wifi_diag, "LOG_PATH", str(tmp_path / "wifi_diag.csv"))

    def fake_run_ping(host, count, timeout):
        if "192.168" in host or host.startswith("127.") or "gateway" in host:
            return _make_ok_ping()
        else:
            # google is bad
            return _make_bad_ping(received=1, jitter=40.0, loss=66.6)

    monkeypatch.setattr(ping_check, "run_ping", fake_run_ping)

    mode_wifi_diag.main()
    out = capsys.readouterr().out
    assert "problems likely after the router" in out or "problems likely after" in out


def test_service_health_blocked_vs_server_error(monkeypatch, tmp_path):
    """
    - DNS failing + HTTP http_dns_error -> possible_blocked_or_restricted
    - DNS ok + HTTP 5xx -> service_server_error
    """
    # Case 1: DNS failing and HTTP reports http_dns_error
    monkeypatch.setattr(dns_check, "run_dns", lambda hostname, timeout=1.0: {
        "hostname": hostname, "ok": False, "ip": None, "dns_ms": 1.0, "error": "nxdomain", "error_kind": "dns_nxdomain"
    })
    monkeypatch.setattr(http_check, "run_http", lambda url, timeout=1.5: {
        "url": url, "ok": False, "status_code": None, "status_class": None, "http_ms": 10.0, "bytes": None, "redirects": None,
        "error": "http dns error", "error_kind": "http_dns_error"
    })
    monkeypatch.setattr(ping_check, "run_ping", lambda target, count=3, timeout=0.7: {"received": 0, "error_kind": "ping_timeout"})

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "possible_blocked_or_restricted"

    # Case 2: DNS ok, HTTP 503
    monkeypatch.setattr(dns_check, "run_dns", lambda hostname, timeout=1.0: {
        "hostname": hostname, "ok": True, "ip": "1.2.3.4", "dns_ms": 1.0, "error": None, "error_kind": "ok"
    })
    monkeypatch.setattr(http_check, "run_http", lambda url, timeout=1.5: {
        "url": url, "ok": False, "status_code": 503, "status_class": "5xx", "http_ms": 200.0, "bytes": 0, "redirects": 0,
        "error": None, "error_kind": "http_5xx"
    })
    row = mode_service_health.check_domain_health("example.com")
    assert row["service_state"] == "service_server_error"


def test_service_health_connectivity_firewall(monkeypatch):
    """
    DNS ok, no HTTP result, ping fails -> connectivity_issue_or_firewall
    """
    monkeypatch.setattr(dns_check, "run_dns", lambda hostname, timeout=1.0: {
        "hostname": hostname, "ok": True, "ip": "1.2.3.4", "dns_ms": 1.0, "error": None, "error_kind": "ok"
    })
    monkeypatch.setattr(http_check, "run_http", lambda url, timeout=1.5: None)
    monkeypatch.setattr(ping_check, "run_ping", lambda target, count=3, timeout=0.7: {"received": 0, "error_kind": "ping_timeout"})

    row = mode_service_health.check_domain_health("somesite.test")
    assert row["service_state"] == "connectivity_issue_or_firewall"
