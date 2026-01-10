"""
Baseline logger and simple CLI. This version persists gateway into config/targets.json.
"""
import argparse
import json
import logging
import tempfile
import os
import re
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
    CONFIG_MISSING_GATEWAY,
)

LOG = logging.getLogger("netinsight.main")

INTERVAL_SECONDS = 30
LOG_PATH = "data/netinsight_log.csv"
DEFAULT_TARGETS_JSON = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config", "targets.json"))


def persist_gateway(gateway_ip, targets_file_path=None, targets_module=None, overwrite=False, write_file=False):
    """
    Persist gateway_ip into targets.json with safety rules:

    - If file has an existing non-empty GATEWAY_HOSTNAME and overwrite=False:
        do NOT change the file (and optionally sync in-memory module to the existing value).
    - Do NOT overwrite per-service hostnames; only fill empty hostname for services tagged "gateway".
    - Do NOT add/normalize unrelated keys (e.g., do not inject SERVICES if missing).
    - Only rewrite the file if the underlying dict actually changes (semantic compare),
      so formatting differences won't trigger rewrites.
    - If write_file=False, never touch the file (only update in-memory module if provided).

    Returns True on success, False on failure.
    """
    import copy
    import json
    import logging
    import os
    import tempfile

    LOG = logging.getLogger("netinsight.persist_gateway")

    if targets_file_path is None:
        targets_file_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "config", "targets.json")
        )

    try:
        # Load existing config
        data = {}
        if os.path.exists(targets_file_path):
            try:
                with open(targets_file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception:
                data = {}

        original = copy.deepcopy(data)

        existing_gw = data.get("GATEWAY_HOSTNAME")

        # If there's an existing non-empty gateway and we're not allowed to overwrite it, do not modify the file at all.
        if existing_gw and not overwrite and (gateway_ip is not None) and existing_gw != gateway_ip:
            LOG.info(
                "Not overwriting existing GATEWAY_HOSTNAME=%s in %s",
                existing_gw,
                targets_file_path,
            )
            # Optionally sync in-memory module to existing gateway
            if targets_module is not None:
                try:
                    targets_module.GATEWAY_HOSTNAME = existing_gw
                    for svc in getattr(targets_module, "SERVICES", []):
                        tags = svc.get("tags", []) or []
                        if "gateway" in tags and not svc.get("hostname"):
                            svc["hostname"] = existing_gw or ""
                except Exception:
                    LOG.exception("Failed to update targets_module from existing gateway")
            return True

        desired_gw = gateway_ip if gateway_ip else None

        if data.get("GATEWAY_HOSTNAME") != desired_gw:
            data["GATEWAY_HOSTNAME"] = desired_gw

        services = data.get("SERVICES")
        if isinstance(services, list):
            for svc in services:
                if not isinstance(svc, dict):
                    continue
                tags = svc.get("tags", []) or []
                if "gateway" in tags:
                    # Only fill if empty; never override explicit hostname
                    if not svc.get("hostname"):
                        svc["hostname"] = desired_gw or ""

        # If nothing changed semantically, do not write (avoids “format overwrite”)
        if data == original:
            LOG.debug("persist_gateway: no semantic changes; not rewriting %s", targets_file_path)
            # Still sync in-memory module
            if targets_module is not None:
                try:
                    targets_module.GATEWAY_HOSTNAME = data.get("GATEWAY_HOSTNAME")
                    for svc in getattr(targets_module, "SERVICES", []):
                        tags = svc.get("tags", []) or []
                        if "gateway" in tags and not svc.get("hostname"):
                            svc["hostname"] = data.get("GATEWAY_HOSTNAME") or ""
                except Exception:
                    LOG.exception("Failed to update targets_module on no-op persist")
            return True

        # If writing is disabled, stop here
        if not write_file:
            LOG.info("persist_gateway: write_file=False; not writing %s", targets_file_path)
            if targets_module is not None:
                try:
                    targets_module.GATEWAY_HOSTNAME = data.get("GATEWAY_HOSTNAME")
                    for svc in getattr(targets_module, "SERVICES", []):
                        tags = svc.get("tags", []) or []
                        if "gateway" in tags and not svc.get("hostname"):
                            svc["hostname"] = data.get("GATEWAY_HOSTNAME") or ""
                except Exception:
                    LOG.exception("Failed to update targets_module when write_file=False")
            return True

        target_dir = os.path.dirname(targets_file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        fd, tmpname = tempfile.mkstemp(prefix="targets.", suffix=".tmp", dir=target_dir or ".")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tf:
                json.dump(data, tf, indent=2)
                tf.write("\n")
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(tmpname, targets_file_path)
        finally:
            try:
                if os.path.exists(tmpname):
                    os.remove(tmpname)
            except Exception:
                pass

        LOG.info("Persisted gateway=%s into %s", desired_gw, targets_file_path)

        # Update in-memory module
        if targets_module is not None:
            try:
                targets_module.GATEWAY_HOSTNAME = data.get("GATEWAY_HOSTNAME")
                for svc in getattr(targets_module, "SERVICES", []):
                    tags = svc.get("tags", []) or []
                    if "gateway" in tags and not svc.get("hostname"):
                        svc["hostname"] = data.get("GATEWAY_HOSTNAME") or ""
            except Exception:
                LOG.exception("Failed to update targets_module after writing file")

        return True

    except Exception:
        LOG.exception("Failed to persist gateway to %s", targets_file_path)
        return False



def _resolve_hostname(svc_hostname, tags, gateway_override=None):
    tags = tags or []
    hostname = svc_hostname or ""

    if hostname:
        return hostname, None

    if "gateway" in tags:
        if gateway_override:
            return gateway_override, None
        try:
            gw = net_utils.get_default_gateway_ip()
        except Exception:
            gw = None
        if gw:
            return gw, None
        return "", CONFIG_MISSING_GATEWAY

    return "", CONFIG_MISSING_HOSTNAME


def _load_services_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("services-file must be a JSON array of service dicts")
    return data


def _default_services():
    # Prefer the JSON config under config/targets.json if present
    if os.path.exists(DEFAULT_TARGETS_JSON):
        try:
            with open(DEFAULT_TARGETS_JSON, "r", encoding="utf-8") as f:
                j = json.load(f)
            svcs = j.get("SERVICES")
            if isinstance(svcs, list):
                return svcs
        except Exception:
            pass
    # fall back to targets_config module values
    return getattr(targets_config, "SERVICES", [])


def run_once(round_id=None, services=None, log_path=None, gateway_override=None):
    if services is None:
        services = _default_services()
    if log_path is None:
        log_path = LOG_PATH
    if round_id is None:
        round_id = utc_now_iso()

    rows = []
    ping_count = dns_count = http_count = 0

    for svc in services:
        name = svc.get("name", "")
        tags = svc.get("tags", []) or []
        url = svc.get("url", "") or ""

        hostname, missing_kind = _resolve_hostname(svc.get("hostname"), tags, gateway_override=gateway_override)

        # PING
        ping_cfg = svc.get("ping", {}) or {}
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
                        error_kind=missing_kind or CONFIG_MISSING_HOSTNAME,
                        error_message="hostname missing for ping",
                        details=json.dumps({"reason": "missing hostname"}, separators=(",", ":")),
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
                        details=json.dumps(details, separators=(",", ":")),
                    )
                )
            ping_count += 1

        # DNS
        dns_cfg = svc.get("dns", {}) or {}
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
                        error_kind=missing_kind or CONFIG_MISSING_HOSTNAME,
                        error_message="hostname missing for dns",
                        details=json.dumps({"reason": "missing hostname"}, separators=(",", ":")),
                    )
                )
            else:
                r = dns_check.run_dns(hostname, timeout=dns_cfg.get("timeout", 2.0))
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
                        details=json.dumps({"ip": r.get("ip")}, separators=(",", ":")),
                    )
                )
            dns_count += 1

        # HTTP
        http_cfg = svc.get("http", {}) or {}
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
                        details=json.dumps({"reason": "missing url"}, separators=(",", ":")),
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
                        details=json.dumps(details, separators=(",", ":")),
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
    p.add_argument("--rotate", action="store_true", help="Rotate existing CSV with timestamp before starting")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p.parse_args()


def _rotate_if_requested(path):
    if os.path.exists(path):
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        new_name = "%s.%s.bak" % (path, ts)
        os.replace(path, new_name)
        LOG.info("Rotated existing log %s -> %s", path, new_name)
        print("Rotated existing log %s -> %s" % (path, new_name))


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
        try:
            services = _load_services_from_file(args.services_file)
            LOG.info("Loaded %d services from %s", len(services), args.services_file)
        except Exception:
            LOG.exception("Failed to load services-file")

    # decide on gateway and persist it to the JSON config and update in-memory targets_config
    gw_used = args.gateway if args.gateway else net_utils.get_default_gateway_ip()

    if gw_used:
        persist_gateway(gw_used, targets_file_path=DEFAULT_TARGETS_JSON, targets_module=targets_config)
    else:
        LOG.debug("No gateway detected/overridden during startup; will emit config_missing_gateway rows for gateway probes.")

    LOG.info("NetInsight baseline starting interval=%s output=%s gateway=%s", args.interval, args.output, gw_used)

    if args.once:
        summary = run_once(log_path=args.output, gateway_override=args.gateway, services=services)
        print("Completed run %s rows=%s failures=%s output=%s" % (summary["round_id"], summary["total_rows"], summary["failures"], args.output))
        return

    print("NetInsight running. Press Ctrl+C to stop. Output:", args.output)
    try:
        while True:
            try:
                run_once(log_path=args.output, gateway_override=args.gateway, services=services)
            except Exception:
                LOG.exception("Unhandled exception during run_once; continuing")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("NetInsight stopped.")
        LOG.info("NetInsight stopped by user (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
