# tests/test_netinsight_checks.py

"""
Simple integration-style tests for the core NetInsight checks.

test it with pytest

These tests hit the real network:
- ping 8.8.8.8
- DNS lookup of www.google.com
- HTTP GET to https://www.google.com/generate_204

They are meant as "does it basically work?" tests,
not as perfect unit tests.
"""

import ping_check
import dns_check
import http_check

def test_run_ping_basic():
    # Use a well-known, stable host for ping
    result = ping_check.run_ping("8.8.8.8", count=2)

    # Basic structure
    assert isinstance(result, dict)
    assert result["target"] == "8.8.8.8"
    assert result["sent"] == 2
    assert 0 <= result["packet_loss_pct"] <= 100

    # If we received any replies, latency numbers should be non-None and >= 0
    if result["received"] > 0:
        assert result["latency_avg_ms"] is not None
        assert result["latency_min_ms"] is not None
        assert result["latency_max_ms"] is not None
        assert result["latency_min_ms"] >= 0
        assert result["latency_max_ms"] >= result["latency_min_ms"]
    else:
        # If everything failed, error message should be set
        assert result["latency_avg_ms"] is None
        assert result["error"] is not None


def test_run_dns_basic():
    hostname = "www.google.com"
    result = dns_check.run_dns(hostname)

    assert isinstance(result, dict)
    assert result["hostname"] == hostname
    assert isinstance(result["dns_ms"], (int, float))
    assert result["dns_ms"] >= 0

    # If lookup worked, ip should be a non-empty string
    if result["ok"]:
        assert result["ip"] is not None
        assert isinstance(result["ip"], str)
        assert result["error"] is None
    else:
        # On failure, ip should be None and we should have an error message
        assert result["ip"] is None
        assert result["error"] is not None


def test_run_http_basic():
    # Lightweight connectivity check URL
    url = "https://www.google.com/generate_204"
    result = http_check.run_http(url)

    assert isinstance(result, dict)
    assert result["url"] == url
    assert isinstance(result["http_ms"], (int, float))
    assert result["http_ms"] >= 0

    # If request succeeded, status_code should be an int and ok=True
    if result["ok"]:
        assert isinstance(result["status_code"], int)
        assert result["error"] is None
    else:
        # If it failed, status_code may be None but error should be set
        assert result["status_code"] is None or isinstance(result["status_code"], int)
        assert result["error"] is not None
