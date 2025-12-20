"""
NetInsight - Quality Score

Reads:
  data/netinsight_log.csv

Writes:
  data/quality_rows.csv         (row-level, with score + tier + score_z)
  data/quality_hourly.csv       (hourly aggregates across all services/probes)
  data/quality_by_service.csv   (service ranking by avg score)

Run:
  python3 scripts/quality_score.py
"""

import math
from pathlib import Path
import pandas as pd

LOG_PATH = Path("data") / "netinsight_log.csv"
OUT_ROWS_PATH = Path("data") / "quality_rows.csv"
OUT_HOURLY_PATH = Path("data") / "quality_hourly.csv"
OUT_SERVICE_PATH = Path("data") / "quality_by_service.csv"

# Local analysis timezone (for grouping, readability)
TIMEZONE = "Europe/Istanbul"


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def parse_timestamp(ts: pd.Series) -> pd.Series:
    """
    Parse timestamps and normalize to TIMEZONE.

    - If tz-aware: convert to TIMEZONE.
    - If tz-naive: assume UTC (collector writes UTC), then convert to TIMEZONE.
    """
    dt = pd.to_datetime(ts, errors="coerce", utc=False)

    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        return dt.dt.tz_convert(TIMEZONE)

    # tz-naive: treat as UTC then convert
    dt = dt.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return dt.dt.tz_convert(TIMEZONE)


def coerce_success(s: pd.Series) -> pd.Series:
    """
    Normalize success column into 0/1 ints.
    Handles: True/False, 1/0, "true"/"false", etc.
    """
    if s.dtype == bool:
        return s.astype(int)

    s2 = s.astype(str).str.strip().str.lower()
    mapping = {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0}
    out = s2.map(mapping)

    out = out.fillna(pd.to_numeric(s, errors="coerce"))
    out = out.fillna(0).astype(int).clip(0, 1)
    return out


def score_ping_row(row: pd.Series, has_loss_col: bool) -> float:
    """0..100 for a ping row. Uses latency_ms, jitter_ms, (optional) packet_loss_pct, success."""
    if int(row.get("success", 1)) == 0:
        return 0.0

    lat = row.get("latency_ms")
    jit = row.get("jitter_ms")

    lat = float(lat) if pd.notna(lat) else 9999.0
    jit = float(jit) if pd.notna(jit) else 9999.0

    lat_score = 100.0 * math.exp(-lat / 200.0)
    jit_score = 100.0 * math.exp(-jit / 20.0)

    if has_loss_col:
        loss = row.get("packet_loss_pct")
        loss = float(loss) if pd.notna(loss) else 0.0
        loss_score = 100.0 * math.exp(-loss / 2.0)
        return clamp(0.55 * lat_score + 0.30 * jit_score + 0.15 * loss_score)

    # if packet_loss_pct not present, renormalize weights
    return clamp(0.65 * lat_score + 0.35 * jit_score)


def score_dns_row(row: pd.Series) -> float:
    """0..100 for a DNS row. Uses dns_ms (or latency_ms), success."""
    if int(row.get("success", 1)) == 0:
        return 0.0

    dns_ms = row.get("dns_ms", row.get("latency_ms"))
    dns_ms = float(dns_ms) if pd.notna(dns_ms) else 9999.0

    s = 100.0 * math.exp(-dns_ms / 50.0)
    return clamp(s)


def score_http_row(row: pd.Series) -> float:
    """0..100 for an HTTP row. Uses http_ms (or latency_ms), status_code if present, success."""
    if int(row.get("success", 1)) == 0:
        return 0.0

    http_ms = row.get("http_ms", row.get("latency_ms"))
    http_ms = float(http_ms) if pd.notna(http_ms) else 9999.0

    timing = 100.0 * math.exp(-http_ms / 300.0)

    status = row.get("status_code")
    if pd.notna(status):
        try:
            code = int(status)
            if 500 <= code < 600:
                timing *= 0.40
            elif 400 <= code < 500:
                timing *= 0.70
        except Exception:
            pass

    return clamp(timing)


def tier_from_score(score: float) -> str:
    if score >= 80:
        return "good"
    if score >= 50:
        return "ok"
    return "bad"


def require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Columns present: {list(df.columns)}")


def main() -> None:
    if not LOG_PATH.exists():
        raise FileNotFoundError(f"Log file not found: {LOG_PATH}")

    df = pd.read_csv(LOG_PATH)
    require_columns(df, ["timestamp", "probe_type", "service_name", "success"])

    # Parse + normalize time
    df["timestamp"] = parse_timestamp(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).copy()

    # Normalize success to 0/1 ints
    df["success"] = coerce_success(df["success"])

    # Convenience column
    df["hour"] = df["timestamp"].dt.hour

    # Compute per-row scores
    probe = df["probe_type"].astype(str)
    has_loss_col = "packet_loss_pct" in df.columns

    df["score"] = 0.0
    if (probe == "ping").any():
        df.loc[probe == "ping", "score"] = df.loc[probe == "ping"].apply(
            lambda r: score_ping_row(r, has_loss_col=has_loss_col), axis=1
        )
    if (probe == "dns").any():
        df.loc[probe == "dns", "score"] = df.loc[probe == "dns"].apply(score_dns_row, axis=1)
    if (probe == "http").any():
        df.loc[probe == "http", "score"] = df.loc[probe == "http"].apply(score_http_row, axis=1)

    df["tier"] = df["score"].apply(tier_from_score)

    # --- Z-score normalization (global, within this dataset) ---
    score_mean = float(df["score"].mean())
    score_std = float(df["score"].std(ddof=0))
    if score_std < 1e-9:
        df["score_z"] = 0.0
    else:
        df["score_z"] = (df["score"] - score_mean) / score_std

    # Deterministic ordering
    sort_cols = [c for c in ["timestamp", "service_name", "probe_type"] if c in df.columns]
    df = df.sort_values(sort_cols).reset_index(drop=True)

    # Save row-level enriched data
    df.to_csv(OUT_ROWS_PATH, index=False)

    # Hourly summary (all services, all probes)
    hourly = (
        df.groupby("hour")
        .agg(
            score_avg=("score", "mean"),
            score_z_avg=("score_z", "mean"),
            score_p10=("score", lambda s: s.quantile(0.10)),
            score_p90=("score", lambda s: s.quantile(0.90)),
            good_pct=("tier", lambda t: 100.0 * (t == "good").mean()),
            bad_pct=("tier", lambda t: 100.0 * (t == "bad").mean()),
            num_rows=("tier", "size"),
        )
        .sort_index()
        .reset_index()
    )
    float_cols = ["score_avg", "score_z_avg", "score_p10", "score_p90", "good_pct", "bad_pct"]
    hourly[float_cols] = hourly[float_cols].round(2)
    hourly.to_csv(OUT_HOURLY_PATH, index=False)

    # Service summary (worst first)
    service = (
        df.groupby("service_name")
        .agg(
            score_avg=("score", "mean"),
            score_z_avg=("score_z", "mean"),
            good_pct=("tier", lambda t: 100.0 * (t == "good").mean()),
            bad_pct=("tier", lambda t: 100.0 * (t == "bad").mean()),
            num_rows=("tier", "size"),
        )
        .sort_values("score_avg", ascending=True)
        .reset_index()
    )
    service[["score_avg", "score_z_avg", "good_pct", "bad_pct"]] = service[
        ["score_avg", "score_z_avg", "good_pct", "bad_pct"]
    ].round(2)
    service.to_csv(OUT_SERVICE_PATH, index=False)

    print(f"Saved: {OUT_ROWS_PATH}")
    print(f"Saved: {OUT_HOURLY_PATH}")
    print(f"Saved: {OUT_SERVICE_PATH}")
    print(f"Rows scored: {len(df)}")


if __name__ == "__main__":
    main()
