# tests/test_cli.py
from src import cli
from src import main as baseline_main
from src import mode_wifi_diag, mode_service_health


def test_cli_parsing_and_dispatch(monkeypatch):
    # baseline --once should call run_once
    called = {"once": False}
    monkeypatch.setattr(baseline_main, "run_once", lambda *a, **k: called.__setitem__("once", True))
    cli.main(["baseline", "--once"])
    assert called["once"]

    # wifi-diag dispatch
    monkeypatch.setattr(mode_wifi_diag, "run_wifi_diag", lambda *a, **k: "diagnosis")
    cli.main(["wifi-diag", "--rounds", "1", "--interval", "0", "--gateway", "gw", "--external", "ex"])
    # service-health dispatch
    monkeypatch.setattr(mode_service_health, "run_service_health", lambda name, log_path=None: "healthy")
    cli.main(["service-health", "--name", "example.com"])
