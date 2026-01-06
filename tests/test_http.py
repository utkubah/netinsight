# tests/test_http_check.py
import pytest
import requests

from src import http_check
from src.error_kinds import HTTP_SSL, HTTP_CONN_ERROR


def test_http_ssl_error(monkeypatch):
    def fake_get(*a, **k):
        raise requests.exceptions.SSLError("SSL fail")

    monkeypatch.setattr(requests, "get", fake_get)
    r = http_check.run_http("https://example.com", timeout=0.1)
    assert r["error_kind"] == HTTP_SSL


def test_http_connection_error(monkeypatch):
    def fake_get(*a, **k):
        raise requests.exceptions.ConnectionError("conn fail")

    monkeypatch.setattr(requests, "get", fake_get)
    r = http_check.run_http("https://example.com", timeout=0.1)
    assert r["error_kind"] == HTTP_CONN_ERROR
