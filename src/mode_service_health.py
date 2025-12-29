# src/mode_service_health.py
"""
NetInsight service health mode (refactored).

Key improvement:
- classification logic is a pure function: classify_service_state(...)
- I/O (running probes, writing CSV, printing) is separate

This makes the code easier to test and easier to justify in a report.
"""

import argparse
import csv
import os
from datetime import datetime, timezone

import ping_check
import dns_check
import http_check

MODE_NAME = "service_health"
LOG_PATH = os.path.join("data", "netinsight_service_health.csv")

CSV_HEADERS = [
    "timestamp",
    "mode",
    "service_name",
    "hostname",
    "url",
    "ping_ok",
    "dns_ok",
    "http_ok",
    "ping_error_kind",
    "dns_error_kind",
    "http_error_kind",
    "http_status_code",
    "service_state",
    "service_reason",
]


def classify_service_state(ping_res, dns_res, http_res):
    """
    Pure classification function.

    Inputs are dicts returned by ping_check.run_ping, dns_check.run_dns, http_check.run_http.
    Returns (service_state, reason_string).
    """
    ping_ok = bool(ping_res) and ping_res.get("received", 0) > 0
    dns_ok = bool(dns_res) and bool(dns_res.get("ok"))
    http_ok = bool(http_res) and bool(http_res.get("ok"))

    http_status = http_res.get("status_code") if http_res else None
    http_ek = http_res.get("error_kind") if http_res else None

    # 1) Clean healthy case
    if dns_ok and http_ok:
        return "healthy", "DNS and HTTP OK"

    # 2) DNS failures
    if not dns_ok:
        if http_ek == "http_dns_error":
            return "possible_blocked_or_restricted", "DNS failing + HTTP DNS error (possible DNS blocking)"
        return "dns_failure", f"DNS failed ({dns_res.get('error_kind') if dns_res else 'unknown'})"

    # 3) DNS OK but HTTP problems
    if dns_ok and http_res:
        if isinstance(http_status, int) and 500 <= http_status <= 599:
            return "service_server_error", f"Server returned {http_status}"
        if isinstance(http_status, int) and 400 <= http_status <= 499:
            return "client_or_access_error", f"Client/access error {http_status}"
        if http_ek in ("http_timeout", "http_connection_error", "http_connection_reset"):
            return "connection_issue_or_blocked", f"HTTP connection problem ({http_ek})"
        return "inconclusive", "DNS OK but HTTP failed in an unclassified way"

    # 4) DNS OK but HTTP missing (shouldn't happen normally, but handle safely)
    if dns_ok and http_res is None:
        if not ping_ok:
            return "connectivity_issue_or_firewall", "DNS OK but ping failed and HTTP missing"
        return "inconclusive", "DNS OK but HTTP missing"

    return "inconclusive", "Could not classify reliably"


def check_domain_health(domain):
    """
    Runs probes, classifies state, writes one CSV row, returns the row dict.
    """
    hostname = domain
    url = f"https://{domain}"

    ping_res = ping_check.run_ping(hostname, count=3, timeout=0.7)
    dns_res = dns_check.run_dns(hostname, timeout=1.0)
    http_res = http_check.run_http(url, timeout=1.5)

    ping_ok = ping_res.get("received", 0) > 0
    dns_ok = bool(dns_res.get("ok"))
    http_ok = bool(http_res.get("ok")) if http_res else False

    service_state, reason = classify_service_state(ping_res, dns_res, http_res)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": MODE_NAME,
        "service_name": domain,
        "hostname": hostname,
        "url": url,
        "ping_ok": ping_ok,
        "dns_ok": dns_ok,
        "http_ok": http_ok,
        "ping_error_kind": ping_res.get("error_kind"),
        "dns_error_kind": dns_res.get("error_kind"),
        "http_error_kind": http_res.get("error_kind") if http_res else None,
        "http_status_code": http_res.get("status_code") if http_res else None,
        "service_state": service_state,
        "service_reason": reason,
    }

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--name", required=True, help="domain to check")
    args = parser.parse_args()

    row = check_domain_health(args.name)
    print(f"{row['service_name']}: {row['service_state']} - {row['service_reason']}")


if __name__ == "__main__":
    main()
