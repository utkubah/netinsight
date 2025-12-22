"""
Deep tests for NetInsight systems (offline, with monkeypatched probes).

This file focuses on:
- Robustness: functions should not crash on weird / edge-case outputs
- Classification: especially for mode_service_health
- Correct basic logging behaviour in baseline (main.run_once)

These tests DO NOT hit the real network. Your existing tests/test_modes.py
can remain as real-network smoke tests.
"""

from datetime import datetime, timezone
import csv
import sys

import pytest

import main
import mode_service_health
import mode_wifi_diag
import mode_speedtest


# ---------------------------------------------------------------------------
# Helpers for patching service_health probes
# ---------------------------------------------------------------------------

def _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret):
    """
    Monkeypatch ping_check / dns_check / http_check inside mode_service_health
    to return the given dicts (or None).
    """
    def fake_run_ping(hostname, count, timeout):
        return ping_ret

    def fake_run_dns(hostname, timeout):
        return dns_ret

    def fake_run_http(url, timeout):
        return http_ret

    monkeypatch.setattr(mode_service_health.ping_check, "run_ping", fake_run_ping)
    monkeypatch.setattr(mode_service_health.dns_check, "run_dns", fake_run_dns)
    monkeypatch.setattr(mode_service_health.http_check, "run_http", fake_run_http)


# ---------------------------------------------------------------------------
# 1) Baseline main.run_once – offline/classified probes
# ---------------------------------------------------------------------------

def test_baseline_run_once_logs_rows(tmp_path, monkeypatch):
    """
    Test main.run_once() without hitting the real network by patching:
    - main.SERVICES to a tiny config
    - main.LOG_PATH to a temporary CSV
    - ping/dns/http to synthetic results

    We then check that:
    - CSV is created
    - rows exist for ping/dns/http
    - HTTP rows include a throughput_mbps detail.
    """
    # Redirect logging to tmp_path
    log_path = tmp_path / "netinsight_log.csv"
    monkeypatch.setattr(main, "LOG_PATH", str(log_path))

    # Tiny services config
    services = [
        {
            "name": "discord",
            "hostname": "discord.com",
            "url": "https://discord.com",
            "tags": ["social", "gaming"],
            "ping": {"enabled": True, "count": 3, "timeout": 0.1},
            "dns": {"enabled": True, "timeout": 0.1},
            "http": {"enabled": True, "timeout": 0.2},
        }
    ]
    monkeypatch.setattr(main, "SERVICES", services)

    # Fake probe outputs
    def fake_run_ping(hostname, count, timeout):
        return {
            "received": count,
            "latency_avg_ms": 20.0,
            "latency_p95_ms": 30.0,
            "jitter_ms": 2.0,
            "packet_loss_pct": 0.0,
            "latencies_ms": [18.0, 20.0, 22.0],
            "error": None,
            "error_kind": None,
        }

    def fake_run_dns(hostname, timeout):
        return {
            "ok": True,
            "ip": "1.2.3.4",
            "dns_ms": 5.0,
            "error": None,
            "error_kind": None,
        }

    def fake_run_http(url, timeout):
        return {
            "ok": True,
            "status_code": 200,
            "http_ms": 100.0,
            "bytes": 200_000,   # 200 KB
            "redirects": 0,
            "status_class": "2xx",
            "error": None,
            "error_kind": None,
        }

    monkeypatch.setattr(main.ping_check, "run_ping", fake_run_ping)
    monkeypatch.setattr(main.dns_check, "run_dns", fake_run_dns)
    monkeypatch.setattr(main.http_check, "run_http", fake_run_http)

    round_id = datetime.now(timezone.utc).isoformat()
    main.run_once(round_id)

    # Read back CSV
    assert log_path.exists()
    with log_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Expect 3 rows for 1 service (ping + dns + http)
    assert len(rows) == 3
    probe_types = {row["probe_type"] for row in rows}
    assert probe_types == {"ping", "dns", "http"}

    # Check HTTP row has throughput_mbps in details
    http_rows = [r for r in rows if r["probe_type"] == "http"]
    assert len(http_rows) == 1
    assert "throughput_mbps=" in http_rows[0]["details"]


# ---------------------------------------------------------------------------
# 2) Service health classification – edge cases for discord.com style patterns
# ---------------------------------------------------------------------------

def test_service_health_healthy_when_dns_and_http_ok(tmp_path, monkeypatch):
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_healthy.csv")

    ping_ret = {"received": 3, "error_kind": None}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = {"ok": True, "status_code": 200, "error_kind": None}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "healthy"
    assert "DNS ok" in row["service_reason"] or "HTTP" in row["service_reason"]


def test_service_health_dns_failure(tmp_path, monkeypatch):
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_dns_failure.csv")

    ping_ret = {"received": 0, "error_kind": "ping_dns_failure"}
    dns_ret = {"ok": False, "error_kind": "dns_temp_failure"}
    http_ret = {"ok": False, "status_code": None, "error_kind": None}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "dns_failure"
    assert "dns" in row["service_reason"].lower()


def test_service_health_possible_blocked_dns_layer(tmp_path, monkeypatch):
    """
    DNS fails at resolver AND http_check reports http_dns_error:
    treat as possible_blocked_or_restricted (e.g. Discord-style DNS blocking).
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_blocked_dns.csv")

    ping_ret = {"received": 0, "error_kind": "ping_dns_failure"}
    dns_ret = {"ok": False, "error_kind": "dns_temp_failure"}
    http_ret = {"ok": False, "status_code": None, "error_kind": "http_dns_error"}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "possible_blocked_or_restricted"
    assert "dns" in row["service_reason"].lower()


def test_service_health_possible_blocked_http_403(tmp_path, monkeypatch):
    """
    DNS ok but HTTP returns 403: common for region blocking or access restriction.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_403.csv")

    ping_ret = {"received": 3, "error_kind": None}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = {"ok": False, "status_code": 403, "error_kind": None}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "possible_blocked_or_restricted"
    assert "403" in row["service_reason"]


def test_service_health_connection_issue_http_timeout(tmp_path, monkeypatch):
    """
    DNS ok, HTTP times out: classify as connection_issue_or_blocked.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_timeout.csv")

    ping_ret = {"received": 3, "error_kind": None}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = {"ok": False, "status_code": None, "error_kind": "http_timeout"}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "connection_issue_or_blocked"
    assert "timeout" in row["service_reason"].lower()


def test_service_health_service_server_error_5xx(tmp_path, monkeypatch):
    """
    DNS ok, HTTP 5xx: service_server_error.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_5xx.csv")

    ping_ret = {"received": 3, "error_kind": None}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = {"ok": False, "status_code": 503, "error_kind": None}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "service_server_error"
    assert "503" in row["service_reason"]


def test_service_health_client_or_access_error_4xx(tmp_path, monkeypatch):
    """
    DNS ok, HTTP 4xx: client_or_access_error (bad URL, no auth, rate limit, etc).
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_4xx.csv")

    ping_ret = {"received": 3, "error_kind": None}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = {"ok": False, "status_code": 404, "error_kind": None}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "client_or_access_error"
    assert "404" in row["service_reason"]


def test_service_health_connectivity_issue_or_firewall(tmp_path, monkeypatch):
    """
    DNS ok, no HTTP result, and ping fails: connectivity_issue_or_firewall.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_firewall.csv")

    ping_ret = {"received": 0, "error_kind": "ping_timeout"}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = None  # http_check didn't run / couldn't run

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "connectivity_issue_or_firewall"
    assert (
        "ping fails" in row["service_reason"].lower()
        or "connectivity" in row["service_reason"].lower()
    )


def test_service_health_connection_issue_dns_ok_ping_ok_http_weird(tmp_path, monkeypatch):
    """
    DNS ok, ping ok, HTTP fails in an odd way: connection_issue_or_blocked.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_partial.csv")

    ping_ret = {"received": 3, "error_kind": None}
    dns_ret = {"ok": True, "error_kind": None}
    http_ret = {"ok": False, "status_code": None, "error_kind": None}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "connection_issue_or_blocked"


def test_service_health_inconclusive_fallback(tmp_path, monkeypatch):
    """
    Weird combination that should hit the final 'inconclusive' fallback.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_inconclusive.csv")

    ping_ret = {"received": 0, "error_kind": None}
    dns_ret = None    # dns_check returned None unexpectedly
    http_ret = None

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    row = mode_service_health.check_domain_health("discord.com")
    assert row["service_state"] == "inconclusive"
    assert "cannot cleanly classify" in row["service_reason"].lower()


def test_service_health_weird_domain_string_does_not_crash(tmp_path, monkeypatch):
    """
    Test robustness against odd 'domain' input. We don't hit the real network,
    we just ensure function returns a dict and doesn't explode on weird names.
    """
    mode_service_health.LOG_PATH = str(tmp_path / "service_health_weird.csv")

    ping_ret = {"received": 0, "error_kind": "ping_dns_failure"}
    dns_ret = {"ok": False, "error_kind": "dns_temp_failure"}
    http_ret = {"ok": False, "status_code": None, "error_kind": "http_dns_error"}

    _patch_service_health_probes(monkeypatch, ping_ret, dns_ret, http_ret)

    weird_domain = "discord.com ; rm -rf /"
    row = mode_service_health.check_domain_health(weird_domain)
    assert isinstance(row, dict)
    # We don't care about exact state, just that there's some classification string
    assert "service_state" in row
    assert "service_reason" in row


# ---------------------------------------------------------------------------
# 3) mode_wifi_diag – robustness with synthetic services
# ---------------------------------------------------------------------------

def test_wifi_diag_with_fake_services(tmp_path, monkeypatch, capsys):
    """
    Test mode_wifi_diag.main() without real network:
    - patch SERVICES to contain gateway + google
    - patch ping_check.run_ping to synthetic results
    - redirect LOG_PATH to tmp_path
    """
    import mode_wifi_diag  # re-import to ensure we patch the right module

    mode_wifi_diag.LOG_PATH = str(tmp_path / "wifi_diag.csv")

    fake_services = [
        {
            "name": "gateway",
            "hostname": "192.168.1.1",
            "tags": ["local", "wifi"],
            "ping": {"enabled": True, "count": 5, "timeout": 0.1},
        },
        {
            "name": "google",
            "hostname": "8.8.8.8",
            "tags": ["internet"],
            "ping": {"enabled": True, "count": 5, "timeout": 0.1},
        },
    ]
    monkeypatch.setattr(mode_wifi_diag, "SERVICES", fake_services, raising=False)

    # synthetic ping results: gateway worse than google
    def fake_run_ping(hostname, count, timeout):
        if hostname == "192.168.1.1":
            return {
                "received": count,
                "latency_avg_ms": 30.0,
                "latency_p95_ms": 50.0,
                "jitter_ms": 10.0,
                "packet_loss_pct": 5.0,
                "error": None,
                "error_kind": None,
            }
        else:
            return {
                "received": count,
                "latency_avg_ms": 10.0,
                "latency_p95_ms": 15.0,
                "jitter_ms": 2.0,
                "packet_loss_pct": 0.0,
                "error": None,
                "error_kind": None,
            }

    monkeypatch.setattr(mode_wifi_diag.ping_check, "run_ping", fake_run_ping)

    # make it only one round for tests
    original_rounds = mode_wifi_diag.ROUNDS
    original_interval = mode_wifi_diag.INTERVAL_SECONDS
    try:
        mode_wifi_diag.ROUNDS = 1
        mode_wifi_diag.INTERVAL_SECONDS = 0
        mode_wifi_diag.main()
    finally:
        mode_wifi_diag.ROUNDS = original_rounds
        mode_wifi_diag.INTERVAL_SECONDS = original_interval

    out = capsys.readouterr().out
    # We don't assert exact wording; just ensure something was printed
    assert out.strip() != ""

    # Check CSV exists and has at least two rows (gateway + google)
    assert (tmp_path / "wifi_diag.csv").exists()
    with (tmp_path / "wifi_diag.csv").open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= 2


# ---------------------------------------------------------------------------
# 4) mode_speedtest – robustness with fake speedtest client
# ---------------------------------------------------------------------------

def test_speedtest_fake_client(tmp_path, monkeypatch, capsys):
    """
    Test mode_speedtest.main() with a fake Speedtest client:
    - no real HTTP calls
    - check outputs and that it doesn't crash on weird values
    """
    import mode_speedtest  # re-import

    class DummyResults:
        def dict(self):
            return {
                "server": {"name": "dummy-server", "sponsor": "dummy-sponsor"},
                "ping": 42.0,
            }

    class DummyST:
        def get_servers(self):
            pass

        def get_best_server(self):
            pass

        def download(self):
            return 12_345_678  # ~12.3 Mbps

        def upload(self):
            return 1_234_567   # ~1.23 Mbps

        @property
        def results(self):
            return DummyResults()

    class DummySpeedtestModule:
        def Speedtest(self):
            return DummyST()

    # Monkeypatch the speedtest module used inside mode_speedtest
    monkeypatch.setattr(mode_speedtest, "speedtest", DummySpeedtestModule())

    mode_speedtest.main()
    out = capsys.readouterr().out

    assert "Speedtest server" in out
    assert "dummy-server" in out
    assert "dummy-sponsor" in out
    assert "Download" in out
    assert "Upload" in out


# ---------------------------------------------------------------------------
# 5) mode_service_health CLI – argument handling (no real network)
# ---------------------------------------------------------------------------

def test_service_health_cli_missing_name_exits():
    """
    If -n/--name is missing, argparse should exit with SystemExit(2).
    This is expected behaviour, not a crash.
    """
    argv_backup = sys.argv[:]
    sys.argv = ["mode_service_health.py"]  # no -n
    try:
        with pytest.raises(SystemExit) as exc:
            mode_service_health.main()
        # argparse uses exit code 2 for argument errors
        assert exc.value.code == 2
    finally:
        sys.argv = argv_backup
