# src/mode_service_health.py
"""
Single-domain service health / blocked-site diagnostic for NetInsight.

Usage:
    python3 src/mode_service_health.py -n discord.com

This runs ping, DNS, and HTTP once for the given domain and classifies it as:

- healthy
- dns_failure
- service_server_error
- client_or_access_error
- possible_blocked_or_restricted
- connection_issue_or_blocked
- connectivity_issue_or_firewall
- no_probes_configured
- inconclusive

It logs one row to data/netinsight_service_health.csv and prints a summary line.
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
    "tags",
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


def check_domain_health(domain):
    """
    Run ping / DNS / HTTP once for a single domain (e.g. 'discord.com')
    and classify its health. Also appends one row to LOG_PATH.

    Returns the row dict (including service_state and service_reason).
    """
    hostname = domain
    url = f"https://{domain}"
    tags = ""  # simple, no tags

    # Slightly aggressive timeouts so it doesn't hang forever on dead networks
    ping_result = ping_check.run_ping(hostname, count=3, timeout=0.7)
    dns_result = dns_check.run_dns(hostname, timeout=1.0)
    http_result = http_check.run_http(url, timeout=1.5)

    ping_ok = False
    dns_ok = False
    http_ok = False

    ping_error_kind = None
    dns_error_kind = None
    http_error_kind = None
    http_status_code = None

    if ping_result is not None:
        ping_ok = ping_result.get("received", 0) > 0
        ping_error_kind = ping_result.get("error_kind")

    if dns_result is not None:
        dns_ok = bool(dns_result.get("ok"))
        dns_error_kind = dns_result.get("error_kind")

    if http_result is not None:
        http_ok = bool(http_result.get("ok"))
        http_error_kind = http_result.get("error_kind")
        http_status_code = http_result.get("status_code")

    # --- Classification ----------------------------------------------
    state = "inconclusive"
    reason = ""

    # nothing ran (shouldn't really happen here, but keep it)
    if ping_result is None and dns_result is None and http_result is None:
        state = "no_probes_configured"
        reason = "No ping/dns/http available for this domain."

    else:
        code = http_status_code or 0
        ek_http = http_error_kind or ""
        ek_dns = dns_error_kind or ""

        # HEALTHY: require DNS OK + HTTP OK.
        # ping is just extra information; a site can be healthy even if it blocks ping.
        if dns_ok and http_ok:
            state = "healthy"
            reason = "DNS ok and HTTP returned a successful 2xx/3xx response."

        # DNS failures at resolver level
        elif not dns_ok and dns_result is not None:
            # DNS failing both at resolver and HTTP layer (NameResolutionError etc.)
            if http_result is not None and ek_http == "http_dns_error":
                state = "possible_blocked_or_restricted"
                reason = (
                    "DNS failing at resolver and HTTP layer; may indicate "
                    "DNS-level blocking, poisoning, or region-based restrictions."
                )
            else:
                state = "dns_failure"
                reason = (
                    f"DNS failed ({ek_dns}); could be local DNS issues, "
                    "misconfiguration, or blocking."
                )

        # DNS ok, HTTP ran but not ok
        elif dns_ok and http_result is not None and not http_ok:
            if code in (403, 451):
                state = "possible_blocked_or_restricted"
                reason = (
                    f"DNS ok, HTTP status {code}; access may be region-blocked "
                    "or restricted by server/ISP."
                )
            elif ek_http in (
                "http_connection_reset",
                "http_timeout",
                "http_connection_error",
            ):
                state = "connection_issue_or_blocked"
                reason = (
                    f"DNS ok, HTTP error_kind={ek_http}; could be firewalling, "
                    "filtering, or unstable upstream connection."
                )
            elif ek_http == "http_dns_error":
                state = "possible_blocked_or_restricted"
                reason = (
                    "DNS ok at resolver, but HTTP reports DNS error; may indicate "
                    "transparent proxying or DPI interfering with requests."
                )
            elif 500 <= code < 600:
                state = "service_server_error"
                reason = f"DNS ok, server returns {code} (5xx)."
            elif 400 <= code < 500:
                state = "client_or_access_error"
                reason = f"DNS ok, server returns {code} (4xx)."
            elif ping_ok:
                # HTTP failing but ping is fine: suspicious partial connectivity
                state = "connection_issue_or_blocked"
                reason = (
                    "DNS ok and ping ok, but HTTP failing; could be filtered, "
                    "firewalled, or partially blocked."
                )
            else:
                state = "inconclusive"
                reason = (
                    f"DNS ok but HTTP failed (status={code}, "
                    f"error_kind={ek_http})."
                )

        # DNS ok, HTTP didn't even run, ping also fails: connectivity/firewall-ish
        elif dns_ok and http_result is None and not ping_ok:
            state = "connectivity_issue_or_firewall"
            reason = (
                "DNS ok but ping fails and no HTTP result; could be ICMP blocked "
                "or a deeper connectivity problem."
            )

        else:
            state = "inconclusive"
            reason = (
                f"ping_ok={ping_ok}, dns_ok={dns_ok}, http_ok={http_ok}; "
                "cannot cleanly classify."
            )

    # --- Build row and log -------------------------------------------
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": MODE_NAME,
        "service_name": domain,
        "hostname": hostname,
        "url": url,
        "tags": tags,
        "ping_ok": ping_ok,
        "dns_ok": dns_ok,
        "http_ok": http_ok,
        "ping_error_kind": ping_error_kind,
        "dns_error_kind": dns_error_kind,
        "http_error_kind": http_error_kind,
        "http_status_code": http_status_code,
        "service_state": state,
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
    parser = argparse.ArgumentParser(
        description="Single-domain service health / blocked-site check."
    )
    parser.add_argument(
        "-n",
        "--name",
        required=True,
        help="Domain name to check (e.g. discord.com)",
    )
    args = parser.parse_args()

    row = check_domain_health(args.name)
    print(f"{row['service_name']}: {row['service_state']} – {row['service_reason']}")


if __name__ == "__main__":
    main()
