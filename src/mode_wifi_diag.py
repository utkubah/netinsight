# src/mode_wifi_diag.py
"""
NetInsight Wi-Fi diagnostic mode (simple).

Idea:
- Ping the gateway (local router) and a public target (google)
- If gateway already looks bad → likely Wi-Fi / local network issue
- If gateway looks fine but google looks bad → likely ISP / upstream issue
- Otherwise inconclusive / healthy

This mode writes a CSV for later analysis and prints a short summary.
"""

import csv
import os
import time
from datetime import datetime, timezone

import targets_config
import ping_check

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


def _summarize(role_results):
    """
    role_results is a list of ping result dicts.
    Returns (avg_latency, avg_jitter, avg_loss, error_kinds_set)
    """
    lat = [_r.get("latency_avg_ms") for _r in role_results]
    jit = [_r.get("jitter_ms") for _r in role_results]
    loss = [_r.get("packet_loss_pct") for _r in role_results]
    kinds = set([_r.get("error_kind") for _r in role_results if _r.get("error_kind")])
    return _avg(lat), _avg(jit), _avg(loss), kinds


def main():
    gateway = _find_target("gateway")
    google = _find_target("google")

    if not gateway or not google:
        print("wifi_diag: missing targets. Please define SERVICES with name='gateway' and name='google'.")
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    gateway_results = []
    google_results = []

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        print(f"NetInsight Wi-Fi diag starting: rounds={ROUNDS}, interval={INTERVAL_SECONDS}s")
        print(f"  gateway: {gateway}")
        print(f"  google:  {google}")

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

    gw_lat, gw_jit, gw_loss, gw_kinds = _summarize(gateway_results)
    gg_lat, gg_jit, gg_loss, gg_kinds = _summarize(google_results)

    print("\nwifi_diag summary:")
    print(f"  gateway: latency={gw_lat} ms, jitter={gw_jit} ms, loss={gw_loss}%  kinds={sorted(gw_kinds)}")
    print(f"  google:  latency={gg_lat} ms, jitter={gg_jit} ms, loss={gg_loss}%  kinds={sorted(gg_kinds)}")

    # Very simple decision logic (easy to explain in a report)
    # Thresholds are intentionally basic:
    WIFI_JITTER_BAD = 20.0
    WIFI_LOSS_BAD = 5.0
    ISP_JITTER_BAD = 20.0
    ISP_LOSS_BAD = 5.0
    WIFI_GOOD_JITTER = 10.0
    WIFI_GOOD_LOSS = 2.0

    # Helpful message for the common “permission denied” ping case
    if ("ping_no_permission" in gw_kinds) or ("ping_no_permission" in gg_kinds):
        print("\n→ Ping may be blocked by permissions on this system.")
        print("  Try running as admin, or allow ICMP ping. Otherwise wifi_diag will be inconclusive.")

    wifi_bad = (gw_jit is not None and gw_jit > WIFI_JITTER_BAD) or (gw_loss is not None and gw_loss > WIFI_LOSS_BAD)
    google_bad = (gg_jit is not None and gg_jit > ISP_JITTER_BAD) or (gg_loss is not None and gg_loss > ISP_LOSS_BAD)
    wifi_good = (gw_jit is not None and gw_jit < WIFI_GOOD_JITTER) and (gw_loss is not None and gw_loss < WIFI_GOOD_LOSS)

    print("")
    if wifi_bad:
        print("→ Likely Wi-Fi / local network problem (gateway already looks bad).")
    elif google_bad and wifi_good:
        print("→ Likely ISP / upstream problem (gateway looks fine, internet looks bad).")
    else:
        print("→ Inconclusive or mostly healthy in this short run.")


if __name__ == "__main__":
    main()
