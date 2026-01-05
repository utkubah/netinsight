# tests/test_service_health.py
import json
import csv
from src import mode_service_health


def test_service_health_healthy(monkeypatch, tmp_path):
    """
    DNS ok + HTTP ok => healthy
    (ping may be blocked, that's acceptable).
    """
    monkeypatch.setattr(mode_service_health.ping_check, "run_ping", lambda *a, **k: {"received": 0, "error": "no reply", "error_kind": "ping_no_reply"})
    monkeypatch.setattr(mode_service_health.dns_check, "run_dns", lambda *a, **k: {"ok": True, "ip": "1.2.3.4", "dns_ms": 5.0, "error_kind": "ok", "error": None})
    monkeypatch.setattr(mode_service_health.http_check, "run_http", lambda *a, **k: {"ok": True, "status_code": 200, "status_class": "2xx", "http_ms": 30.0, "bytes": 0, "redirects": 0, "error_kind": "ok", "error": None})

    log_path = tmp_path / "health.csv"
    state = mode_service_health.run_service_health("example.com", log_path=str(log_path))
    assert state == "healthy"

    with open(log_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    details = json.loads(rows[0]["details"])
    assert details["state"] == "healthy"


def test_service_health_server_error(monkeypatch, tmp_path):
    """
    DNS ok + HTTP 503 => service_server_error
    """
    monkeypatch.setattr(mode_service_health.ping_check, "run_ping", lambda *a, **k: {"received": 1, "error_kind": "ok"})
    monkeypatch.setattr(mode_service_health.dns_check, "run_dns", lambda *a, **k: {"ok": True, "ip": "1.2.3.4", "error_kind": "ok"})
    monkeypatch.setattr(mode_service_health.http_check, "run_http", lambda *a, **k: {"ok": False, "status_code": 503, "status_class": "5xx", "http_ms": 80.0, "error_kind": "http_non_ok_status", "error": "HTTP 503"})

    state = mode_service_health.run_service_health("down.example", log_path=str(tmp_path / "health.csv"))
    assert state == "service_server_error"


def test_service_health_dns_failure(monkeypatch, tmp_path):
    """
    DNS failure -> dns_failure or possible_blocked_or_restricted
    """
    monkeypatch.setattr(mode_service_health.ping_check, "run_ping", lambda *a, **k: {"received": 1, "error_kind": "ok"})
    monkeypatch.setattr(mode_service_health.dns_check, "run_dns", lambda *a, **k: {"ok": False, "ip": None, "dns_ms": 50.0, "error_kind": "dns_gaierror", "error": "Temporary failure in name resolution"})
    monkeypatch.setattr(mode_service_health.http_check, "run_http", lambda *a, **k: {"ok": False, "status_code": None, "status_class": None, "error_kind": "http_connection_error", "error": "DNS failure"})

    state = mode_service_health.run_service_health("blocked.example", log_path=str(tmp_path / "health.csv"))
    assert state in ("dns_failure", "possible_blocked_or_restricted")
