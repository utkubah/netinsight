"""
Service health: ping + dns + http for a single domain.
Provides classify_service_state() and run_service_health().
"""
import json
import logging
import os

from .csv_log import make_row, append_rows, utc_now_iso
from .logging_setup import setup_logging
from . import ping_check
from . import dns_check
from . import http_check
from .error_kinds import PING_EXCEPTION, DNS_EXCEPTION, HTTP_EXCEPTION

LOG = logging.getLogger("netinsight.service_health")
LOG_PATH = os.path.join("data", "netinsight_service_health.csv")


def classify_service_state(ping_r, dns_r, http_r):
    # DNS failing first
    if not dns_r.get("ok"):
        msg = (dns_r.get("error") or "").lower()
        if "name or service not known" in msg or "not known" in msg:
            return "possible_blocked_or_restricted"
        if "timeout" in msg or "gaierror" in msg:
            return "dns_failure"
        return "dns_failure"

    # If HTTP OK -> healthy
    if http_r and http_r.get("ok"):
        return "healthy"

    # HTTP present but not ok
    if http_r:
        sc = http_r.get("status_class") or ""
        if sc == "5xx":
            return "service_server_error"
        if sc == "4xx":
            return "client_or_access_error"

        ek = (http_r.get("error_kind") or "").lower()
        if "timeout" in ek:
            if ping_r.get("received", 0) > 0:
                return "connection_issue_or_blocked"
            return "connectivity_issue_or_firewall"
        if "ssl" in ek or "connection" in ek:
            if ping_r.get("received", 0) > 0:
                return "connection_issue_or_blocked"
            return "connectivity_issue_or_firewall"

    # HTTP missing
    if not http_r:
        if ping_r.get("received", 0) == 0:
            return "connectivity_issue_or_firewall"
        return "inconclusive"

    return "inconclusive"


def run_service_health(domain, log_path=None):
    if log_path is None:
        log_path = LOG_PATH

    round_id = utc_now_iso()
    url = f"https://{domain}"

    try:
        ping_r = ping_check.run_ping(domain, count=2, timeout=1.5)
    except Exception as e:
        ping_r = {"received": 0, "error_kind": PING_EXCEPTION, "error": str(e)}

    try:
        dns_r = dns_check.run_dns(domain, timeout=2.5)
    except Exception as e:
        dns_r = {"ok": False, "ip": None, "error_kind": DNS_EXCEPTION, "error": str(e)}

    try:
        http_r = http_check.run_http(url, timeout=5.0)
    except Exception as e:
        http_r = {"ok": False, "error_kind": HTTP_EXCEPTION, "error": str(e)}

    state = classify_service_state(ping_r, dns_r, http_r)

    details = json.dumps({"ping": ping_r, "dns": dns_r, "http": http_r, "state": state}, separators=(",", ":"), sort_keys=True)

    row = make_row(
        mode="service_health",
        round_id=round_id,
        service_name=domain,
        hostname=domain,
        url=url,
        tags="service_health",
        probe_type="service_health",
        success=(state == "healthy"),
        latency_ms=http_r.get("http_ms") if http_r else None,
        status_code=http_r.get("status_code") if http_r else None,
        error_kind=state,
        error_message=(http_r.get("error") or dns_r.get("error") or ping_r.get("error") or ""),
        details=details,
    )

    append_rows(log_path, [row])
    LOG.info("service_health %s => %s", domain, state)
    return state


def main():
    setup_logging()
    import argparse

    p = argparse.ArgumentParser(description="NetInsight service health check")
    p.add_argument("-n", "--name", required=True)
    args = p.parse_args()
    run_service_health(args.name)


if __name__ == "__main__":
    main()
