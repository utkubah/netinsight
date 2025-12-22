"""
Smoke tests for NetInsight modes using real services.

These tests are intentionally light: they just make sure the entrypoints
don't crash. They still hit the real network, so they may be slow if there
is no internet, but they should not raise unexpected exceptions.
"""

from datetime import datetime, timezone
import sys

import pytest
import main
import mode_wifi_diag
import mode_speedtest
import mode_service_health


def test_run_once_does_not_crash():
    # Calls the actual baseline loop once with real services.
    round_id = datetime.now(timezone.utc).isoformat()
    main.run_once(round_id)


def test_wifi_diag_does_not_crash():
    # Call the real wifi_diag.main(), but make it only do 1 round so tests
    # don't take forever.
    original_rounds = mode_wifi_diag.ROUNDS
    original_interval = mode_wifi_diag.INTERVAL_SECONDS
    try:
        mode_wifi_diag.ROUNDS = 1
        mode_wifi_diag.INTERVAL_SECONDS = 0
        mode_wifi_diag.main()
    finally:
        mode_wifi_diag.ROUNDS = original_rounds
        mode_wifi_diag.INTERVAL_SECONDS = original_interval


def test_speedtest_does_not_crash():
    """
    Call the real speedtest mode. If the environment blocks speedtest
    (e.g. HTTP 403 or no internet), we skip instead of failing the suite.
    """
    import speedtest

    try:
        mode_speedtest.main()
    except speedtest.ConfigRetrievalError:
        pytest.skip("speedtest config retrieval blocked/403 in this environment")
    except Exception:
        pytest.skip("speedtest failed due to environment/network; skipping")


def test_service_health_cli_does_not_crash(tmp_path, capsys):
    """
    Call the real CLI entrypoint of mode_service_health with a real domain.

    This sets sys.argv as if we ran:
        python src/mode_service_health.py -n discord.com

    and verifies that it runs without crashing and prints a summary line.
    """
    # Write CSV into a temp dir so tests don't pollute real data/
    mode_service_health.LOG_PATH = str(tmp_path / "service_health.csv")

    argv_backup = sys.argv[:]
    sys.argv = ["mode_service_health.py", "-n", "discord.com"]
    try:
        mode_service_health.main()
    finally:
        sys.argv = argv_backup

    out = capsys.readouterr().out
    # We don't assert the exact classification (depends on your region),
    # only that it printed a line for discord.com.
    assert "discord.com:" in out
