import csv
from pathlib import Path

from src import main, csv_log


def test_run_once_writes_expected_number_of_rows(tmp_path, monkeypatch):
    # Two services: svc1 has ping,dns,http -> 3 rows; svc2 has ping,dns -> 2 rows. Total = 5
    services = [
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
            "url": "",
            "tags": ["test"],
            "ping": {"enabled": True, "count": 2, "timeout": 0.5},
            "dns": {"enabled": True, "timeout": 0.5},
            "http": {"enabled": False, "timeout": 0.5},
        },
    ]

    # Monkeypatch probe functions to deterministic values
    monkeypatch.setattr(main.ping_check, "run_ping", lambda host, count=3, timeout=1.0: {
        "sent": count,
        "received": count,
        "latency_avg_ms": 10.0,
        "latency_p95_ms": 15.0,
        "jitter_ms": 1.0,
        "latencies_ms": [9.8, 10.2],
        "packet_loss_pct": 0.0,
        "error": None,
        "error_kind": "ok",
    })
    monkeypatch.setattr(main.dns_check, "run_dns", lambda hostname, timeout=1.0: {
        "hostname": hostname, "ok": True, "ip": "1.2.3.4", "dns_ms": 5.0, "error": None, "error_kind": "ok"
    })
    monkeypatch.setattr(main.http_check, "run_http", lambda url, timeout=1.0: {
        "url": url, "ok": True, "status_code": 200, "status_class": "2xx", "http_ms": 50.0,
        "bytes": 1000, "redirects": 0, "error": None, "error_kind": "ok"
    })

    log_file = tmp_path / "netinsight_log.csv"
    summary = main.run_once(round_id="test-round", services=services, log_path=str(log_file))

    assert summary["total_rows"] == 5
    assert log_file.exists()

    rows = list(csv.DictReader(open(log_file, newline="", encoding="utf-8")))
    assert len(rows) == 5
    # ensure header matches our CSV_HEADERS
    assert set(rows[0].keys()) == set(csv_log.CSV_HEADERS)
    # verify each row has a JSON-like details field
    for r in rows:
        assert "details" in r
