# tests/test_ping_behaviour.py
import subprocess
from src import ping_check


def test_ping_tool_missing(monkeypatch):
    # Simulate FileNotFoundError when running subprocess
    def fake_run(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(ping_check, "subprocess", ping_check.subprocess)  # ensure attribute exists
    monkeypatch.setattr(ping_check.subprocess, "run", fake_run)
    res = ping_check.run_ping("example.test", count=1, timeout=0.1)
    assert res["error_kind"] == "ping_tool_missing"


def test_ping_timeout(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ping", timeout=1)
    monkeypatch.setattr(ping_check.subprocess, "run", fake_run)
    res = ping_check.run_ping("example.test", count=1, timeout=0.1)
    assert res["error_kind"] == "ping_timeout"
