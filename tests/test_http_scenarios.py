# tests/test_http_classification.py
import http_check
from requests import exceptions as req_exc


def test_http_timeout(monkeypatch):
    def fake_get(url, timeout):
        raise req_exc.Timeout("timed out")

    monkeypatch.setattr(http_check.requests, "get", fake_get)
    res = http_check.run_http("https://example.test", timeout=0.1)
    assert res["ok"] is False
    assert res["error_kind"] == "http_timeout"


def test_http_ssl_error(monkeypatch):
    def fake_get(url, timeout):
        raise req_exc.SSLError("ssl fail")

    monkeypatch.setattr(http_check.requests, "get", fake_get)
    res = http_check.run_http("https://badssl.test", timeout=0.1)
    assert res["ok"] is False
    assert res["error_kind"] == "http_ssl_error"


def test_http_4xx_and_5xx(monkeypatch):
    class FakeResp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.content = b""
            self.history = []

    def fake_get_404(url, timeout):
        return FakeResp(404)

    monkeypatch.setattr(http_check.requests, "get", fake_get_404)
    res = http_check.run_http("https://example.test/404", timeout=1.0)
    assert res["status_code"] == 404
    assert res["error_kind"] == "http_4xx"

    def fake_get_500(url, timeout):
        return FakeResp(500)

    monkeypatch.setattr(http_check.requests, "get", fake_get_500)
    res2 = http_check.run_http("https://example.test/500", timeout=1.0)
    assert res2["status_code"] == 500
    assert res2["error_kind"] == "http_5xx"
