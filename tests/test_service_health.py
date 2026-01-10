import pytest

from src.mode_service_health import classify_service_state


def test_dns_blocked():
    ping_r = {"received": 0}
    dns_r = {"ok": False, "error": "Name or service not known"}
    http_r = {"ok": False}
    assert classify_service_state(ping_r, dns_r, http_r) == "possible_blocked_or_restricted"


def test_dns_timeout():
    ping_r = {"received": 0}
    dns_r = {"ok": False, "error": "DNS timeout"}
    http_r = {"ok": False}
    assert classify_service_state(ping_r, dns_r, http_r) == "dns_failure"


def test_http_healthy():
    ping_r = {"received": 1}
    dns_r = {"ok": True}
    http_r = {"ok": True}
    assert classify_service_state(ping_r, dns_r, http_r) == "healthy"


def test_http_5xx():
    ping_r = {"received": 1}
    dns_r = {"ok": True}
    http_r = {"ok": False, "status_class": "5xx"}
    assert classify_service_state(ping_r, dns_r, http_r) == "service_server_error"


def test_http_4xx():
    ping_r = {"received": 1}
    dns_r = {"ok": True}
    http_r = {"ok": False, "status_class": "4xx"}
    assert classify_service_state(ping_r, dns_r, http_r) == "client_or_access_error"


def test_http_timeout_with_ping():
    ping_r = {"received": 2}
    dns_r = {"ok": True}
    http_r = {"ok": False, "error_kind": "http_timeout"}
    assert classify_service_state(ping_r, dns_r, http_r) == "connection_issue_or_blocked"


def test_http_timeout_without_ping():
    ping_r = {"received": 0}
    dns_r = {"ok": True}
    http_r = {"ok": False, "error_kind": "http_timeout"}
    assert classify_service_state(ping_r, dns_r, http_r) == "connectivity_issue_or_firewall"


def test_http_ssl_mapping_with_ping():
    ping_r = {"received": 1}
    dns_r = {"ok": True}
    http_r = {"ok": False, "error_kind": "http_ssl_error"}
    assert classify_service_state(ping_r, dns_r, http_r) == "connection_issue_or_blocked"


def test_http_missing_ping_zero():
    ping_r = {"received": 0}
    dns_r = {"ok": True}
    http_r = None
    assert classify_service_state(ping_r, dns_r, http_r) == "connectivity_issue_or_firewall"


def test_http_missing_ping_nonzero():
    ping_r = {"received": 3}
    dns_r = {"ok": True}
    http_r = None
    assert classify_service_state(ping_r, dns_r, http_r) == "inconclusive"
