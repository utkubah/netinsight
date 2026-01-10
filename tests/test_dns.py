import socket
import pytest

from src import dns_check
from src.error_kinds import DNS_TIMEOUT


def test_dns_timeout(monkeypatch):
    # simulate socket.gethostbyname raising socket.timeout
    def fake_gethostbyname(h):
        raise socket.timeout("timed out")

    monkeypatch.setattr("socket.gethostbyname", fake_gethostbyname)
    r = dns_check.run_dns("example.com", timeout=0.1)
    assert r["error_kind"] == DNS_TIMEOUT
