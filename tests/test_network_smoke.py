# tests/test_network_smoke.py
import os
import pytest

from src import ping_check, dns_check, http_check

def test_ping_smoke():
    r = ping_check.run_ping("8.8.8.8", count=2, timeout=1.0)
    assert isinstance(r, dict)
    assert r["sent"] == 2
    assert 0 <= r["packet_loss_pct"] <= 100

def test_dns_smoke():
    r = dns_check.run_dns("www.google.com", timeout=2.0)
    assert "dns_ms" in r and r["dns_ms"] >= 0

def test_http_smoke():
    r = http_check.run_http("https://www.google.com/generate_204", timeout=3.0)
    assert "http_ms" in r and r["http_ms"] >= 0
