import math
import pandas as pd
from pathlib import Path


LOG_PATH = Path("data") / "netinsight_log.csv"
OUT_ROWS_PATH = Path("data") / "quality_rows.csv"
OUT_HOURLY_PATH = Path("data") / "quality_hourly.csv"
OUT_SERVICE_PATH = Path("data") / "quality_by_service.csv"

# --- Scoring weights (tweakable) ---
W_PING = 0.55
W_DNS = 0.15
W_HTTP = 0.30

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def score_ping(row: pd.Series) -> float:
    """
    Returns 0..100 for a ping row.
    Uses latency_ms, jitter_ms, packet_loss_pct (if present), success.
    """
    # If ping failed, score is low
    if int(row.get("success", 1)) == 0:
        return 0.0

    lat = row.get("latency_ms")
    jit = row.get("jitter_ms")
    loss = row.get("packet_loss_pct")

    # Fallbacks if columns missing
    lat = float(lat) if pd.notna(lat) else 9999.0
    jit = float(jit) if pd.notna(jit) else 9999.0
    loss = float(loss) if pd.notna(loss) else 0.0

    # Latency score: 0ms=>100, 200ms=>~50, 600ms=>~10
    lat_score = 100.0 * math.exp(-lat / 200.0)

    # Jitter score: 0ms=>100, 20ms=>~37, 50ms=>~8
    jit_score = 100.0 * math.exp(-jit / 20.0)

    # Loss score: 0%=>100, 2%=>~37, 10%=>~0.7
    loss_score = 100.0 * math.exp(-loss / 2.0)

    # Combine
    return clamp(0.55 * lat_score + 0.30 * jit_score + 0.15 * loss_score, 0.0, 100.0)

def score_dns(row: pd.Series) -> float:
    """
    Returns 0..100 for a DNS row.
    Uses dns_ms (or latency_ms), success.
    """
    if int(row.get("success", 1)) == 0:
        return 0.0

    dns_ms = row.get("dns_ms", row.get("latency_ms"))
    dns_ms = float(dns_ms) if pd.notna(dns_ms) else 9999.0

    # 0ms=>100, 50ms=>~37, 200ms=>~1.8
    s = 100.0 * math.exp(-dns_ms / 50.0)
    return clamp(s, 0.0, 100.0)

def score_http(row: pd.Series) -> float:
    """
    Returns 0..100 for an HTTP row.
    Uses http_ms (or latency_ms), status_code if present, success.
    """
    if int(row.get("success", 1)) == 0:
        return 0.0

    http_ms = row.get("http_ms", row.get("latency_ms"))
    http_ms = float(http_ms) if pd.notna(http_ms) else 9999.0

    # Base timing score: 0ms=>100, 300ms=>~37, 1200ms=>~2
    timing = 100.0 * math.exp(-http_ms / 300.0)

    # Penalize bad status codes if present
    status = row.get("status_code")
    if pd.notna(status):
        try:
            code = int(status)
            if 500 <= code < 600:
                timing *= 0.4
            elif 400 <= code < 500:
                timing *= 0.7
        except Exception:
            pass

    return clamp(timing, 0.0, 100.0)

def tier_from_score(score: float) -> str:
    if score >= 80:
        return "good"
    if score >= 50:
        return "ok"
    return "bad"

def main() -> None:
    df = pd.read_csv(LOG_PATH)

    # Parse time
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).copy()
    df["hour"] = df["timestamp"].dt.hour

    # Compute per-row scores
    probe = df["probe_type"].astype(str)

    df["score"] = 0.0
    df.loc[probe == "ping", "score"] = df[probe == "ping"].apply(score_ping, axis=1)
    df.loc[probe == "dns",  "score"] = df[probe == "dns"].apply(score_dns, axis=1)
    df.loc[probe == "http", "score"] = df[probe == "http"].apply(score_http, axis=1)

    df["tier"] = df["score"].apply(tier_from_score)

    # Save row-level enriched data
    df.to_csv(OUT_ROWS_PATH, index=False)

    # Hourly summary (all services, all probes)
    hourly = (
        df.groupby("hour")
        .agg(
            score_avg=("score", "mean"),
            score_p10=("score", lambda s: s.quantile(0.10)),
            score_p90=("score", lambda s: s.quantile(0.90)),
            good_pct=("tier", lambda t: 100.0 * (t == "good").mean()),
            bad_pct=("tier", lambda t: 100.0 * (t == "bad").mean()),
            n=("tier", "size"),
        )
        .sort_index()
        .reset_index()
    )
    hourly.to_csv(OUT_HOURLY_PATH, index=False)

    # Service summary
    service = (
        df.groupby("service_name")
        .agg(
            score_avg=("score", "mean"),
            good_pct=("tier", lambda t: 100.0 * (t == "good").mean()),
            bad_pct=("tier", lambda t: 100.0 * (t == "bad").mean()),
            n=("tier", "size"),
        )
        .sort_values("score_avg", ascending=True)
        .reset_index()
    )
    service.to_csv(OUT_SERVICE_PATH, index=False)

    print(f"Saved: {OUT_ROWS_PATH}")
    print(f"Saved: {OUT_HOURLY_PATH}")
    print(f"Saved: {OUT_SERVICE_PATH}")

if __name__ == "__main__":
    main()
