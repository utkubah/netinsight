# scripts/analyze_speedtest.py
"""
NetInsight - Speedtest Analysis

Reads:
  data/netinsight_speedtest.csv

Writes:
  data/speedtest_summary.csv
  data/speedtest_hourly.csv

Run:
  python3 scripts/analyze_speedtest.py
"""

from pathlib import Path
import pandas as pd

IN_PATH = Path("data") / "netinsight_speedtest.csv"
OUT_SUMMARY = Path("data") / "speedtest_summary.csv"
OUT_HOURLY = Path("data") / "speedtest_hourly.csv"

# timezone
TIMEZONE = "Europe/Rome"


def ensure_tz(ts: pd.Series) -> pd.Series:
    d = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(d.dt, "tz") and d.dt.tz is not None:
        return d.dt.tz_convert(TIMEZONE)
    d = d.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return d.dt.tz_convert(TIMEZONE)


def main() -> None:
    if not IN_PATH.exists():
        print(f"[speedtest] no input yet: {IN_PATH} (run: python3 -m src.cli speedtest)")
        return

    df = pd.read_csv(IN_PATH)

    required = {"timestamp", "ping_ms", "download_mbps", "upload_mbps", "error"}
    missing = required - set(df.columns)
    if missing:
        print(f"[speedtest] schema mismatch in {IN_PATH}. Missing: {sorted(missing)}. Found: {list(df.columns)}")
        return

    df["timestamp"] = ensure_tz(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).copy()

    for c in ["ping_ms", "download_mbps", "upload_mbps"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["ok"] = df["error"].fillna("").astype(str).str.len().eq(0)

    ok_df = df[df["ok"]].copy()

    summary = {
        "total_runs": int(len(df)),
        "ok_runs": int(df["ok"].sum()),
        "error_runs": int((~df["ok"]).sum()),
        "ping_ms_avg": float(ok_df["ping_ms"].mean()) if not ok_df.empty else None,
        "download_mbps_avg": float(ok_df["download_mbps"].mean()) if not ok_df.empty else None,
        "upload_mbps_avg": float(ok_df["upload_mbps"].mean()) if not ok_df.empty else None,
        "download_mbps_p10": float(ok_df["download_mbps"].quantile(0.10)) if not ok_df.empty else None,
        "download_mbps_p90": float(ok_df["download_mbps"].quantile(0.90)) if not ok_df.empty else None,
        "upload_mbps_p10": float(ok_df["upload_mbps"].quantile(0.10)) if not ok_df.empty else None,
        "upload_mbps_p90": float(ok_df["upload_mbps"].quantile(0.90)) if not ok_df.empty else None,
    }
    pd.DataFrame([summary]).to_csv(OUT_SUMMARY, index=False)

    df["hour"] = df["timestamp"].dt.hour
    hourly = (
        df[df["ok"]]
        .groupby("hour")
        .agg(
            ping_ms_avg=("ping_ms", "mean"),
            download_mbps_avg=("download_mbps", "mean"),
            upload_mbps_avg=("upload_mbps", "mean"),
            n=("ok", "size"),
        )
        .reset_index()
        .sort_values("hour")
    )
    if not hourly.empty:
        hourly[["ping_ms_avg", "download_mbps_avg", "upload_mbps_avg"]] = hourly[
            ["ping_ms_avg", "download_mbps_avg", "upload_mbps_avg"]
        ].round(2)
    hourly.to_csv(OUT_HOURLY, index=False)

    print(f"Saved: {OUT_SUMMARY}")
    print(f"Saved: {OUT_HOURLY}")


if __name__ == "__main__":
    main()
