"""
NetInsight - WiFi Diagnostic Analysis

Reads:
  data/netinsight_wifi_diag.csv   (produced by src/mode_wifi_diag.py)

Writes:
  data/wifi_diag_windows.csv      (rolling-window summary)
  data/wifi_diag_summary.csv      (1-row quick summary)

Run:
  python3 scripts/analyze_wifi_diag.py

Goal:
- Compare gateway (local Wi-Fi path) vs google (external path)
- Decide whether issues are likely:
    - wifi_local (gateway bad)
    - isp_external (gateway ok, google bad)
    - both_bad
    - healthy_or_inconclusive
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

IN_PATH = Path("data") / "netinsight_wifi_diag.csv"
OUT_WINDOWS = Path("data") / "wifi_diag_windows.csv"
OUT_SUMMARY = Path("data") / "wifi_diag_summary.csv"

TIMEZONE = "Europe/Istanbul"

WINDOW_SECONDS = 60  # rolling window size
STEP_SECONDS = 10    # sample step (resample grid)
MIN_SAMPLES = 5

# thresholds (tune later)
LOSS_BAD_PCT = 5.0
JITTER_BAD_MS = 25.0
LAT_BAD_MS = 80.0


def ensure_tz(ts: pd.Series) -> pd.Series:
    d = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(d.dt, "tz") and d.dt.tz is not None:
        return d.dt.tz_convert(TIMEZONE)
    d = d.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return d.dt.tz_convert(TIMEZONE)


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def main() -> None:
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input not found: {IN_PATH}. Run src/mode_wifi_diag.py first.")

    df = pd.read_csv(IN_PATH)
    if df.empty:
        print("wifi_diag: input is empty.")
        return

    # --- normalize timestamp ---
    ts_col = _pick_col(df, ["timestamp", "time", "ts"])
    if not ts_col:
        raise ValueError(f"wifi_diag: could not find a timestamp column. Have: {list(df.columns)}")
    df["timestamp"] = ensure_tz(df[ts_col])
    df = df.dropna(subset=["timestamp"]).copy()

    # --- normalize role/service column ---
    # Utku's wifi_diag usually has role=gateway/google, not service_name/probe_type
    role_col = _pick_col(df, ["role", "service_name", "target", "name"])
    if not role_col:
        raise ValueError(f"wifi_diag: could not find role column. Have: {list(df.columns)}")

    df["role"] = df[role_col].astype(str).str.strip().str.lower()

    # map common variants to gateway/google
    role_map = {
        "gw": "gateway",
        "router": "gateway",
        "local": "gateway",
        "gateway": "gateway",
        "google": "google",
        "external": "google",
        "internet": "google",
    }
    df["role"] = df["role"].map(lambda x: role_map.get(x, x))

    # --- numeric metrics ---
    # accept multiple possible column names
    lat_col = _pick_col(df, ["latency_ms", "latency_avg_ms", "latency", "rtt_avg_ms", "avg_ms"])
    p95_col = _pick_col(df, ["latency_p95_ms", "p95_ms", "rtt_p95_ms"])
    jit_col = _pick_col(df, ["jitter_ms", "jitter"])
    loss_col = _pick_col(df, ["packet_loss_pct", "loss_pct", "loss"])

    if not lat_col or not jit_col or not loss_col:
        raise ValueError(
            "wifi_diag: missing required metric columns. "
            f"Need latency+jitter+loss. Have: {list(df.columns)}"
        )

    df["latency_ms"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["jitter_ms"] = pd.to_numeric(df[jit_col], errors="coerce")
    df["packet_loss_pct"] = pd.to_numeric(df[loss_col], errors="coerce")

    if p95_col:
        df["latency_p95_ms"] = pd.to_numeric(df[p95_col], errors="coerce")
    else:
        df["latency_p95_ms"] = pd.NA

    df = df.dropna(subset=["latency_ms", "jitter_ms", "packet_loss_pct"]).copy()
    if df.empty:
        print("wifi_diag: no usable numeric rows after cleaning.")
        return

    # --- build rolling windows per role ---
    df = df.sort_values("timestamp").set_index("timestamp")

    window = f"{WINDOW_SECONDS}s"
    step = f"{STEP_SECONDS}s"

    rows = []
    for role in ["gateway", "google"]:
        seg = df[df["role"] == role].copy()
        if seg.empty:
            continue

        roll_lat = seg["latency_ms"].rolling(window, min_periods=MIN_SAMPLES).mean()
        roll_jit = seg["jitter_ms"].rolling(window, min_periods=MIN_SAMPLES).mean()
        roll_loss = seg["packet_loss_pct"].rolling(window, min_periods=MIN_SAMPLES).mean()
        roll_n = seg["latency_ms"].rolling(window, min_periods=MIN_SAMPLES).count()

        tmp = pd.DataFrame(
            {
                "role": role,
                "latency_ms": roll_lat,
                "jitter_ms": roll_jit,
                "packet_loss_pct": roll_loss,
                "n_samples": roll_n,
            }
        )

        sampled = tmp.resample(step).last().dropna(subset=["latency_ms", "jitter_ms", "packet_loss_pct", "n_samples"])
        sampled = sampled.reset_index().rename(columns={"timestamp": "window_end"})
        sampled["window_start"] = sampled["window_end"] - pd.Timedelta(seconds=WINDOW_SECONDS)

        sampled["latency_ms"] = sampled["latency_ms"].round(2)
        sampled["jitter_ms"] = sampled["jitter_ms"].round(2)
        sampled["packet_loss_pct"] = sampled["packet_loss_pct"].round(2)
        sampled["n_samples"] = sampled["n_samples"].astype(int)

        # flags
        sampled["flag_bad_loss"] = sampled["packet_loss_pct"] >= LOSS_BAD_PCT
        sampled["flag_bad_jitter"] = sampled["jitter_ms"] >= JITTER_BAD_MS
        sampled["flag_bad_latency"] = sampled["latency_ms"] >= LAT_BAD_MS
        sampled["is_bad"] = sampled["flag_bad_loss"] | sampled["flag_bad_jitter"] | sampled["flag_bad_latency"]

        rows.append(sampled)

    if not rows:
        print("wifi_diag: not enough data for gateway/google.")
        return

    windows = pd.concat(rows, ignore_index=True)
    windows.to_csv(OUT_WINDOWS, index=False)

    # --- summary decision (use last available window for each role) ---
    def last_role(role: str) -> pd.Series | None:
        r = windows[windows["role"] == role]
        if r.empty:
            return None
        return r.sort_values("window_end").iloc[-1]

    gw = last_role("gateway")
    gg = last_role("google")

    def pretty_row(r: pd.Series | None) -> str:
        if r is None:
            return "missing"
        return f"lat={r['latency_ms']}ms jit={r['jitter_ms']}ms loss={r['packet_loss_pct']}% bad={bool(r['is_bad'])} n={int(r['n_samples'])}"

    # diagnosis
    diagnosis = "healthy_or_inconclusive"
    if gw is not None and gg is not None:
        gw_bad = bool(gw["is_bad"])
        gg_bad = bool(gg["is_bad"])
        if gw_bad and gg_bad:
            diagnosis = "both_bad"
        elif gw_bad and not gg_bad:
            diagnosis = "wifi_local"
        elif (not gw_bad) and gg_bad:
            diagnosis = "isp_external"
        else:
            diagnosis = "healthy_or_inconclusive"
    elif gw is not None and gg is None:
        diagnosis = "inconclusive_missing_google"
    elif gw is None and gg is not None:
        diagnosis = "inconclusive_missing_gateway"
    else:
        diagnosis = "inconclusive_no_data"

    summary = pd.DataFrame(
        [{
            "diagnosis": diagnosis,
            "gateway_last": pretty_row(gw),
            "google_last": pretty_row(gg),
            "total_windows": int(len(windows)),
        }]
    )
    summary.to_csv(OUT_SUMMARY, index=False)

    print(f"Saved: {OUT_WINDOWS}")
    print(f"Saved: {OUT_SUMMARY}")
    print("\nwifi_diag last windows:")
    print(f"  gateway: {pretty_row(gw)}")
    print(f"  google : {pretty_row(gg)}")
    print(f"\nDiagnosis: {diagnosis}")


if __name__ == "__main__":
    main()
