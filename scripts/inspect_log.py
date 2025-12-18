# scripts/inspect_log.py
"""
Quick inspection tool for NetInsight logs.

Run from the project root as:
    python scripts/inspect_log.py

It will:
- load data/netinsight_log.csv into a pandas DataFrame
- print head()
- show success rates by probe_type
- show per-service latency + success summary
- show top error kinds / messages
- show a few rows for interesting services like discord and x_com
"""

import os
import sys

import pandas as pd


LOG_PATH = os.path.join("data", "netinsight_log.csv")


def main() -> None:
    if not os.path.exists(LOG_PATH):
        print(f"Log file not found: {LOG_PATH}")
        print("Run the NetInsight collector first (main.py) to generate some data.")
        sys.exit(1)

    df = pd.read_csv(LOG_PATH)

    print("=== Basic info ===")
    print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
    print("Columns:", list(df.columns))
    print()

    print("=== Head ===")
    print(df.head())
    print()

    # Make sure expected columns exist
    missing = [col for col in ["probe_type", "success", "latency_ms"] if col not in df.columns]
    if missing:
        print("WARNING: Missing expected columns in CSV:", missing)
        print("You may be using an older schema.")
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
        # Convert True/False to readable
        success_stats["success"] = success_stats["success"].astype(str)
        print(success_stats)
        print()
    else:
        print("probe_type and/or success columns not found; skipping success breakdown.\n")

    # Per-service summary: avg latency and success rate per service + probe_type
    if {"service_name", "probe_type", "latency_ms", "success"} <= set(df.columns):
        print("=== Per-service summary (mean latency_ms, success rate) ===")
        summary = (
            df.groupby(["service_name", "probe_type"])
            .agg(
                mean_latency_ms=("latency_ms", "mean"),
                success_rate=("success", "mean"),  # fraction of rows with success=True
                count=("latency_ms", "size"),
            )
            .reset_index()
            .sort_values(["service_name", "probe_type"])
        )
        # Round for nicer printing
        summary["mean_latency_ms"] = summary["mean_latency_ms"].round(2)
        summary["success_rate"] = summary["success_rate"].round(3)
        print(summary)
        print()
    else:
        print("service_name / probe_type / latency_ms / success missing; "
              "skipping per-service summary.\n")

    # Error overview: prefer error_kind if present, else fall back to error_message
    print("=== Error overview ===")
    if "error_kind" in df.columns:
        err_counts = df[df["error_kind"].notna() & (df["error_kind"] != "ok")]["error_kind"].value_counts()
        print("Top error kinds:")
        print(err_counts.head(20))
        print()
    elif "error_message" in df.columns:
        err_counts = df[df["error_message"].notna() & (df["error_message"] != "")]["error_message"].value_counts()
        print("Top error messages (raw):")
        print(err_counts.head(10))
        print()
    else:
        print("No error_kind or error_message column found.\n")

    # Inspect some specific interesting services
    for svc_name in ["discord", "x_com"]:
        if "service_name" in df.columns and svc_name in df["service_name"].unique():
            print(f"=== Sample rows for service_name == '{svc_name}' ===")
            print(
                df[df["service_name"] == svc_name]
                .sort_values("timestamp")
                .head(10)
            )
            print()

    print(df.groupby(["service_name", "probe_type", "error_kind"]).size())


    print("Done.")


if __name__ == "__main__":
    main()
