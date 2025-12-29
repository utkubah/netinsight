# src/main.py
"""
NetInsight baseline logger.

Periodically runs ping, DNS, and HTTP probes defined in targets_config.SERVICES
and appends one CSV row per probe.

Design goals:
- simple, readable code
- deterministic CSV schema
- runtime access to targets_config.SERVICES (no import-time freezing)
"""

import csv
import os
import time
from datetime import datetime, timezone

import targets_config
import ping_check
import dns_check
import http_check

INTERVAL_SECONDS = 30
LOG_PATH = os.path.join("data", "netinsight_log.csv")
MODE_NAME = "baseline"

CSV_HEADERS = [
    "timestamp",
    "mode",
    "round_id",
    "service_name",
    "hostname",
    "url",
    "tags",
    "probe_type",
    "success",
    "latency_ms",
    "latency_p95_ms",
    "jitter_ms",
    "packet_loss_pct",
    "status_code",
    "error_kind",
    "error_message",
    "details",
]


def run_once(round_id=None):
    """
    Run one full probe round over all services and append rows to CSV.
    """
    if round_id is None:
        round_id = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        ping_count = dns_count = http_count = 0

        for svc in targets_config.SERVICES:
            name = svc.get("name")
            hostname = svc.get("hostname")
            url = svc.get("url")
            tags = ",".join(svc.get("tags", []))

            # --- PING --------------------------------------------------
            ping_cfg = svc.get("ping", {})
            if ping_cfg.get("enabled") and hostname:
                res = ping_check.run_ping(
                    hostname,
                    count=ping_cfg.get("count", 5),
                    timeout=ping_cfg.get("timeout", 1.0),
                )

                row = dict.fromkeys(CSV_HEADERS, "")
                row.update({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": MODE_NAME,
                    "round_id": round_id,
                    "service_name": name,
                    "hostname": hostname,
                    "url": url,
                    "tags": tags,
                    "probe_type": "ping",
                    "success": res.get("received", 0) > 0,
                    "latency_ms": res.get("latency_avg_ms"),
                    "latency_p95_ms": res.get("latency_p95_ms"),
                    "jitter_ms": res.get("jitter_ms"),
                    "packet_loss_pct": res.get("packet_loss_pct"),
                    "error_kind": res.get("error_kind"),
                    "error_message": res.get("error"),
                })

                samples = res.get("latencies_ms") or []
                if samples:
                    row["details"] = "samples=" + "|".join(f"{x:.1f}" for x in samples)

                writer.writerow(row)
                ping_count += 1

            # --- DNS ---------------------------------------------------
            dns_cfg = svc.get("dns", {})
            if dns_cfg.get("enabled") and hostname:
                res = dns_check.run_dns(
                    hostname,
                    timeout=dns_cfg.get("timeout", 2.0),
                )

                row = dict.fromkeys(CSV_HEADERS, "")
                row.update({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": MODE_NAME,
                    "round_id": round_id,
                    "service_name": name,
                    "hostname": hostname,
                    "url": url,
                    "tags": tags,
                    "probe_type": "dns",
                    "success": bool(res.get("ok")),
                    "latency_ms": res.get("dns_ms"),
                    "error_kind": res.get("error_kind"),
                    "error_message": res.get("error"),
                    "details": f"ip={res.get('ip')}" if res.get("ip") else "",
                })

                writer.writerow(row)
                dns_count += 1

            # --- HTTP --------------------------------------------------
            http_cfg = svc.get("http", {})
            if http_cfg.get("enabled") and url:
                res = http_check.run_http(
                    url,
                    timeout=http_cfg.get("timeout", 3.0),
                )

                row = dict.fromkeys(CSV_HEADERS, "")
                row.update({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": MODE_NAME,
                    "round_id": round_id,
                    "service_name": name,
                    "hostname": hostname,
                    "url": url,
                    "tags": tags,
                    "probe_type": "http",
                    "success": bool(res.get("ok")),
                    "latency_ms": res.get("http_ms"),
                    "status_code": res.get("status_code"),
                    "error_kind": res.get("error_kind"),
                    "error_message": res.get("error"),
                })

                details = []
                if res.get("status_class"):
                    details.append(f"status_class={res.get('status_class')}")
                if res.get("bytes") is not None:
                    details.append(f"bytes={res.get('bytes')}")
                if res.get("redirects") is not None:
                    details.append(f"redirects={res.get('redirects')}")

                row["details"] = ";".join(details)
                writer.writerow(row)
                http_count += 1

        print(
            f"[round {round_id}] "
            f"wrote {ping_count} ping, {dns_count} dns, {http_count} http rows"
        )


def main():
    print(f"NetInsight baseline logger starting (interval={INTERVAL_SECONDS}s)")
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
