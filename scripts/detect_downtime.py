"""
NetInsight - Downtime Detection (ping)

Rule:
- Downtime event = >= MIN_CONSEC_FAILURES consecutive failures
- Failures belong to same event if gaps between failures <= MAX_GAP_SECONDS

Reads:
  data/netinsight_log.csv

Writes:
  data/downtimes.csv       (event-level)
  data/total_downtime.csv  (per-service totals)

Run:
  python3 scripts/detect_downtime.py
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

LOG_PATH = Path("data") / "netinsight_log.csv"
OUTPUT_EVENTS = Path("data") / "downtimes.csv"
OUTPUT_TOTALS = Path("data") / "total_downtime.csv"

MIN_CONSEC_FAILURES = 3
MAX_GAP_SECONDS = 90
PROBE_TYPE = "ping"
TIMEZONE = "Europe/Istanbul"


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

    required = {"timestamp", "service_name", "probe_type", "success"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}. Columns present: {list(df.columns)}")

    df["timestamp"] = parse_timestamp(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).copy()
    df["success"] = coerce_success(df["success"])

    df = df[df["probe_type"].astype(str) == PROBE_TYPE].copy()
    df = df.sort_values(["service_name", "timestamp"]).reset_index(drop=True)
    return df


def detect_downtimes_for_service(df: pd.DataFrame, service: str) -> List[Dict]:
    svc_df = df[df["service_name"] == service].reset_index(drop=True)

    events: List[Dict] = []

    current_start: Optional[pd.Timestamp] = None
    last_failure_ts: Optional[pd.Timestamp] = None
    fail_count = 0

    for _, row in svc_df.iterrows():
        ts: pd.Timestamp = row["timestamp"]
        ok = int(row["success"]) == 1

        if not ok:
            if current_start is None:
                current_start = ts
                last_failure_ts = ts
                fail_count = 1
            else:
                # check gap against last failure timestamp
                gap = (ts - last_failure_ts).total_seconds() if last_failure_ts is not None else 0
                if gap <= MAX_GAP_SECONDS:
                    fail_count += 1
                    last_failure_ts = ts
                else:
                    # close previous event
                    if fail_count >= MIN_CONSEC_FAILURES and last_failure_ts is not None:
                        events.append(
                            {
                                "service_name": service,
                                "probe_type": PROBE_TYPE,
                                "start_time": current_start,
                                "end_time": last_failure_ts,
                                "duration_seconds": float((last_failure_ts - current_start).total_seconds()),
                                "num_failures": int(fail_count),
                            }
                        )
                    # start new event
                    current_start = ts
                    last_failure_ts = ts
                    fail_count = 1

        else:
            # success closes any open downtime candidate
            if current_start is not None and last_failure_ts is not None:
                if fail_count >= MIN_CONSEC_FAILURES:
                    events.append(
                        {
                            "service_name": service,
                            "probe_type": PROBE_TYPE,
                            "start_time": current_start,
                            "end_time": last_failure_ts,
                            "duration_seconds": float((last_failure_ts - current_start).total_seconds()),
                            "num_failures": int(fail_count),
                        }
                    )
            current_start = None
            last_failure_ts = None
            fail_count = 0

    # end-of-file close
    if current_start is not None and last_failure_ts is not None and fail_count >= MIN_CONSEC_FAILURES:
        events.append(
            {
                "service_name": service,
                "probe_type": PROBE_TYPE,
                "start_time": current_start,
                "end_time": last_failure_ts,
                "duration_seconds": float((last_failure_ts - current_start).total_seconds()),
                "num_failures": int(fail_count),
            }
        )

    return events


def detect_all_downtimes(df: pd.DataFrame) -> pd.DataFrame:
    all_events: List[Dict] = []

    for service in sorted(df["service_name"].unique()):
        all_events.extend(detect_downtimes_for_service(df, service))

    if not all_events:
        return pd.DataFrame(
            columns=["service_name", "probe_type", "start_time", "end_time", "duration_seconds", "num_failures"]
        )

    events_df = pd.DataFrame(all_events)
    events_df = events_df.sort_values(["service_name", "start_time"]).reset_index(drop=True)
    return events_df


def compute_total_downtime(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=["service_name", "total_downtime_seconds", "num_events"])

    totals = (
        events.groupby("service_name")
        .agg(
            total_downtime_seconds=("duration_seconds", "sum"),
            num_events=("start_time", "count"),
        )
        .sort_values("total_downtime_seconds", ascending=False)
        .reset_index()
    )
    totals["total_downtime_seconds"] = totals["total_downtime_seconds"].round(2)
    return totals


def main() -> None:
    df = load_log()
    events = detect_all_downtimes(df)
    events.to_csv(OUTPUT_EVENTS, index=False)
    print(f"Saved downtime events to {OUTPUT_EVENTS}")

    totals = compute_total_downtime(events)
    totals.to_csv(OUTPUT_TOTALS, index=False)
    print(f"Saved total downtime summary to {OUTPUT_TOTALS}")

    if events.empty:
        print("No downtime events detected with current thresholds.")
    else:
        print("\n=== Total downtime per service ===")
        print(totals.to_string(index=False))


if __name__ == "__main__":
    main()
