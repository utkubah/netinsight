# src/main.py
"""
Baseline logger using the improved CSV schema (csv_log).
"""

import logging
import time

from .csv_log import make_row, append_rows, utc_now_iso, CSV_HEADERS
from .logging_setup import setup_logging
from . import targets_config
from . import ping_check
from . import dns_check
from . import http_check
from . import net_utils

LOG = logging.getLogger("netinsight.main")

INTERVAL_SECONDS = 30
LOG_PATH = "data/netinsight_log.csv"


def _tags_to_str(tags):
    return ",".join(tags or [])


def _resolve_gateway_if_needed(hostname, tags):
    if hostname:
        return hostname
    if "gateway" in (tags or []):
        return net_utils.get_default_gateway_ip()
    return hostname


def run_once(round_id=None, services=None, log_path=None):
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
        hostname = _resolve_gateway_if_needed(svc.get("hostname"), tags)
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
                        error_kind="config_missing_hostname",
                        error_message="hostname missing for ping",
                        details='{"reason":"missing hostname"}',
                    )
                )
            else:
                r = ping_check.run_ping(hostname, count=ping_cfg.get("count", 3), timeout=ping_cfg.get("timeout", 1.0))
                details = {"latencies_ms": r.get("latencies_ms") or []}
                rows.append(
                    make_row(
                        mode="baseline",
                        round_id=round_id,
                        service_name=name,
                        hostname=hostname,
                        url=url,
                        tags=",".join(tags),
                        probe_type="ping",
                        success=(r.get("received", 0) > 0),
                        latency_ms=r.get("latency_avg_ms"),
                        latency_p95_ms=r.get("latency_p95_ms"),
                        jitter_ms=r.get("jitter_ms"),
                        packet_loss_pct=r.get("packet_loss_pct"),
                        error_kind=r.get("error_kind"),
                        error_message=r.get("error"),
                        details=str(details),
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
                        error_kind="config_missing_hostname",
                        error_message="hostname missing for dns",
                        details='{"reason":"missing hostname"}',
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
                        details=str(details),
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
                        error_kind="config_missing_url",
                        error_message="url missing",
                        details='{"reason":"missing url"}',
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
                        details=str(details),
                    )
                )
            http_count += 1

    append_rows(log_path, rows)
    LOG.info("round=%s wrote ping=%d dns=%d http=%d rows=%d", round_id, ping_count, dns_count, http_count, len(rows))
    return {"round_id": round_id, "total_rows": len(rows)}


def main():
    setup_logging()
    LOG.info("NetInsight baseline starting, interval=%s", INTERVAL_SECONDS)
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
