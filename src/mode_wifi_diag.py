# src/mode_wifi_diag.py
"""
NetInsight Wi-Fi diagnostic mode (simple + robust logging).

This version ensures logging is configured to print to stdout even if another
part of the application configured logging already.
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime, timezone

import targets_config
import ping_check

logger = logging.getLogger(__name__)

MODE_NAME = "wifi_diag"
LOG_PATH = os.path.join("data", "netinsight_wifi_diag.csv")

ROUNDS = 10
INTERVAL_SECONDS = 1
PING_COUNT = 3
PING_TIMEOUT = 1.0

CSV_HEADERS = [
    "timestamp",
    "mode",
    "round_id",
    "role",
    "target",
    "success",
    "latency_ms",
    "latency_p95_ms",
    "jitter_ms",
    "packet_loss_pct",
    "error_kind",
    "error_message",
]


def _find_target(name):
    for s in targets_config.SERVICES:
        if s.get("name") == name:
            return s.get("hostname")
    return None


def _avg(values):
    values = [v for v in values if isinstance(v, (int, float))]
    if not values:
        return None
    return sum(values) / len(values)


def _configure_logging():
    """
    Ensure logging prints to stdout so tests that capture stdout can see it.

    Use force=True when available; otherwise remove root handlers and reconfigure.
    """
    try:
        # Python 3.8+ supports force to reconfigure root logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True,
        )
    except TypeError:
        # Older Python: remove all handlers then configure to stdout
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])


def main():
    _configure_logging()

    gateway = _find_target("gateway")
    google = _find_target("google")

    if not gateway or not google:
        logger.error("wifi_diag: missing 'gateway' or 'google' in targets_config.SERVICES")
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    gateway_results = []
    google_results = []

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        logger.info("NetInsight Wi-Fi diag starting: rounds=%d, interval=%ds", ROUNDS, INTERVAL_SECONDS)
        logger.info("  gateway=%s", gateway)
        logger.info("  google=%s", google)

        for i in range(ROUNDS):
            rid = f"{datetime.now(timezone.utc).isoformat()}#{i}"

            for role, target in (("gateway", gateway), ("google", google)):
                res = ping_check.run_ping(target, count=PING_COUNT, timeout=PING_TIMEOUT)

                row = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": MODE_NAME,
                    "round_id": rid,
                    "role": role,
                    "target": target,
                    "success": res.get("received", 0) > 0,
                    "latency_ms": res.get("latency_avg_ms"),
                    "latency_p95_ms": res.get("latency_p95_ms"),
                    "jitter_ms": res.get("jitter_ms"),
                    "packet_loss_pct": res.get("packet_loss_pct"),
                    "error_kind": res.get("error_kind"),
                    "error_message": res.get("error"),
                }
                writer.writerow(row)

                if role == "gateway":
                    gateway_results.append(res)
                else:
                    google_results.append(res)

            time.sleep(INTERVAL_SECONDS)

    gw_lat = _avg([r.get("latency_avg_ms") for r in gateway_results])
    gw_jit = _avg([r.get("jitter_ms") for r in gateway_results])
    gw_loss = _avg([r.get("packet_loss_pct") for r in gateway_results])

    gg_lat = _avg([r.get("latency_avg_ms") for r in google_results])
    gg_jit = _avg([r.get("jitter_ms") for r in google_results])
    gg_loss = _avg([r.get("packet_loss_pct") for r in google_results])

    logger.info("\nwifi_diag summary:")
    logger.info("  gateway: latency=%s jitter=%s loss=%s", gw_lat, gw_jit, gw_loss)
    logger.info("  google:  latency=%s jitter=%s loss=%s", gg_lat, gg_jit, gg_loss)

    if any(r.get("error_kind") == "ping_no_permission" for r in gateway_results + google_results):
        logger.warning("Ping permission issue detected: ICMP may be blocked for this process. Try enabling ICMP or running with privileges.")

    # thresholds
    WIFI_JITTER_BAD = 20.0
    WIFI_LOSS_BAD = 5.0
    WIFI_GOOD_JITTER = 10.0
    WIFI_GOOD_LOSS = 2.0
    ISP_JITTER_BAD = 20.0
    ISP_LOSS_BAD = 5.0

    wifi_bad = (gw_jit is not None and gw_jit > WIFI_JITTER_BAD) or (gw_loss is not None and gw_loss > WIFI_LOSS_BAD)
    google_bad = (gg_jit is not None and gg_jit > ISP_JITTER_BAD) or (gg_loss is not None and gg_loss > ISP_LOSS_BAD)
    wifi_good = (gw_jit is not None and gw_jit < WIFI_GOOD_JITTER) and (gw_loss is not None and gw_loss < WIFI_GOOD_LOSS)

    if wifi_bad:
        logger.info("→ Likely Wi-Fi / local network problem (gateway already looks bad).")
    elif google_bad and wifi_good:
        logger.info("→ Likely ISP / upstream problem (gateway looks fine, internet looks bad).")
    else:
        logger.info("→ Inconclusive or mostly healthy in this short run.")


if __name__ == "__main__":
    main()
