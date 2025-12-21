# src/mode_wifi_diag.py
"""
Wi-Fi vs ISP diagnostic mode for NetInsight.

This mode runs a short, high-frequency ping test against:
- a local "gateway" (service named 'gateway' in targets_config.SERVICES)
- an external baseline "google" (service named 'google' in SERVICES)

It logs only ping metrics (latency, jitter, packet loss, error_kind) to
data/netinsight_wifi_diag.csv with mode=wifi_diag.

HOW TO INTERPRET RESULTS (for analysis / summary):

You get rows with:
  - role = "gateway" or "google"
  - latency_ms, latency_p95_ms, jitter_ms, packet_loss_pct, error_kind

Heuristics:

1. Likely Wi-Fi / local network problem:
   - gateway has high jitter (>20–30 ms) and/or packet_loss_pct > ~5%
   - and google is also bad or worse.
   => Problem is before leaving your local network (Wi-Fi congestion,
      interference, too many users, weak signal).

2. Likely ISP / external path problem:
   - gateway is stable (low latency, low jitter, ~0% loss)
   - but google shows high latency/jitter/loss.
   => Wi-Fi is fine; problem is on ISP / upstream / internet side.

3. Wi-Fi congestion vs constant bad Wi-Fi:
   - Congestion: gateway usually good, but during busy hours you see repeated
     bursts of bad jitter/loss.
   - Structural: gateway metrics are consistently bad most of the time.
"""

import csv
import os
import time
from datetime import datetime, timezone

import ping_check
from targets_config import SERVICES

MODE_NAME = "wifi_diag"
LOG_PATH = os.path.join("data", "netinsight_wifi_diag.csv")

ROUNDS = 20           # how many rounds to run
INTERVAL_SECONDS = 1  # seconds between rounds
PING_COUNT = 5        # pings per host per round
PING_TIMEOUT = 1.0    # seconds per ping

CSV_HEADERS = [
    "timestamp",
    "mode",
    "round_id",
    "role",             # "gateway" or "google"
    "target",
    "success",
    "latency_ms",
    "latency_p95_ms",
    "jitter_ms",
    "packet_loss_pct",
    "error_kind",
    "error_message",
    "details",
]


def main():
    # Find gateway and google from SERVICES
    gateway_host = None
    google_host = None

    for svc in SERVICES:
        name = svc.get("name")
        host = svc.get("hostname")
        if name == "gateway" and host:
            gateway_host = host
        if name == "google" and host:
            google_host = host

    if gateway_host is None:
        print(
            "wifi_diag: no 'gateway' service with a hostname found in targets_config.SERVICES.\n"
            "Please add something like:\n"
            "  {'name': 'gateway', 'hostname': '192.168.1.1', ...}\n"
        )
        return

    if google_host is None:
        print(
            "wifi_diag: no 'google' service with a hostname found in targets_config.SERVICES.\n"
            "Please add something like:\n"
            "  {'name': 'google', 'hostname': 'www.google.com', ...}\n"
        )
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    # simple accumulators for a tiny summary at the end
    stats = {
        "gateway": {
            "latency_sum": 0.0,
            "latency_count": 0,
            "jitter_sum": 0.0,
            "jitter_count": 0,
            "loss_sum": 0.0,
            "loss_count": 0,
        },
        "google": {
            "latency_sum": 0.0,
            "latency_count": 0,
            "jitter_sum": 0.0,
            "jitter_count": 0,
            "loss_sum": 0.0,
            "loss_count": 0,
        },
    }

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        print(
            f"NetInsight Wi-Fi diag starting: {ROUNDS} rounds, "
            f"interval={INTERVAL_SECONDS}s, mode={MODE_NAME}"
        )
        print(f"  gateway: {gateway_host}")
        print(f"  google:  {google_host}")

        for i in range(ROUNDS):
            round_id = f"{datetime.now(timezone.utc).isoformat()}#wifi_diag#{i}"
            timestamp = datetime.now(timezone.utc).isoformat()

            for role, host in (("gateway", gateway_host), ("google", google_host)):
                ping_result = ping_check.run_ping(
                    host,
                    count=PING_COUNT,
                    timeout=PING_TIMEOUT,
                )

                row = {key: None for key in CSV_HEADERS}
                row["timestamp"] = timestamp
                row["mode"] = MODE_NAME
                row["round_id"] = round_id
                row["role"] = role
                row["target"] = host
                row["success"] = ping_result.get("received", 0) > 0
                row["latency_ms"] = ping_result.get("latency_avg_ms")
                row["latency_p95_ms"] = ping_result.get("latency_p95_ms")
                row["jitter_ms"] = ping_result.get("jitter_ms")
                row["packet_loss_pct"] = ping_result.get("packet_loss_pct")
                row["error_kind"] = ping_result.get("error_kind")
                row["error_message"] = ping_result.get("error")

                lat_list = ping_result.get("latencies_ms") or []
                if lat_list:
                    samples_str = ";".join(f"{x:.2f}" for x in lat_list)
                    row["details"] = f"samples={samples_str}"
                else:
                    row["details"] = ""

                writer.writerow(row)

                # update simple stats for summary
                latency = ping_result.get("latency_avg_ms")
                jitter = ping_result.get("jitter_ms")
                loss = ping_result.get("packet_loss_pct")

                if isinstance(latency, (int, float)):
                    stats[role]["latency_sum"] += latency
                    stats[role]["latency_count"] += 1
                if isinstance(jitter, (int, float)):
                    stats[role]["jitter_sum"] += jitter
                    stats[role]["jitter_count"] += 1
                if isinstance(loss, (int, float)):
                    stats[role]["loss_sum"] += loss
                    stats[role]["loss_count"] += 1

            time.sleep(INTERVAL_SECONDS)

    # tiny summary / quick interpretation
    def avg(stat_dict, key_sum, key_count):
        if stat_dict[key_count] > 0:
            return stat_dict[key_sum] / stat_dict[key_count]
        return None

    gw_lat = avg(stats["gateway"], "latency_sum", "latency_count")
    gw_jit = avg(stats["gateway"], "jitter_sum", "jitter_count")
    gw_loss = avg(stats["gateway"], "loss_sum", "loss_count")

    gg_lat = avg(stats["google"], "latency_sum", "latency_count")
    gg_jit = avg(stats["google"], "jitter_sum", "jitter_count")
    gg_loss = avg(stats["google"], "loss_sum", "loss_count")

    print("\nwifi_diag summary (approx):")
    print(
        f"  gateway: latency={gw_lat:.1f} ms, jitter={gw_jit:.1f} ms, "
        f"loss={gw_loss:.1f}%"
        if gw_lat is not None and gw_jit is not None and gw_loss is not None
        else "  gateway: not enough data"
    )
    print(
        f"  google:  latency={gg_lat:.1f} ms, jitter={gg_jit:.1f} ms, "
        f"loss={gg_loss:.1f}%"
        if gg_lat is not None and gg_jit is not None and gg_loss is not None
        else "  google:  not enough data"
    )

    wifi_suspect = False
    isp_suspect = False

    # Very rough thresholds; the analysis layer can refine these later
    if gw_jit is not None and gw_loss is not None:
        if gw_jit > 20.0 or gw_loss > 5.0:
            wifi_suspect = True

    if (
        gg_jit is not None
        and gg_loss is not None
        and gw_jit is not None
        and gw_loss is not None
    ):
        if (gg_jit > 20.0 or gg_loss > 5.0) and (gw_jit < 10.0 and gw_loss < 2.0):
            isp_suspect = True

    if wifi_suspect:
        print("  → Wi-Fi / local network likely unstable (gateway already looks bad).")
    elif isp_suspect:
        print("  → Wi-Fi looks OK; problems likely after the router (ISP / internet).")
    else:
        print("  → Both paths look mostly healthy or inconclusive in this short run.")

    print("\nwifi_diag: finished.")


if __name__ == "__main__":
    main()
