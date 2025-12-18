# src/main.py
"""
NetInsight main loop (basic MVP).

- Runs a ping, DNS and HTTP check once and appends a CSV row under data/netinsight_log.csv.
- Prints a compact summary to stdout.
"""

import os
import csv
import time
from datetime import datetime, timezone

# Import the public names expected by tests / external code
import ping_check
import dns_check
import http_check

INTERVAL_SECONDS = 30  # how often to run tests
LOG_PATH = os.path.join("data", "netinsight_log.csv")

CSV_HEADERS = [
    "timestamp",
    # ping
    "ping_target",
    "ping_latency_avg_ms",
    "ping_packet_loss_pct",
    "ping_error",
    # dns
    "dns_hostname",
    "dns_ms",
    "dns_ok",
    "dns_error",
    # http
    "http_url",
    "http_ms",
    "http_ok",
    "http_status_code",
    "http_error",
]


def ensure_log_exists():
    """Ensure the data directory exists and the CSV has a header."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()


def run_once():
    """Run one round of checks, print a summary, and append a CSV row."""
    # Note: the checks use the simple implementations in ping_test.py, dns_test.py, http_test.py
    ping_result = ping_check.run_ping("8.8.8.8")
    dns_result = dns_check.run_dns("www.google.com")
    http_result = http_check.run_http("https://www.google.com/generate_204")

    timestamp = datetime.now(timezone.utc).isoformat()

    row = {
        "timestamp": timestamp,
        # ping
        "ping_target": ping_result.get("target"),
        "ping_latency_avg_ms": ping_result.get("latency_avg_ms"),
        "ping_packet_loss_pct": ping_result.get("packet_loss_pct"),
        "ping_error": ping_result.get("error"),
        # dns
        "dns_hostname": dns_result.get("hostname"),
        "dns_ms": dns_result.get("dns_ms"),
        "dns_ok": dns_result.get("ok"),
        "dns_error": dns_result.get("error"),
        # http
        "http_url": http_result.get("url"),
        "http_ms": http_result.get("http_ms"),
        "http_ok": http_result.get("ok"),
        "http_status_code": http_result.get("status_code"),
        "http_error": http_result.get("error"),
    }

    # Print a compact human-friendly summary
    print(
        f"[{timestamp}] ping_loss={row['ping_packet_loss_pct']}% "
        f"dns_ok={row['dns_ok']} http_ok={row['http_ok']} "
        f"http_status={row['http_status_code']}"
    )

    # Append to CSV
    ensure_log_exists()
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(row)


def main():
    ensure_log_exists()
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
