# src/main.py
"""
NetInsight main loop.

For each measurement round, we:
- loop over all SERVICES from targets_config.py
- for each service, run:
    - ping  (if enabled)
    - DNS   (if enabled)
    - HTTP  (if enabled)
- append one CSV row per probe to data/netinsight_log.csv
- print a short summary
"""

import csv
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import ping_check
import dns_check
import http_check
from targets_config import SERVICES


INTERVAL_SECONDS = 30
LOG_PATH = os.path.join("data", "netinsight_log.csv")

CSV_HEADERS = [
    "timestamp",
    "round_id",
    "service_name",
    "hostname",
    "url",
    "tags",          # comma-separated
    "probe_type",    # "ping" / "dns" / "http"
    "success",       # True/False-ish
    "latency_ms",    # ping_avg / dns_ms / http_ms
    "latency_p95_ms",
    "jitter_ms",
    "packet_loss_pct",
    "status_code",
    "error_kind",
    "error_message",
    "details",       # compact extra info (raw latencies, DNS IP, etc.)
]


def run_once() -> None:
    # Ensure data dir exists and header is written if file is new
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        start_ts = datetime.now(timezone.utc).isoformat()
        round_id = start_ts  # use start timestamp as round identifier

        ping_count = 0
        dns_count = 0
        http_count = 0

        for svc in SERVICES:
            name = svc["name"]
            hostname = svc["hostname"]
            url = svc["url"]
            tags_list: List[str] = svc.get("tags", [])
            tags_str = ",".join(tags_list)

            # --- PING -----------------------------------------------------
            ping_cfg = svc.get("ping", {})
            if ping_cfg.get("enabled", False):
                count = ping_cfg.get("count", 3)
                timeout = ping_cfg.get("timeout", 1.0)

                ping_result = ping_check.run_ping(hostname, count=count, timeout=timeout)

                lat_list = ping_result.get("latencies_ms") or []
                if lat_list:
                    lat_str = ";".join(f"{x:.2f}" for x in lat_list)
                else:
                    lat_str = ""

                success = ping_result.get("received", 0) > 0
                row: Dict[str, Any] = {key: None for key in CSV_HEADERS}
                row["timestamp"] = datetime.now(timezone.utc).isoformat()
                row["round_id"] = round_id
                row["service_name"] = name
                row["hostname"] = hostname
                row["url"] = url
                row["tags"] = tags_str
                row["probe_type"] = "ping"
                row["success"] = success
                row["latency_ms"] = ping_result.get("latency_avg_ms")
                row["latency_p95_ms"] = ping_result.get("latency_p95_ms")
                row["jitter_ms"] = ping_result.get("jitter_ms")
                row["packet_loss_pct"] = ping_result.get("packet_loss_pct")
                row["status_code"] = None
                row["error_kind"] = ping_result.get("error_kind")
                row["error_message"] = ping_result.get("error")
                row["details"] = (
                    f"min={ping_result.get('latency_min_ms')};"
                    f"max={ping_result.get('latency_max_ms')};"
                    f"samples={lat_str}"
                )

                writer.writerow(row)
                ping_count += 1

            # --- DNS ------------------------------------------------------
            dns_cfg = svc.get("dns", {})
            if dns_cfg.get("enabled", False):
                timeout = dns_cfg.get("timeout", 2.0)

                dns_result = dns_check.run_dns(hostname, timeout=timeout)

                success = bool(dns_result.get("ok"))
                row = {key: None for key in CSV_HEADERS}
                row["timestamp"] = datetime.now(timezone.utc).isoformat()
                row["round_id"] = round_id
                row["service_name"] = name
                row["hostname"] = hostname
                row["url"] = url
                row["tags"] = tags_str
                row["probe_type"] = "dns"
                row["success"] = success
                row["latency_ms"] = dns_result.get("dns_ms")
                row["latency_p95_ms"] = None
                row["jitter_ms"] = None
                row["packet_loss_pct"] = None
                row["status_code"] = None
                row["error_kind"] = dns_result.get("error_kind")
                row["error_message"] = dns_result.get("error")
                ip = dns_result.get("ip")
                row["details"] = f"ip={ip}" if ip else ""

                writer.writerow(row)
                dns_count += 1

            # --- HTTP -----------------------------------------------------
            http_cfg = svc.get("http", {})
            if http_cfg.get("enabled", False):
                timeout = http_cfg.get("timeout", 3.0)

                http_result = http_check.run_http(url, timeout=timeout)

                success = bool(http_result.get("ok"))
                row = {key: None for key in CSV_HEADERS}
                row["timestamp"] = datetime.now(timezone.utc).isoformat()
                row["round_id"] = round_id
                row["service_name"] = name
                row["hostname"] = hostname
                row["url"] = url
                row["tags"] = tags_str
                row["probe_type"] = "http"
                row["success"] = success
                row["latency_ms"] = http_result.get("http_ms")
                row["latency_p95_ms"] = None
                row["jitter_ms"] = None
                row["packet_loss_pct"] = None
                row["status_code"] = http_result.get("status_code")
                row["error_kind"] = http_result.get("error_kind")
                row["error_message"] = http_result.get("error")
                row["details"] = ""

                writer.writerow(row)
                http_count += 1

        print(
            f"[{start_ts}] round complete (round_id={round_id}): "
            f"{ping_count} ping, {dns_count} dns, {http_count} http probes"
        )


def main() -> None:
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
