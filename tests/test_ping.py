import subprocess
from types import SimpleNamespace

import pytest

from src import ping_check
from src.error_kinds import PING_PERMISSION_DENIED


def _fake_completed(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_ping_permission_denied(monkeypatch):
    # fake subprocess.run returning permission-denied text
    out = "PING example.com (93.184.216.34): Permission denied"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed(stdout=out, stderr="", returncode=1))
    r = ping_check.run_ping("example.com", count=1, timeout=1.0)
    assert r["error_kind"] == PING_PERMISSION_DENIED
    assert "permission" in (r["error"] or "").lower()


def test_ping_p95_and_jitter(monkeypatch):
    # produce three latencies in stdout: time=10 ms, time=20 ms, time=30 ms
    out = "time=10.0 ms\ntime=20.0 ms\ntime=30.0 ms\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed(stdout=out, stderr="", returncode=0))
    r = ping_check.run_ping("example.com", count=3, timeout=1.0)
    # 95th percentile index calculation in code:
    # idx = int(0.95 * (len(lat_sorted) - 1)) => int(0.95 * 2) = int(1.9) = 1 => p95 == sorted[1] == 20
    assert r["latency_p95_ms"] == 20.0
    # jitter: mean absolute difference of consecutive samples in original order (10 and 10 => average 10)
    assert r["jitter_ms"] == 10.0
