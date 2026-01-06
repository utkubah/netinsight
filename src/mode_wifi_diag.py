# src/mode_wifi_diag.py
"""
Wi-Fi diagnostic: compare gateway vs external host.

CLI usage:
  python -m src.mode_wifi_diag --gateway 192.168.1.1 --rounds 3 --interval 1 --log-path data/wifi.csv --rotate

Behavior:
- If --gateway given, it is used and persisted to config/targets.json (via main.persist_gateway).
- If --gateway not given, it tries net_utils.get_default_gateway_ip() (which checks NETINSIGHT_GATEWAY_IP).
- If no gateway found, the gateway rows are written with error_kind=config_missing_gateway.
"""
import argparse
import json
import logging
import os
import time
from datetime import datetime

from .csv_log import make_row, append_rows, utc_now_iso
from .logging_setup import setup_logging
from . import ping_check
from . import net_utils
from . import targets_config
from .error_kinds import CONFIG_MISSING_GATEWAY, PING_EXCEPTION

LOG = logging.getLogger("netinsight.wifi_diag")
LOG_PATH = os.path.join("data", "netinsight_wifi_diag.csv")


def run_wifi_diag(rounds=10, interval=1.0, gateway_host=None, external_host=None, log_path=None):
    """
    Runs the wifi diagnostic and writes rows to log_path. Returns diagnosis string.
    - rounds: number of samples (small int)
    - interval: seconds between samples
    - gateway_host: IP string or None
    - external_host: external host name or IP (defaults to targets_config.WIFI_DIAG_EXTERNAL_HOST)
    """
    if log_path is None:
        log_path = LOG_PATH

    if external_host is None:
        external_host = getattr(targets_config, "WIFI_DIAG_EXTERNAL_HOST", "www.google.com")

    # If gateway_host is None, try auto-detect (net_utils honors NETINSIGHT_GATEWAY_IP env)
    if gateway_host is None:
        gateway_host = net_utils.get_default_gateway_ip()

    round_id = utc_now_iso()
    LOG.info("wifi_diag: gateway=%s external=%s rounds=%s interval=%s", gateway_host, external_host, rounds, interval)

    rows = []
    gw_lats = []
    ex_lats = []
    gw_ok = 0
    ex_ok = 0

    for i in range(rounds):
        # Gateway probe
        if gateway_host:
            try:
                rgw = ping_check.run_ping(gateway_host, count=1, timeout=1.0)
            except Exception as e:
                rgw = {"received": 0, "latency_avg_ms": None, "error_kind": PING_EXCEPTION, "error": str(e)}
            gw_lats.append(rgw.get("latency_avg_ms"))
            if rgw.get("received", 0) > 0:
                gw_ok += 1

            rows.append(
                make_row(
                    mode="wifi_diag",
                    round_id=round_id,
                    service_name="gateway",
                    hostname=gateway_host,
                    probe_type="ping",
                    success=(rgw.get("received", 0) > 0),
                    latency_ms=rgw.get("latency_avg_ms"),
                    error_kind=rgw.get("error_kind"),
                    error_message=rgw.get("error") or "",
                    details=json.dumps({"round": i + 1}, separators=(",", ":"), sort_keys=True),
                )
            )
        else:
            # explicit missing-gateway row
            rows.append(
                make_row(
                    mode="wifi_diag",
                    round_id=round_id,
                    service_name="gateway",
                    hostname="",
                    probe_type="ping",
                    success=False,
                    error_kind=CONFIG_MISSING_GATEWAY,
                    error_message="gateway not detected",
                    details=json.dumps({"round": i + 1}, separators=(",", ":"), sort_keys=True),
                )
            )

        # External baseline probe
        try:
            rex = ping_check.run_ping(external_host, count=1, timeout=1.5)
        except Exception as e:
            rex = {"received": 0, "latency_avg_ms": None, "error_kind": PING_EXCEPTION, "error": str(e)}
        ex_lats.append(rex.get("latency_avg_ms"))
        if rex.get("received", 0) > 0:
            ex_ok += 1

        rows.append(
            make_row(
                mode="wifi_diag",
                round_id=round_id,
                service_name="external",
                hostname=external_host,
                probe_type="ping",
                success=(rex.get("received", 0) > 0),
                latency_ms=rex.get("latency_avg_ms"),
                error_kind=rex.get("error_kind"),
                error_message=rex.get("error") or "",
                details=json.dumps({"round": i + 1}, separators=(",", ":"), sort_keys=True),
            )
        )

        if interval and interval > 0:
            time.sleep(interval)

    append_rows(log_path, rows)

    # Compute medians & success rates
    gw_med = _median([v for v in gw_lats if v is not None])
    ex_med = _median([v for v in ex_lats if v is not None])
    gw_rate = gw_ok / rounds if rounds else 0
    ex_rate = ex_ok / rounds if rounds else 0

    MIN_GATEWAY_LATENCY_MS = 2.0 #this is selected since in wsl local env ping is too fast

    diagnosis = "Inconclusive or mostly healthy."

    # Rate-based hard failures first
    if gw_rate < 0.6 and ex_rate >= 0.8:
        diagnosis = "Likely Wi-Fi / local network problem."

    elif gw_rate >= 0.8 and ex_rate < 0.6:
        diagnosis = "Likely ISP / upstream problem."

    # Congestion detection (normalized gateway latency)
    elif (
        gw_rate >= 0.8 and
        ex_rate >= 0.8 and
        gw_med is not None and
        ex_med is not None
    ):
        # Normalize gateway latency so ratios remain meaningful
        gw_med_norm = max(gw_med, MIN_GATEWAY_LATENCY_MS)

        # ISP congestion: external much slower than gateway
        if (ex_med / gw_med_norm) >= 4.0:
            diagnosis = "Likely ISP congestion (external latency >> gateway)."

        # Wi-Fi congestion: gateway much slower than external
        elif (gw_med_norm / ex_med) >= 4.0:
            diagnosis = "Likely Wi-Fi congestion (gateway latency >> external)."



    LOG.info("wifi_diag result: %s", diagnosis)
    return diagnosis


def _median(values):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    m = n // 2
    if n % 2 == 1:
        return s[m]
    return (s[m - 1] + s[m]) / 2.0


def _rotate_if_requested(path):
    if os.path.exists(path):
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        new_name = "%s.%s.bak" % (path, ts)
        os.replace(path, new_name)
        LOG.info("Rotated existing log %s -> %s", path, new_name)
        print("Rotated existing log %s -> %s" % (path, new_name))


def main(argv=None):
    """
    CLI for wifi_diag. argv is optional list for tests; if None argparse reads sys.argv.
    """
    setup_logging()
    p = argparse.ArgumentParser(description="NetInsight wifi_diag mode")
    p.add_argument("--gateway", default=None, help="Override gateway IP")
    p.add_argument("--external-host", default=None, help="External host used as baseline")
    p.add_argument("--rounds", type=int, default=5, help="Number of rounds")
    p.add_argument("--interval", type=float, default=1.0, help="Seconds between rounds")
    p.add_argument("--log-path", default=LOG_PATH, help="CSV output path")
    p.add_argument("--rotate", action="store_true", help="Rotate existing CSV before writing")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = p.parse_args(argv)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.rotate and os.path.exists(args.log_path):
        _rotate_if_requested(args.log_path)

    # Decide gateway: CLI override first, else autodetect.
    gw_used = args.gateway if args.gateway else net_utils.get_default_gateway_ip()

    # If a gateway was chosen, persist it to the JSON config and update in-memory
    gw_used = args.gateway if args.gateway else net_utils.get_default_gateway_ip()

    if gw_used:
        try:
            # import here to avoid top-level circular imports
            from . import main as main_mod
            # persist to the same default JSON used by main and update in-memory targets_config
            main_mod.persist_gateway(gw_used, targets_file_path=main_mod.DEFAULT_TARGETS_JSON, targets_module=targets_config)
        except Exception:
            LOG.exception("Failed to persist gateway from wifi_diag startup")
    else:
        LOG.debug("No gateway detected/override in wifi_diag startup; gateway rows will show config_missing_gateway.")


    diagnosis = run_wifi_diag(rounds=args.rounds, interval=args.interval, gateway_host=gw_used, external_host=args.external_host, log_path=args.log_path)
    print("wifi_diag:", diagnosis)
    return diagnosis


if __name__ == "__main__":
    main()
