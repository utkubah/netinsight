"""
Service health classification tests (pure logic).

These tests prove that classify_service_state() detects:
- healthy
- possible_blocked_or_restricted
- service_server_error
- connectivity_issue_or_firewall
"""

import mode_service_health


def test_classify_healthy():
    ping = {"received": 2}
    dns = {"ok": True, "error_kind": "ok"}
    http = {"ok": True, "status_code": 200, "error_kind": "ok"}

    state, reason = mode_service_health.classify_service_state(ping, dns, http)
    assert state == "healthy"


def test_classify_possible_dns_block():
    ping = {"received": 0}
    dns = {"ok": False, "error_kind": "dns_nxdomain"}
    http = {"ok": False, "status_code": None, "error_kind": "http_dns_error"}

    state, reason = mode_service_health.classify_service_state(ping, dns, http)
    assert state == "possible_blocked_or_restricted"


def test_classify_server_error():
    ping = {"received": 1}
    dns = {"ok": True, "error_kind": "ok"}
    http = {"ok": False, "status_code": 503, "error_kind": "http_5xx"}

    state, reason = mode_service_health.classify_service_state(ping, dns, http)
    assert state == "service_server_error"


def test_classify_connectivity_firewall():
    ping = {"received": 0}
    dns = {"ok": True, "error_kind": "ok"}
    http = None

    state, reason = mode_service_health.classify_service_state(ping, dns, http)
    assert state == "connectivity_issue_or_firewall"
