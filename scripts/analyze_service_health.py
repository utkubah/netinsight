# scripts/analyze_service_health.py
"""
NetInsight - Service Health Analysis

Reads:
  data/netinsight_service_health.csv

Writes:
  data/service_health_summary.csv
  data/service_health_by_domain.csv
  data/service_health_recent.csv

Run:
  python3 scripts/analyze_service_health.py

What it does:
- Parses the service health log produced by src/mode_service_health.py
- Produces:
  (1) Overall summary (counts/percentages by service_state)
  (2) Per-domain summary (how often each state happened per domain)
  (3) Recent results table (last N rows)
"""

from pathlib import Path
import pandas as pd

IN_PATH = Path("data") / "netinsight_service_health.csv"
OUT_SUMMARY = Path("data") / "service_health_summary.csv"
OUT_BY_DOMAIN = Path("data") / "service_health_by_domain.csv"
OUT_RECENT = Path("data") / "service_health_recent.csv"

TIMEZONE = "Europe/Istanbul"
RECENT_N = 50


def parse_timestamp(ts: pd.Series) -> pd.Series:
    """
    Parse timestamps and normalize to TIMEZONE.
    - If tz-aware: convert to TIMEZONE
    - If tz-naive: assume UTC then convert to TIMEZONE
    """
    dt = pd.to_datetime(ts, errors="coerce", utc=False)

    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        return dt.dt.tz_convert(TIMEZONE)

    dt = dt.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return dt.dt.tz_convert(TIMEZONE)


def coerce_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    s2 = s.astype(str).str.strip().str.lower()
    mapping = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}
    out = s2.map(mapping)
    out = out.fillna(False)
    return out.astype(bool)


def require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {IN_PATH}: {missing}. Found: {list(df.columns)}")


def main() -> None:
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input not found: {IN_PATH}. Run src/mode_service_health.py first.")

    df = pd.read_csv(IN_PATH)

    required = [
        "timestamp", "mode", "service_name", "hostname", "url",
        "ping_ok", "dns_ok", "http_ok",
        "ping_error_kind", "dns_error_kind", "http_error_kind",
        "http_status_code", "service_state", "service_reason",
    ]
    require_columns(df, required)

    # Parse time
    df["timestamp"] = parse_timestamp(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).copy()

    # Normalize booleans
    df["ping_ok"] = coerce_bool(df["ping_ok"])
    df["dns_ok"] = coerce_bool(df["dns_ok"])
    df["http_ok"] = coerce_bool(df["http_ok"])

    # status code numeric
    df["http_status_code"] = pd.to_numeric(df["http_status_code"], errors="coerce")

    # Some convenience columns
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour

    # Sort
    df = df.sort_values("timestamp").reset_index(drop=True)

    # --- (1) Overall summary -----------------------------------------
    total = len(df)
    state_counts = df["service_state"].astype(str).value_counts(dropna=False).reset_index()
    state_counts.columns = ["service_state", "count"]
    state_counts["pct"] = (100.0 * state_counts["count"] / max(total, 1)).round(2)

    # Quick signal metrics (overall)
    # "blocked-ish" bucket (from Utku's classifier)
    blockedish_states = {
        "possible_blocked_or_restricted",
        "connection_issue_or_blocked",
        "connectivity_issue_or_firewall",
    }
    df["is_blockedish"] = df["service_state"].astype(str).isin(blockedish_states)

    overall = pd.DataFrame(
        {
            "metric": [
                "rows_total",
                "domains_unique",
                "healthy_pct",
                "blockedish_pct",
                "dns_ok_pct",
                "http_ok_pct",
                "ping_ok_pct",
            ],
            "value": [
                total,
                df["service_name"].nunique(),
                round(100.0 * (df["service_state"].astype(str) == "healthy").mean(), 2),
                round(100.0 * df["is_blockedish"].mean(), 2),
                round(100.0 * df["dns_ok"].mean(), 2),
                round(100.0 * df["http_ok"].mean(), 2),
                round(100.0 * df["ping_ok"].mean(), 2),
            ],
        }
    )

    summary = overall.merge(
        state_counts.assign(metric=lambda x: "state_" + x["service_state"].astype(str) + "_pct")[["metric", "pct"]],
        on="metric",
        how="left",
    )
    # keep both overall metrics and state pct table separately (cleaner)
    overall.to_csv(OUT_SUMMARY, index=False)

    # Also write a separate distribution file next to it (more readable)
    dist_path = Path("data") / "service_health_state_distribution.csv"
    state_counts.to_csv(dist_path, index=False)

    # --- (2) Per-domain summary --------------------------------------
    # Per domain: how many runs + share of each state
    per_domain = (
        df.groupby(["service_name", "service_state"])
        .size()
        .reset_index(name="count")
    )

    # Pivot states into columns
    per_domain_pivot = per_domain.pivot_table(
        index="service_name",
        columns="service_state",
        values="count",
        fill_value=0,
        aggfunc="sum",
    ).reset_index()

    # total + key rates
    per_domain_pivot["runs_total"] = per_domain_pivot.drop(columns=["service_name"]).sum(axis=1)

    # Helper to safely compute %
    def pct_col(state: str) -> pd.Series:
        if state not in per_domain_pivot.columns:
            return 0.0
        return (100.0 * per_domain_pivot[state] / per_domain_pivot["runs_total"].clip(lower=1)).round(2)

    per_domain_pivot["healthy_pct"] = pct_col("healthy")
    per_domain_pivot["blockedish_pct"] = (
        pct_col("possible_blocked_or_restricted")
        + pct_col("connection_issue_or_blocked")
        + pct_col("connectivity_issue_or_firewall")
    ).round(2)

    # Order: most problematic first (blockedish high), then low healthy
    per_domain_pivot = per_domain_pivot.sort_values(
        ["blockedish_pct", "healthy_pct", "runs_total"],
        ascending=[False, True, False],
    ).reset_index(drop=True)

    per_domain_pivot.to_csv(OUT_BY_DOMAIN, index=False)

    # --- (3) Recent table --------------------------------------------
    recent = df.tail(RECENT_N).copy()
    keep_cols = [
        "timestamp", "service_name", "service_state", "http_status_code",
        "ping_ok", "dns_ok", "http_ok",
        "ping_error_kind", "dns_error_kind", "http_error_kind",
        "service_reason",
    ]
    keep_cols = [c for c in keep_cols if c in recent.columns]
    recent[keep_cols].to_csv(OUT_RECENT, index=False)

    # Console output (short)
    print(f"Saved: {OUT_SUMMARY}")
    print(f"Saved: {dist_path}")
    print(f"Saved: {OUT_BY_DOMAIN}")
    print(f"Saved: {OUT_RECENT}")

    if total > 0:
        last = df.iloc[-1]
        print(
            f"Last: {last['timestamp']} domain={last['service_name']} "
            f"state={last['service_state']} code={last['http_status_code']}"
        )


if __name__ == "__main__":
    main()
