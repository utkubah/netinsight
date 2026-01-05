# src/main.py
"""
Baseline logger using the improved CSV schema (csv_log).

Enhancements:
- --once : run single round
- --interval : change interval
- --output / -o : csv path
- --gateway : override gateway IP for gateway-tagged services
- --services-file : provide a JSON file containing a SERVICES list
- --rotate : rotate existing CSV to avoid schema mismatch
- --debug : enable debug logging
"""
import argparse
import json
import logging
import os
import time
from datetime import datetime

from .csv_log import make_row, append_rows, utc_now_iso
from .logging_setup import setup_logging
from . import targets_config
from . import ping_check
from . import dns_check
from . import http_check
from . import net_utils

from .error_kinds import (
    CONFIG_MISSING_HOSTNAME,
    CONFIG_MISSING_URL,
)

LOG = logging.getLogger("netinsight.main")

INTERVAL_SECONDS = 30
LOG_PATH = "data/netinsight_log.csv"


def _resolve_gateway_if_needed(hostname, tags, gateway_override=None):
    if hostname:
        return hostname
    if "gateway" in (tags or []):
        if gateway_override:
            return gateway_override
        return net_utils.get_default_gateway_ip()
    return hostname


def run_once(round_id=None, services=None, log_path=None, gateway_override=None):
    if services is None:
        services = targets_config.SERVICES
    if log_path is None:
        log_path = LOG_PATH
    if round_id is None:
        round_id = utc_now_iso()

    rows = []
    ping_count = dns_count = http_count = 0

    for svc in services:
        name = svc.get("name", "")
        tags = svc.get("tags", [])
        hostname = _resolve_gateway_if_needed(svc.get("hostname"), tags, gateway_override=gateway_override)
        url = svc.get("url", "")

        # PING
        ping_cfg = svc.get("ping", {})
        if ping_cfg.get("enabled"):
            if not hostname:
                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname="",
                        url=url,
                        tags=",".join(tags),
                        probe_type="ping",
                        success=False,
                        error_kind=CONFIG_MISSING_HOSTNAME,
                        error_message="hostname missing for ping",
                        details=json.dumps({"reason": "missing hostname"}, separators=(",", ":"), sort_keys=True),
                    )
                )
            else:
                r = ping_check.run_ping(hostname, count=ping_cfg.get("count", 3), timeout=ping_cfg.get("timeout", 1.0))

                success = (r.get("received", 0) > 0)
                details = {
                    "sent": r.get("sent"),
                    "received": r.get("received"),
                    "latencies_ms": r.get("latencies_ms") or [],
                    "partial_success": bool(success and (r.get("packet_loss_pct") or 0) > 0),
                }

                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname=hostname,
                        url=url,
                        tags=",".join(tags),
                        probe_type="ping",
                        success=success,
                        latency_ms=r.get("latency_avg_ms"),
                        latency_p95_ms=r.get("latency_p95_ms"),
                        jitter_ms=r.get("jitter_ms"),
                        packet_loss_pct=r.get("packet_loss_pct"),
                        error_kind=r.get("error_kind"),
                        error_message=r.get("error"),
                        details=json.dumps(details, separators=(",", ":"), sort_keys=True),
                    )
                )
            ping_count += 1

        # DNS
        dns_cfg = svc.get("dns", {})
        if dns_cfg.get("enabled"):
            if not hostname:
                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname="",
                        url=url,
                        tags=",".join(tags),
                        probe_type="dns",
                        success=False,
                        error_kind=CONFIG_MISSING_HOSTNAME,
                        error_message="hostname missing for dns",
                        details=json.dumps({"reason": "missing hostname"}, separators=(",", ":"), sort_keys=True),
                    )
                )
            else:
                r = dns_check.run_dns(hostname, timeout=dns_cfg.get("timeout", 2.0))
                details = {"ip": r.get("ip")}
                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname=hostname,
                        url=url,
                        tags=",".join(tags),
                        probe_type="dns",
                        success=bool(r.get("ok")),
                        latency_ms=r.get("dns_ms"),
                        error_kind=r.get("error_kind"),
                        error_message=r.get("error"),
                        details=json.dumps(details, separators=(",", ":"), sort_keys=True),
                    )
                )
            dns_count += 1

        # HTTP
        http_cfg = svc.get("http", {})
        if http_cfg.get("enabled"):
            if not url:
                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname=hostname or "",
                        url="",
                        tags=",".join(tags),
                        probe_type="http",
                        success=False,
                        error_kind=CONFIG_MISSING_URL,
                        error_message="url missing",
                        details=json.dumps({"reason": "missing url"}, separators=(",", ":"), sort_keys=True),
                    )
                )
            else:
                r = http_check.run_http(url, timeout=http_cfg.get("timeout", 3.0))
                details = {"status_class": r.get("status_class"), "bytes": r.get("bytes"), "redirects": r.get("redirects")}
                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname=hostname or "",
                        url=url,
                        tags=",".join(tags),
                        probe_type="http",
                        success=bool(r.get("ok")),
                        latency_ms=r.get("http_ms"),
                        status_code=r.get("status_code"),
                        error_kind=r.get("error_kind"),
                        error_message=r.get("error"),
                        details=json.dumps(details, separators=(",", ":"), sort_keys=True),
                    )
                )
            http_count += 1

    append_rows(log_path, rows)

    failures = sum(1 for r in rows if r.get("success") == "False")
    if failures:
        LOG.warning("round=%s failures=%d rows=%d (ping=%d dns=%d http=%d)", round_id, failures, len(rows), ping_count, dns_count, http_count)
    else:
        LOG.info("round=%s ok rows=%d (ping=%d dns=%d http=%d)", round_id, len(rows), ping_count, dns_count, http_count)

    return {"round_id": round_id, "total_rows": len(rows), "failures": failures}


def _parse_args():
    p = argparse.ArgumentParser(description="NetInsight baseline monitor")
    p.add_argument("--once", action="store_true", help="Run a single round and exit")
    p.add_argument("--interval", type=float, default=INTERVAL_SECONDS, help="Interval between rounds (seconds)")
    p.add_argument("--output", "-o", default=LOG_PATH, help="CSV log path")
    p.add_argument("--gateway", default=None, help="Override gateway IP for 'gateway' probes (if not provided, auto-detect).")
    p.add_argument("--services-file", default=None, help="Optional JSON file containing a SERVICES array")
    p.add_argument("--rotate", action="store_true", help="Rotate existing log file with timestamp before starting")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p.parse_args()


def _load_services_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("services-file must be a JSON array of service dicts")
    return data


def _rotate_if_requested(path):
    if os.path.exists(path):
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        new_name = f"{path}.{ts}.bak"
        os.replace(path, new_name)
        LOG.info("Rotated existing log %s -> %s", path, new_name)
        print(f"Rotated existing log {path} -> {new_name}")


def main():
    setup_logging()
    args = _parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        LOG.debug("Debug logging enabled")

    if args.rotate and os.path.exists(args.output):
        _rotate_if_requested(args.output)

    services = None
    if args.services_file:
        services = _load_services_from_file(args.services_file)
        LOG.info("Loaded %d services from %s", len(services), args.services_file)

    LOG.info("NetInsight baseline starting interval=%s output=%s gateway_override=%s", args.interval, args.output, args.gateway)

    if args.once:
        summary = run_once(log_path=args.output, gateway_override=args.gateway, services=services)
        print(f"Completed run {summary['round_id']}: rows={summary['total_rows']} failures={summary['failures']} output={args.output}")
        return

    try:
        while True:
            try:
                run_once(log_path=args.output, gateway_override=args.gateway, services=services)
            except Exception:
                LOG.exception("Unhandled exception during run_once; continuing")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        LOG.info("NetInsight baseline stopped by user (KeyboardInterrupt).")
        print("NetInsight baseline stopped by user.")


if __name__ == "__main__":
    main()
