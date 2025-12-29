# tests/test_main_logging.py
import csv
import os

import main
import ping_check
import dns_check
import http_check
import targets_config


def test_run_once_writes_rows(monkeypatch, tmp_path):
    """
    Test that main.run_once writes one row per enabled probe for our small
    temporary SERVICES configuration.
    """
    # create a tiny services list for the test
    test_services = [
        {
            "name": "svc1",
            "hostname": "host1.test",
            "url": "https://host1.test/",
            "tags": ["test"],
            "ping": {"enabled": True, "count": 2, "timeout": 0.5},
            "dns": {"enabled": True, "timeout": 0.5},
            "http": {"enabled": True, "timeout": 0.5},
        },
        {
            "name": "svc2",
            "hostname": "host2.test",
            "url": None,
            "tags": ["test"],
            "ping": {"enabled": True, "count": 2, "timeout": 0.5},
            "dns": {"enabled": True, "timeout": 0.5},
            "http": {"enabled": False, "timeout": 0.5},
        },
    ]

    monkeypatch.setattr(targets_config, "SERVICES", test_services)

    log_file = tmp_path / "netinsight_log.csv"
    monkeypatch.setattr(main, "LOG_PATH", str(log_file))

    # fake probes
    monkeypatch.setattr(ping_check, "run_ping", lambda host, count, timeout: {
        "received": 2, "latency_avg_ms": 10.0, "latency_p95_ms": 15.0, "jitter_ms": 1.0,
        "latencies_ms": [9.8, 10.2], "packet_loss_pct": 0.0, "error": None, "error_kind": "ok"
    })
    monkeypatch.setattr(dns_check, "run_dns", lambda hostname, timeout=1.0: {
        "hostname": hostname, "ok": True, "ip": "1.2.3.4", "dns_ms": 5.0, "error": None, "error_kind": "ok"
    })
    monkeypatch.setattr(http_check, "run_http", lambda url, timeout=1.0: {
        "url": url, "ok": True, "status_code": 200, "status_class": "2xx", "http_ms": 50.0,
        "bytes": 1000, "redirects": 0, "error": None, "error_kind": "ok"
    })

    # run
    main.run_once(round_id="test-run-1")

    # read CSV and ensure rows exist
    assert log_file.exists()
    rows = []
    with open(log_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # two services: svc1 has ping,dns,http -> 3 rows; svc2 has ping,dns -> 2 rows. total = 5
    assert len(rows) == 5

    # basic checks on first row
    first = rows[0]
    assert first.get("service_name") in ("svc1", "svc2")
    assert first.get("probe_type") in ("ping", "dns", "http")
