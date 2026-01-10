"""
Quick inspection tool for NetInsight logs.

Run:
  python3 scripts/inspect_log.py
"""

from pathlib import Path
import sys
import pandas as pd

LOG_PATH = Path("data") / "netinsight_log.csv"
TIMEZONE = "Europe/Rome"


def parse_timestamp(ts: pd.Series) -> pd.Series:
    dt = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_convert(TIMEZONE)
    else:
        dt = dt.dt.tz_localize(TIMEZONE, nonexistent="shift_forward", ambiguous="NaT")
    return dt


def main() -> None:
    if not LOG_PATH.exists():
        print(f"Log file not found: {LOG_PATH}")
        print("Run the NetInsight collector first (src/main.py) to generate data.")
        sys.exit(1)

    df = pd.read_csv(LOG_PATH)

    print("=== Basic info ===")
    print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
    print("Columns:", list(df.columns))
    print()

    if "timestamp" in df.columns:
        df["timestamp"] = parse_timestamp(df["timestamp"])
        ts_ok = df["timestamp"].dropna()
        if not ts_ok.empty:
            print("=== Time range ===")
            print(f"min: {ts_ok.min()}")
            print(f"max: {ts_ok.max()}")
            print()

    print("=== Head ===")
    print(df.head())
    print()

    # Success rates by probe_type
    if {"probe_type", "success"} <= set(df.columns):
        print("=== Success rate by probe_type ===")
        success_stats = (
            df.groupby("probe_type")["success"]
            .value_counts(normalize=True)
            .rename("fraction")
            .reset_index()
        )
        success_stats["success"] = success_stats["success"].astype(str)
        print(success_stats)
        print()
    else:
        print("probe_type and/or success columns not found; skipping success breakdown.\n")

    # Per-service summary
    needed = {"service_name", "probe_type", "latency_ms", "success"}
    if needed <= set(df.columns):
        print("=== Per-service summary (mean latency_ms, success_rate) ===")
        summary = (
            df.groupby(["service_name", "probe_type"])
            .agg(
                mean_latency_ms=("latency_ms", "mean"),
                success_rate=("success", "mean"),  # 0..1
                count=("latency_ms", "size"),
            )
            .reset_index()
            .sort_values(["service_name", "probe_type"])
        )
        summary["mean_latency_ms"] = summary["mean_latency_ms"].round(2)
        summary["success_rate"] = summary["success_rate"].round(3)
        print(summary)
        print()
    else:
        print("service_name / probe_type / latency_ms / success missing; skipping per-service summary.\n")

    print("=== Error overview ===")
    if "error_kind" in df.columns:
        err_counts = (
            df[df["error_kind"].notna() & (df["error_kind"] != "ok")]["error_kind"]
            .value_counts()
        )
        print("Top error kinds:")
        print(err_counts.head(20))
        print()
    elif "error_message" in df.columns:
        err_counts = (
            df[df["error_message"].notna() & (df["error_message"] != "")]["error_message"]
            .value_counts()
        )
        print("Top error messages (raw):")
        print(err_counts.head(10))
        print()
    else:
        print("No error_kind or error_message column found.\n")

    # Sample a couple services
    if "service_name" in df.columns:
        for svc_name in ["discord", "x_com"]:
            if svc_name in set(df["service_name"].astype(str)):
                print(f"=== Sample rows for service_name == '{svc_name}' ===")
                cols = [c for c in ["timestamp", "probe_type", "success", "latency_ms", "error_kind", "error_message"] if c in df.columns]
                view = df[df["service_name"] == svc_name].copy()
                if "timestamp" in view.columns:
                    view = view.sort_values("timestamp")
                print(view[cols].head(10))
                print()

    if {"service_name", "probe_type", "error_kind"} <= set(df.columns):
        print("=== Counts by (service, probe, error_kind) ===")
        print(df.groupby(["service_name", "probe_type", "error_kind"]).size().sort_values(ascending=False).head(40))
        print()

    print("Done.")


if __name__ == "__main__":
    main()
