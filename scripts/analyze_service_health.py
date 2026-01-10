#!/usr/bin/env python3
"""
NetInsight - Service Health Analysis (schema-flex)

Supports BOTH schemas:
1) Old schema (your early version):
   columns like ping_ok,dns_ok,http_ok,service_state,service_reason,...

2) New unified schema (current main):
   columns like timestamp,mode,round_id,service_name,...,status_code,error_kind,details(JSON)
   where details includes nested ping/dns/http + "state".

Reads:
  data/netinsight_service_health.csv
  (optional) data/netinsight_service_health_old.csv  (auto-included if present)

Writes:
  data/service_health_summary.csv
  data/service_health_state_distribution.csv
  data/service_health_by_domain.csv
  data/service_health_recent.csv

Run:
  python3 scripts/analyze_service_health.py
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

IN_PATH = Path("data") / "netinsight_service_health.csv"
OLD_PATH = Path("data") / "netinsight_service_health_old.csv"

OUT_SUMMARY = Path("data") / "service_health_summary.csv"
OUT_DIST = Path("data") / "service_health_state_distribution.csv"
OUT_BY_DOMAIN = Path("data") / "service_health_by_domain.csv"
OUT_RECENT = Path("data") / "service_health_recent.csv"

TIMEZONE = "Europe/Rome"  # project timezone (you can change if needed)


BLOCKEDISH_STATES = {
    "possible_blocked_or_restricted",
    "connection_issue_or_blocked",
    "connectivity_issue_or_firewall",
    "dns_failure",
}


def ensure_tz(ts: pd.Series) -> pd.Series:
    d = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(d.dt, "tz") and d.dt.tz is not None:
        return d.dt.tz_convert(TIMEZONE)
    d = d.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return d.dt.tz_convert(TIMEZONE)


def _safe_json_loads(x: str) -> dict:
    if x is None:
        return {}
    s = str(x).strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _normalize_old_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["timestamp"] = ensure_tz(df["timestamp"])
    out["service_name"] = df.get("service_name", "")
    out["service_state"] = df.get("service_state", "inconclusive").astype(str)
    out["http_status_code"] = pd.to_numeric(df.get("http_status_code"), errors="coerce")

    def _to_bool(v):
        if pd.isna(v):
            return False
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "y")

    out["ping_ok"] = df.get("ping_ok", False).map(_to_bool)
    out["dns_ok"] = df.get("dns_ok", False).map(_to_bool)
    out["http_ok"] = df.get("http_ok", False).map(_to_bool)

    out["ping_error_kind"] = df.get("ping_error_kind")
    out["dns_error_kind"] = df.get("dns_error_kind")
    out["http_error_kind"] = df.get("http_error_kind")
    out["service_reason"] = df.get("service_reason", "")

    return out.dropna(subset=["timestamp"]).copy()


def _normalize_new_schema(df: pd.DataFrame) -> pd.DataFrame:
    out_rows = []
    for r in df.itertuples(index=False):
        row = r._asdict()

        details = _safe_json_loads(row.get("details"))
        ping = details.get("ping") if isinstance(details.get("ping"), dict) else {}
        dns = details.get("dns") if isinstance(details.get("dns"), dict) else {}
        http = details.get("http") if isinstance(details.get("http"), dict) else {}

        state = details.get("state")
        if not state:
            ek = row.get("error_kind")
            if isinstance(ek, str) and ek:
                state = ek
            else:
                state = "inconclusive"

        # Derive ok flags from nested results
        ping_ok = False
        if ping:
            if "received" in ping:
                ping_ok = (ping.get("received", 0) or 0) > 0
            else:
                ping_ok = (ping.get("error_kind") == "ok")

        dns_ok = False
        if dns:
            if "ok" in dns:
                dns_ok = bool(dns.get("ok"))
            else:
                dns_ok = (dns.get("error_kind") == "ok")

        http_ok = False
        if http:
            if "ok" in http:
                http_ok = bool(http.get("ok"))
            else:
                http_ok = (http.get("error_kind") == "ok")

        status_code = row.get("status_code")
        if status_code is None or (isinstance(status_code, float) and pd.isna(status_code)):
            status_code = http.get("status_code")

        service_reason = details.get("reason", "")
        if not service_reason:
            service_reason = ""

        out_rows.append(
            {
                "timestamp": row.get("timestamp"),
                "service_name": row.get("service_name", ""),
                "service_state": str(state),
                "http_status_code": status_code,
                "ping_ok": bool(ping_ok),
                "dns_ok": bool(dns_ok),
                "http_ok": bool(http_ok),
                "ping_error_kind": ping.get("error_kind") if ping else None,
                "dns_error_kind": dns.get("error_kind") if dns else None,
                "http_error_kind": http.get("error_kind") if http else None,
                "service_reason": service_reason,
            }
        )

    out = pd.DataFrame(out_rows)
    out["timestamp"] = ensure_tz(out["timestamp"])
    out["http_status_code"] = pd.to_numeric(out["http_status_code"], errors="coerce")
    return out.dropna(subset=["timestamp"]).copy()


def load_and_normalize(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "ping_ok" in df.columns and "service_state" in df.columns:
        return _normalize_old_schema(df)

    if "details" in df.columns and "service_name" in df.columns:
        return _normalize_new_schema(df)

    raise ValueError(
        f"Unrecognized schema in {path}. Columns: {list(df.columns)}"
    )


def main() -> None:
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input not found: {IN_PATH}")

    parts = [load_and_normalize(IN_PATH)]
    if OLD_PATH.exists():
        try:
            parts.append(load_and_normalize(OLD_PATH))
        except Exception:
            # If old file exists but is weird, ignore it (we don't want to block current runs)
            pass

    df = pd.concat(parts, ignore_index=True).dropna(subset=["timestamp"]).copy()
    if df.empty:
        print("No rows to analyze.")
        return

    df = df.sort_values(["timestamp", "service_name"]).reset_index(drop=True)

    df["is_healthy"] = df["service_state"].astype(str).eq("healthy")
    df["is_blockedish"] = df["service_state"].astype(str).isin(BLOCKEDISH_STATES)

    # --- Summary ---
    summary = pd.DataFrame(
        [
            {"metric": "rows_total", "value": float(len(df))},
            {"metric": "domains_unique", "value": float(df["service_name"].nunique())},
            {"metric": "healthy_pct", "value": round(100.0 * df["is_healthy"].mean(), 2)},
            {"metric": "blockedish_pct", "value": round(100.0 * df["is_blockedish"].mean(), 2)},
        ]
    )
    summary.to_csv(OUT_SUMMARY, index=False)

    dist = (
        df.groupby("service_state")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    dist["pct"] = (100.0 * dist["count"] / dist["count"].sum()).round(2)
    dist.to_csv(OUT_DIST, index=False)

    by_domain = (
        df.groupby("service_name")
        .agg(
            runs=("service_state", "size"),
            healthy_pct=("is_healthy", lambda s: round(100.0 * s.mean(), 2)),
            blockedish_pct=("is_blockedish", lambda s: round(100.0 * s.mean(), 2)),
            last_timestamp=("timestamp", "max"),
        )
        .reset_index()
    )

    last_rows = (
        df.sort_values(["service_name", "timestamp"])
        .groupby("service_name")
        .tail(1)[["service_name", "service_state", "http_status_code"]]
        .rename(columns={"service_state": "last_state", "http_status_code": "last_http_status_code"})
    )

    by_domain = by_domain.merge(last_rows, on="service_name", how="left")
    by_domain = by_domain.sort_values(["blockedish_pct", "runs"], ascending=[False, False]).reset_index(drop=True)
    by_domain.to_csv(OUT_BY_DOMAIN, index=False)

    # --- Recent ---
    recent_cols = [
        "timestamp",
        "service_name",
        "service_state",
        "http_status_code",
        "ping_ok",
        "dns_ok",
        "http_ok",
        "ping_error_kind",
        "dns_error_kind",
        "http_error_kind",
        "service_reason",
    ]
    recent = df[recent_cols].sort_values("timestamp", ascending=False).head(50)
    recent.to_csv(OUT_RECENT, index=False)

    # Console
    last = df.sort_values("timestamp").tail(1).iloc[0]
    print(f"Saved: {OUT_SUMMARY}")
    print(f"Saved: {OUT_DIST}")
    print(f"Saved: {OUT_BY_DOMAIN}")
    print(f"Saved: {OUT_RECENT}")
    print(
        f"Last: {last['timestamp']} domain={last['service_name']} "
        f"state={last['service_state']} code={last['http_status_code']}"
    )


if __name__ == "__main__":
    main()
