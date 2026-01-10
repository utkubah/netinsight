"""
NetInsight - Time of Day Analysis (ping)

Reads:
  data/netinsight_log.csv

Writes:
  data/hourly_stats.csv   (ping-only, aggregated by hour)

Run:
  python3 scripts/analyze_time_of_day.py
"""

from pathlib import Path
import pandas as pd

LOG_PATH = Path("data") / "netinsight_log.csv"
OUT_PATH = Path("data") / "hourly_stats.csv"
TIMEZONE = "Europe/Rome"


def parse_timestamp(ts: pd.Series) -> pd.Series:
    dt = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_convert(TIMEZONE)
    else:
        dt = dt.dt.tz_localize(TIMEZONE, nonexistent="shift_forward", ambiguous="NaT")
    return dt


def coerce_success(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.astype(int)
    s2 = s.astype(str).str.strip().str.lower()
    mapping = {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0}
    out = s2.map(mapping)
    out = out.fillna(pd.to_numeric(s, errors="coerce")).fillna(0).astype(int).clip(0, 1)
    return out


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        raise FileNotFoundError(f"Log file not found: {LOG_PATH}")

    df = pd.read_csv(LOG_PATH)
    needed = {"timestamp", "probe_type", "success"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df["timestamp"] = parse_timestamp(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).copy()
    df["success"] = coerce_success(df["success"])
    df["hour"] = df["timestamp"].dt.hour
    return df


def hourly_ping_stats(df: pd.DataFrame) -> pd.DataFrame:
    ping_df = df[df["probe_type"].astype(str) == "ping"].copy()

    if ping_df.empty:
        return pd.DataFrame(columns=["hour", "avg_latency_ms", "packet_loss_pct", "num_probes"]).set_index("hour")

    # latency_ms might be missing if schema differs
    if "latency_ms" not in ping_df.columns:
        ping_df["latency_ms"] = pd.NA

    grouped = (
        ping_df.groupby("hour")
        .agg(
            avg_latency_ms=("latency_ms", "mean"),
            packet_loss_pct=("success", lambda s: 100.0 * (1.0 - s.mean())),
            num_probes=("success", "size"),
        )
        .sort_index()
    )

    grouped["avg_latency_ms"] = grouped["avg_latency_ms"].round(2)
    grouped["packet_loss_pct"] = grouped["packet_loss_pct"].round(2)
    return grouped


def print_hourly_summary(stats: pd.DataFrame) -> None:
    if stats.empty:
        print("No ping data available.")
        return

    print("\n=== Hourly Ping Stats (0-23) ===")
    print(stats)

    best_latency = stats.nsmallest(3, "avg_latency_ms")
    worst_latency = stats.nlargest(3, "avg_latency_ms")
    worst_loss = stats.nlargest(3, "packet_loss_pct")

    print("\n=== Best Hours (lowest avg latency) ===")
    print(best_latency)

    print("\n=== Worst Hours (highest avg latency) ===")
    print(worst_latency)

    print("\n=== Worst Hours (highest packet loss) ===")
    print(worst_loss)


def main():
    df = load_log()
    stats = hourly_ping_stats(df)

    print_hourly_summary(stats)
    stats.to_csv(OUT_PATH, index=True)
    print(f"\nSaved hourly stats to {OUT_PATH}")


if __name__ == "__main__":
    main()
