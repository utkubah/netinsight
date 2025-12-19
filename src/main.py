# src/main.py
"""
NetInsight baseline logger.

This script runs the "baseline" mode:
- every INTERVAL_SECONDS, it iterates over SERVICES
- for each service, it runs ping / DNS / HTTP if enabled
- logs one row per probe to data/netinsight_log.csv

The CSV includes a 'mode' column so future modes can share the same file
or be filtered easily.
"""

import csv
import os
import time
from datetime import datetime, timezone

import ping_check
import dns_check
import http_check
from targets_config import SERVICES

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


def run_once(round_id: str):
    """Run one measurement round over all configured SERVICES."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        ping_count = 0
        dns_count = 0
        http_count = 0

        for svc in SERVICES:
            name = svc.get("name")
            hostname = svc.get("hostname")
            url = svc.get("url")
            tags = svc.get("tags", [])
            tags_str = ",".join(tags)

            # --- PING ----------------------------------------------------
            ping_cfg = svc.get("ping", {})
            if ping_cfg.get("enabled", False) and hostname:
                count = ping_cfg.get("count", 5)
                timeout = ping_cfg.get("timeout", 1.0)

                ping_result = ping_check.run_ping(hostname, count=count, timeout=timeout)

                row = {key: None for key in CSV_HEADERS}
                row["timestamp"] = datetime.now(timezone.utc).isoformat()
                row["mode"] = MODE_NAME
                row["round_id"] = round_id
                row["service_name"] = name
                row["hostname"] = hostname
                row["url"] = url
                row["tags"] = tags_str
                row["probe_type"] = "ping"
                row["success"] = ping_result.get("received", 0) > 0
                row["latency_ms"] = ping_result.get("latency_avg_ms")
                row["latency_p95_ms"] = ping_result.get("latency_p95_ms")
                row["jitter_ms"] = ping_result.get("jitter_ms")
                row["packet_loss_pct"] = ping_result.get("packet_loss_pct")
                row["status_code"] = None
                row["error_kind"] = ping_result.get("error_kind")
                row["error_message"] = ping_result.get("error")

                lat_list = ping_result.get("latencies_ms") or []
                if lat_list:
                    samples_str = ";".join(f"{x:.2f}" for x in lat_list)
                    row["details"] = f"samples={samples_str}"
                else:
                    row["details"] = ""

                writer.writerow(row)
                ping_count += 1

            # --- DNS ----------------------------------------------------
            dns_cfg = svc.get("dns", {})
            if dns_cfg.get("enabled", False) and hostname:
                dns_timeout = dns_cfg.get("timeout", 2.0)

                dns_result = dns_check.run_dns(hostname, timeout=dns_timeout)

                row = {key: None for key in CSV_HEADERS}
                row["timestamp"] = datetime.now(timezone.utc).isoformat()
                row["mode"] = MODE_NAME
                row["round_id"] = round_id
                row["service_name"] = name
                row["hostname"] = hostname
                row["url"] = url
                row["tags"] = tags_str
                row["probe_type"] = "dns"
                row["success"] = bool(dns_result.get("ok"))
                row["latency_ms"] = dns_result.get("dns_ms")
                row["latency_p95_ms"] = None
                row["jitter_ms"] = None
                row["packet_loss_pct"] = None
                row["status_code"] = None
                row["error_kind"] = dns_result.get("error_kind")
                row["error_message"] = dns_result.get("error")

                ip = dns_result.get("ip")
                if ip:
                    row["details"] = f"ip={ip}"
                else:
                    row["details"] = ""

                writer.writerow(row)
                dns_count += 1

            # --- HTTP ---------------------------------------------------
            http_cfg = svc.get("http", {})
            if http_cfg.get("enabled", False) and url:
                http_timeout = http_cfg.get("timeout", 3.0)

                http_result = http_check.run_http(url, timeout=http_timeout)

                row = {key: None for key in CSV_HEADERS}
                row["timestamp"] = datetime.now(timezone.utc).isoformat()
                row["mode"] = MODE_NAME
                row["round_id"] = round_id
                row["service_name"] = name
                row["hostname"] = hostname
                row["url"] = url
                row["tags"] = tags_str
                row["probe_type"] = "http"
                row["success"] = bool(http_result.get("ok"))
                row["latency_ms"] = http_result.get("http_ms")
                row["latency_p95_ms"] = None
                row["jitter_ms"] = None
                row["packet_loss_pct"] = None
                row["status_code"] = http_result.get("status_code")
                row["error_kind"] = http_result.get("error_kind")
                row["error_message"] = http_result.get("error")

                details_parts = []
                status_class = http_result.get("status_class")
                if status_class is not None:
                    details_parts.append(f"status_class={status_class}")

                bytes_downloaded = http_result.get("bytes")
                if bytes_downloaded is not None:
                    details_parts.append(f"bytes={bytes_downloaded}")

                redirects = http_result.get("redirects")
                if redirects is not None:
                    details_parts.append(f"redirects={redirects}")

                row["details"] = ";".join(details_parts)

                writer.writerow(row)
                http_count += 1

        print(
            f"[round {round_id}] wrote {ping_count} ping, "
            f"{dns_count} dns, {http_count} http rows"
        )


def main():
    print(
        f"NetInsight baseline logger starting: "
        f"interval={INTERVAL_SECONDS}s, mode={MODE_NAME}"
    )
    while True:
        round_id = datetime.now(timezone.utc).isoformat()
        run_once(round_id)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
