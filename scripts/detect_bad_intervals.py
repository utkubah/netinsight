"""
NetInsight - Bad Interval Detection (statistical) + Service Attribution + Diagnosis + Z

Reads:
  data/quality_rows.csv

Writes:
  data/bad_intervals.csv

Run:
  python3 scripts/detect_bad_intervals.py

What it does:
- Rolling windows (WINDOW_MINUTES), sampled every STEP_MINUTES
- Computes per-window:
    mean_score, bad_pct, n_samples
- Computes dataset baseline over windows:
    global_mean, global_std
- Adds per-window z-score:
    window_score_z = (mean_score - global_mean) / global_std   (negative => worse)
- Flags "bad windows" via:
    window_score_z <= -K_STD   OR   bad_pct >= BAD_PCT_THRESHOLD
- Merges consecutive bad windows into intervals (sample-weighted)
- Adds interval attribution:
    affected_services_count, top_services_by_bad_pct, top_services_by_count
- Adds diagnosis:
    gateway_involved, diagnosis (network_wide vs service_specific)
- Adds interval normalization:
    mean_score_z, mean_score_delta (relative to global window baseline)
"""

from pathlib import Path
import pandas as pd

IN_PATH = Path("data") / "quality_rows.csv"
OUT_PATH = Path("data") / "bad_intervals.csv"

TIMEZONE = "Europe/Istanbul"

WINDOW_MINUTES = 5
STEP_MINUTES = 1
MIN_SAMPLES = 30

# "low mean" threshold in z units (negative z is worse)
K_STD = 1.0

# high-bad threshold
BAD_PCT_THRESHOLD = 50.0  # percent (0..100)

# severity thresholds (z is negative when worse)
SEV_1_Z = -1.0
SEV_2_Z = -1.5
SEV_3_Z = -2.0

SEV_1_BAD_PCT = 50.0
SEV_2_BAD_PCT = 60.0
SEV_3_BAD_PCT = 80.0

# Diagnosis threshold: how many services affected => "network-wide"
NETWORK_WIDE_MIN_AFFECTED_SERVICES = 8


def ensure_tz(ts: pd.Series) -> pd.Series:
    """
    Parse timestamps and ensure tz-aware in TIMEZONE.
    - If tz-aware: convert to TIMEZONE.
    - If tz-naive: assume UTC then convert to TIMEZONE.
    """
    d = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(d.dt, "tz") and d.dt.tz is not None:
        return d.dt.tz_convert(TIMEZONE)

    d = d.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return d.dt.tz_convert(TIMEZONE)


def build_window_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rolling time-window metrics sampled every STEP_MINUTES.

    Output columns:
      window_end, window_start, mean_score, bad_pct, n_samples
    """
    df = df.sort_values("timestamp").copy()
    df = df.set_index("timestamp")

    w = f"{WINDOW_MINUTES}min"

    roll_mean = df["score"].rolling(w, min_periods=MIN_SAMPLES).mean()
    roll_bad = df["is_bad"].rolling(w, min_periods=MIN_SAMPLES).mean()
    roll_n = df["score"].rolling(w, min_periods=MIN_SAMPLES).count()

    tmp = pd.DataFrame(
        {
            "mean_score": roll_mean,
            "bad_pct": 100.0 * roll_bad,
            "n_samples": roll_n,
        }
    )

    sampled = tmp.resample(f"{STEP_MINUTES}min").last()
    sampled = sampled.dropna(subset=["mean_score", "bad_pct", "n_samples"]).copy()

    sampled = sampled.reset_index().rename(columns={"timestamp": "window_end"})
    sampled["window_start"] = sampled["window_end"] - pd.Timedelta(minutes=WINDOW_MINUTES)

    sampled["mean_score"] = sampled["mean_score"].round(2)
    sampled["bad_pct"] = sampled["bad_pct"].round(2)
    sampled["n_samples"] = sampled["n_samples"].astype(int)

    return sampled


def severity_from(window_score_z: float, bad_pct: float) -> int:
    """
    Severity rule:
      - Sev3: z <= -2.0 OR bad_pct >= 80
      - Sev2: z <= -1.5 OR bad_pct >= 60
      - Sev1: z <= -1.0 OR bad_pct >= 50
    """
    if (window_score_z <= SEV_3_Z) or (bad_pct >= SEV_3_BAD_PCT):
        return 3
    if (window_score_z <= SEV_2_Z) or (bad_pct >= SEV_2_BAD_PCT):
        return 2
    if (window_score_z <= SEV_1_Z) or (bad_pct >= SEV_1_BAD_PCT):
        return 1
    return 0


def merge_bad_windows(w: pd.DataFrame) -> pd.DataFrame:
    """
    Merge consecutive bad windows into intervals.

    Weighted aggregation:
      interval_mean_score = weighted by n_samples over windows
      interval_bad_pct    = weighted by n_samples over windows
      interval_mean_score_z = weighted by n_samples over windows (optional but nice)

    Expects columns in w:
      window_start, window_end, mean_score, bad_pct, n_samples,
      flag_low_mean, flag_high_bad, is_bad_window, severity
    """
    bad = w[w["is_bad_window"]].sort_values("window_start").reset_index(drop=True)
    if bad.empty:
        return pd.DataFrame(
            columns=[
                "start_time",
                "end_time",
                "duration_seconds",
                "mean_score",
                "bad_pct",
                "n_samples",
                "num_windows",
                "severity",
                "reason",
            ]
        )

    step = pd.Timedelta(minutes=STEP_MINUTES)
    intervals = []

    cur_start = bad.loc[0, "window_start"]
    cur_end = bad.loc[0, "window_end"]

    w_sum_score = float(bad.loc[0, "mean_score"]) * int(bad.loc[0, "n_samples"])
    w_sum_bad = float(bad.loc[0, "bad_pct"]) * int(bad.loc[0, "n_samples"])
    w_sum_n = int(bad.loc[0, "n_samples"])
    num_windows = 1

    cur_sev = int(bad.loc[0, "severity"])
    any_low_mean = bool(bad.loc[0, "flag_low_mean"])
    any_high_bad = bool(bad.loc[0, "flag_high_bad"])

    def finalize_interval():
        mean_score = (w_sum_score / w_sum_n) if w_sum_n > 0 else 0.0
        bad_pct = (w_sum_bad / w_sum_n) if w_sum_n > 0 else 0.0
        reason = (
            "low_mean+high_bad"
            if (any_low_mean and any_high_bad)
            else ("low_mean" if any_low_mean else "high_bad")
        )
        return {
            "start_time": cur_start,
            "end_time": cur_end,
            "duration_seconds": float((cur_end - cur_start).total_seconds()),
            "mean_score": round(mean_score, 2),
            "bad_pct": round(bad_pct, 2),
            "n_samples": int(w_sum_n),
            "num_windows": int(num_windows),
            "severity": int(cur_sev),
            "reason": reason,
        }

    for i in range(1, len(bad)):
        row = bad.loc[i]
        next_start = row["window_start"]
        next_end = row["window_end"]

        contiguous = next_start <= (cur_end + step)

        if contiguous:
            cur_end = max(cur_end, next_end)

            n_i = int(row["n_samples"])
            w_sum_score += float(row["mean_score"]) * n_i
            w_sum_bad += float(row["bad_pct"]) * n_i
            w_sum_n += n_i
            num_windows += 1

            cur_sev = max(cur_sev, int(row["severity"]))
            any_low_mean = any_low_mean or bool(row["flag_low_mean"])
            any_high_bad = any_high_bad or bool(row["flag_high_bad"])
        else:
            intervals.append(finalize_interval())

            cur_start = next_start
            cur_end = next_end

            n_i = int(row["n_samples"])
            w_sum_score = float(row["mean_score"]) * n_i
            w_sum_bad = float(row["bad_pct"]) * n_i
            w_sum_n = n_i
            num_windows = 1

            cur_sev = int(row["severity"])
            any_low_mean = bool(row["flag_low_mean"])
            any_high_bad = bool(row["flag_high_bad"])

    intervals.append(finalize_interval())

    out = pd.DataFrame(intervals)
    out["duration_seconds"] = out["duration_seconds"].round(2)
    out = out.sort_values(["severity", "duration_seconds"], ascending=[False, False]).reset_index(drop=True)
    return out


def attribute_services(df_rows: pd.DataFrame, intervals: pd.DataFrame, top_k: int = 3) -> pd.DataFrame:
    """
    Adds columns:
      affected_services_count
      top_services_by_bad_pct   (e.g. 'gateway(100%),discord(92%),...')
      top_services_by_count     (e.g. 'youtube(123),google(120),...')
    """
    intervals = intervals.copy()

    if intervals.empty or "service_name" not in df_rows.columns:
        intervals["affected_services_count"] = 0
        intervals["top_services_by_bad_pct"] = ""
        intervals["top_services_by_count"] = ""
        return intervals

    df_rows = df_rows.sort_values("timestamp").copy()

    affected_counts = []
    top_bad_list = []
    top_count_list = []

    for _, itv in intervals.iterrows():
        start = itv["start_time"]
        end = itv["end_time"]

        seg = df_rows[(df_rows["timestamp"] >= start) & (df_rows["timestamp"] <= end)].copy()
        if seg.empty:
            affected_counts.append(0)
            top_bad_list.append("")
            top_count_list.append("")
            continue

        per = (
            seg.groupby("service_name")
            .agg(
                bad_pct=("is_bad", lambda s: 100.0 * s.mean()),
                n=("is_bad", "size"),
            )
            .reset_index()
        )

        affected = int((per["bad_pct"] > 0).sum())
        affected_counts.append(affected)

        top_bad = per.sort_values(["bad_pct", "n"], ascending=[False, False]).head(top_k)
        top_bad_str = ",".join([f"{r.service_name}({r.bad_pct:.0f}%)" for r in top_bad.itertuples(index=False)])
        top_bad_list.append(top_bad_str)

        top_n = per.sort_values("n", ascending=False).head(top_k)
        top_n_str = ",".join([f"{r.service_name}({int(r.n)})" for r in top_n.itertuples(index=False)])
        top_count_list.append(top_n_str)

    intervals["affected_services_count"] = affected_counts
    intervals["top_services_by_bad_pct"] = top_bad_list
    intervals["top_services_by_count"] = top_count_list
    return intervals


def add_diagnosis(intervals: pd.DataFrame) -> pd.DataFrame:
    """
    Adds columns:
      gateway_involved (bool)
      diagnosis: 'network_wide' or 'service_specific'
    """
    intervals = intervals.copy()

    intervals["gateway_involved"] = (
        intervals.get("top_services_by_bad_pct", pd.Series([""] * len(intervals)))
        .astype(str)
        .str.contains("gateway(", regex=False)
    )

    def diag(row) -> str:
        affected = int(row.get("affected_services_count", 0))
        if affected >= NETWORK_WIDE_MIN_AFFECTED_SERVICES:
            return "network_wide"
        return "service_specific"

    intervals["diagnosis"] = intervals.apply(diag, axis=1)
    return intervals


def main() -> None:
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input not found: {IN_PATH}. Run scripts/quality_score.py first.")

    df = pd.read_csv(IN_PATH)

    required = {"timestamp", "score", "tier"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {IN_PATH}: {sorted(missing)}")

    df["timestamp"] = ensure_tz(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).copy()

    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["score"]).copy()

    df["is_bad"] = (df["tier"].astype(str) == "bad").astype(int)

    windows = build_window_table(df)
    if windows.empty:
        print("No valid windows produced (check MIN_SAMPLES / data density).")
        return

    global_mean = float(windows["mean_score"].mean())
    global_std = float(windows["mean_score"].std(ddof=0))

    # per-window z-score (negative => worse)
    if global_std > 1e-9:
        windows["window_score_z"] = (windows["mean_score"] - global_mean) / global_std
    else:
        windows["window_score_z"] = 0.0

    # flags
    windows["flag_low_mean"] = windows["window_score_z"] <= (-K_STD)
    windows["flag_high_bad"] = windows["bad_pct"] >= BAD_PCT_THRESHOLD
    windows["is_bad_window"] = windows["flag_low_mean"] | windows["flag_high_bad"]

    # severity (standardized by z)
    windows["severity"] = windows.apply(
        lambda r: severity_from(float(r["window_score_z"]), float(r["bad_pct"])),
        axis=1,
    )

    intervals = merge_bad_windows(windows)
    intervals = attribute_services(df, intervals, top_k=3)
    intervals = add_diagnosis(intervals)

    # interval normalization vs global window baseline
    if global_std > 1e-9:
        intervals["mean_score_z"] = (intervals["mean_score"] - global_mean) / global_std
    else:
        intervals["mean_score_z"] = 0.0
    intervals["mean_score_z"] = intervals["mean_score_z"].round(2)

    # NEW: delta in raw score units (interpretable)
    intervals["mean_score_delta"] = (intervals["mean_score"] - global_mean).round(2)

    intervals.to_csv(OUT_PATH, index=False)

    print("=== Bad Interval Detection Summary ===")
    print(f"Windows: {len(windows)}")
    print(f"Bad windows: {int(windows['is_bad_window'].sum())}")
    print(f"Global mean score: {global_mean:.2f}")
    print(f"Global std score:  {global_std:.2f}")
    print(f"Saved: {OUT_PATH}")

    if intervals.empty:
        print("No bad intervals detected with current thresholds.")
    else:
        print("\nTop intervals (severity, duration):")
        cols = [
            "start_time",
            "end_time",
            "duration_seconds",
            "mean_score",
            "mean_score_delta",
            "mean_score_z",
            "bad_pct",
            "severity",
            "reason",
            "affected_services_count",
            "top_services_by_bad_pct",
            "gateway_involved",
            "diagnosis",
        ]
        cols = [c for c in cols if c in intervals.columns]
        print(intervals[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
