"""
Unit tests for HTTP error classification.
"""

import http_check
from requests import exceptions as exc


def test_http_timeout(monkeypatch):
    monkeypatch.setattr(http_check.requests, "get", lambda *a, **k: (_ for _ in ()).throw(exc.Timeout()))
    res = http_check.run_http("https://x")
    assert res["error_kind"] == "http_timeout"


def test_http_ssl_error(monkeypatch):
    monkeypatch.setattr(http_check.requests, "get", lambda *a, **k: (_ for _ in ()).throw(exc.SSLError("ssl")))
    res = http_check.run_http("https://x")
    assert res["error_kind"] == "http_ssl_error"
