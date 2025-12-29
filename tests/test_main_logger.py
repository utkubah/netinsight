"""
Baseline logger tests.

Goal: show that one CSV row is written per enabled probe
and that the schema is stable and readable.
"""

import csv
from pathlib import Path

import main
import targets_config
import ping_check
import dns_check
import http_check


def test_run_once_writes_expected_number_of_rows(monkeypatch, tmp_path):
    """
    Two services:
      - svc1: ping + dns + http
      - svc2: ping + dns
    → total expected rows = 5
    """

    services = [
        {
            "name": "svc1",
            "hostname": "svc1.test",
            "url": "https://svc1.test",
            "tags": ["test"],
            "ping": {"enabled": True, "count": 2, "timeout": 1},
            "dns": {"enabled": True, "timeout": 1},
            "http": {"enabled": True, "timeout": 1},
        },
        {
            "name": "svc2",
            "hostname": "svc2.test",
            "url": None,
            "tags": ["test"],
            "ping": {"enabled": True, "count": 2, "timeout": 1},
            "dns": {"enabled": True, "timeout": 1},
            "http": {"enabled": False},
        },
    ]

    monkeypatch.setattr(targets_config, "SERVICES", services)
    monkeypatch.setattr(main, "LOG_PATH", str(tmp_path / "log.csv"))

    monkeypatch.setattr(ping_check, "run_ping", lambda *a, **k: {
        "received": 2,
        "latency_avg_ms": 10.0,
        "latency_p95_ms": 15.0,
        "jitter_ms": 1.0,
        "latencies_ms": [9.0, 11.0],
        "packet_loss_pct": 0.0,
        "error": None,
        "error_kind": "ok",
    })

    monkeypatch.setattr(dns_check, "run_dns", lambda *a, **k: {
        "ok": True,
        "ip": "1.2.3.4",
        "dns_ms": 5.0,
        "error": None,
        "error_kind": "ok",
    })

    monkeypatch.setattr(http_check, "run_http", lambda *a, **k: {
        "ok": True,
        "status_code": 200,
        "status_class": "2xx",
        "http_ms": 50.0,
        "bytes": 1000,
        "redirects": 0,
        "error": None,
        "error_kind": "ok",
    })

    main.run_once(round_id="test-round")

    rows = list(csv.DictReader(open(main.LOG_PATH)))
    assert len(rows) == 5
