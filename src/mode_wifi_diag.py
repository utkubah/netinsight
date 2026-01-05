# src/mode_wifi_diag.py
"""
Wi-Fi diagnostic: compare gateway vs external host.
"""

import logging
import os
import time

from .csv_log import make_row, append_rows, utc_now_iso
from .logging_setup import setup_logging
from . import ping_check
from . import net_utils
from . import targets_config

LOG = logging.getLogger("netinsight.wifi_diag")
LOG_PATH = os.path.join("data", "netinsight_wifi_diag.csv")


def run_wifi_diag(rounds=10, interval=1.0, gateway_host=None, external_host=None, log_path=None):
    if log_path is None:
        log_path = LOG_PATH

    if external_host is None:
        external_host = "www.google.com"

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
        # gateway
        if gateway_host:
            rgw = ping_check.run_ping(gateway_host, count=1, timeout=1.0)
            gw_lats.append(rgw.get("latency_avg_ms"))
            if rgw.get("received", 0) > 0:
                gw_ok += 1
            rows.append(make_row(mode="wifi_diag", round_id=round_id, service_name="gateway", hostname=gateway_host, probe_type="ping", success=(rgw.get("received", 0) > 0), latency_ms=rgw.get("latency_avg_ms"), error_kind=rgw.get("error_kind"), details=str({"round": i + 1})))
        else:
            rows.append(make_row(mode="wifi_diag", round_id=round_id, service_name="gateway", hostname="", probe_type="ping", success=False, error_kind="config_missing_gateway", error_message="gateway not detected", details=str({"round": i + 1})))

        # external
        rex = ping_check.run_ping(external_host, count=1, timeout=1.5)
        ex_lats.append(rex.get("latency_avg_ms"))
        if rex.get("received", 0) > 0:
            ex_ok += 1
        rows.append(make_row(mode="wifi_diag", round_id=round_id, service_name="external", hostname=external_host, probe_type="ping", success=(rex.get("received", 0) > 0), latency_ms=rex.get("latency_avg_ms"), error_kind=rex.get("error_kind"), details=str({"round": i + 1})))

        if interval and interval > 0:
            time.sleep(interval)

    append_rows(log_path, rows)

    # simple medians and success rates
    gw_med = _median([v for v in gw_lats if v is not None])
    ex_med = _median([v for v in ex_lats if v is not None])
    gw_rate = gw_ok / rounds if rounds else 0
    ex_rate = ex_ok / rounds if rounds else 0

    # decision rules
    if not gateway_host:
        diagnosis = "Gateway not detected: cannot perform wifi_diag."
    elif gw_rate < 0.6 and ex_rate >= 0.8:
        diagnosis = "Likely Wi-Fi / local network problem."
    elif gw_rate >= 0.8 and ex_rate < 0.6:
        diagnosis = "Likely ISP / upstream problem."
    else:
        if gw_med and ex_med and gw_med > ex_med * 2:
            diagnosis = "Likely Wi-Fi congestion (gateway latency >> external)."
        elif gw_med and ex_med and ex_med > gw_med * 2:
            diagnosis = "Likely ISP congestion (external latency >> gateway)."
        else:
            diagnosis = "Inconclusive or mostly healthy."

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


def main():
    setup_logging()
    run_wifi_diag()


if __name__ == "__main__":
    main()
