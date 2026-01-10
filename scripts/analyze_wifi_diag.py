# scripts/analyze_wifi_diag.py
"""
NetInsight - Wi-Fi diag analysis (robust)

Reads:
  data/netinsight_wifi_diag.csv

Writes:
  data/wifi_diag_summary.csv
  data/wifi_diag_windows.csv

Run:
  python3 scripts/analyze_wifi_diag.py
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

IN_PATH = Path("data") / "netinsight_wifi_diag.csv"
OUT_SUMMARY = Path("data") / "wifi_diag_summary.csv"
OUT_WINDOWS = Path("data") / "wifi_diag_windows.csv"

TIMEZONE = "Europe/Rome"


def ensure_tz(ts: pd.Series) -> pd.Series:
    d = pd.to_datetime(ts, errors="coerce", utc=False)
    if hasattr(d.dt, "tz") and d.dt.tz is not None:
        return d.dt.tz_convert(TIMEZONE)
    d = d.dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    return d.dt.tz_convert(TIMEZONE)


def _to_bool(x) -> bool:
    if pd.isna(x):
        return False
    if isinstance(x, bool):
        return bool(x)
    s = str(x).strip().lower()
    return s in ("1", "true", "t", "yes", "y", "ok")


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    m = n // 2
    if n % 2 == 1:
        return float(s[m])
    return float((s[m - 1] + s[m]) / 2.0)


def _mean_abs_diff(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    diffs = [abs(vals[i] - vals[i - 1]) for i in range(1, len(vals))]
    return float(sum(diffs) / len(diffs)) if diffs else None


def _fmt_last(role: str, ok: bool, lat: float | None, jit: float | None, loss: float | None, err: str | None) -> str:
    status = "ok" if ok else "bad"
    lat_s = "-" if lat is None else f"{lat:.2f}ms"
    jit_s = "-" if jit is None else f"{jit:.2f}ms"
    loss_s = "-" if loss is None else f"{loss:.2f}%"
    if err:
        return f"{role}: {status} lat={lat_s} jit={jit_s} loss={loss_s} err={err}"
    return f"{role}: {status} lat={lat_s} jit={jit_s} loss={loss_s}"


def main() -> None:
    if not IN_PATH.exists():
        print("wifi_diag: input missing. Run:")
        print("  python3 -m src.cli wifi-diag --rounds 5")
        return

    df = pd.read_csv(IN_PATH)

    ts_col = _pick_col(df, ["timestamp", "time", "ts"])
    round_col = _pick_col(df, ["round_id", "round", "run_id"])
    role_col = _pick_col(df, ["service_name", "role", "target", "name"])
    probe_col = _pick_col(df, ["probe_type", "probe"])
    success_col = _pick_col(df, ["success", "ok"])
    lat_col = _pick_col(df, ["latency_ms", "latency_avg_ms", "ping_ms", "latency"])

    if round_col is None or role_col is None:
        print("wifi_diag: unsupported schema (missing round_id or service_name/role).")
        print(f"Columns: {list(df.columns)}")
        return

    if probe_col is not None:
        df = df[df[probe_col].astype(str).str.lower().eq("ping")].copy()

    # Timestamp parse 
    if ts_col is not None:
        df[ts_col] = ensure_tz(df[ts_col])

    df[role_col] = df[role_col].astype(str).str.strip().str.lower()
    df[role_col] = df[role_col].replace(
        {
            "google": "external",
            "www.google.com": "external",
            "external_host": "external",
        }
    )

    # Success
    if success_col is not None:
        df["_success"] = df[success_col].apply(_to_bool)
    else:
        # fallback: success if latency exists
        df["_success"] = True

    if lat_col is not None:
        df["_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    else:
        df["_lat"] = pd.Series([None] * len(df))

    err_col = _pick_col(df, ["error_kind", "error", "error_message"])
    if err_col is not None:
        df["_err"] = df[err_col].fillna("").astype(str)
    else:
        df["_err"] = ""

    # Drop rows that are totally empty
    df = df.dropna(subset=[round_col, role_col], how="any").copy()
    if df.empty:
        print("wifi_diag: empty after cleaning.")
        return

    windows = []
    for (rid, role), g in df.groupby([round_col, role_col], dropna=True):
        total = int(len(g))
        ok_n = int(g["_success"].sum())
        ok_rate = ok_n / total if total else 0.0
        loss_pct = (1.0 - ok_rate) * 100.0

        lat_vals = [float(x) for x in g.loc[g["_success"], "_lat"].dropna().tolist()]
        lat_med = _median(lat_vals)
        jit = _mean_abs_diff(lat_vals)

        # mark "ok" strictly: for small sample sizes, require no failures
        ok = ok_rate >= 0.8

        # pick representative timestamp if present
        ts_val = None
        if ts_col is not None:
            ts_series = g[ts_col].dropna()
            if not ts_series.empty:
                ts_val = ts_series.iloc[-1]

        # representative error
        err = ""
        if ok_n < total:
            # if any failed, try show last non-empty err
            nonempty = g["_err"][g["_err"].astype(str).str.len() > 0]
            if not nonempty.empty:
                err = str(nonempty.iloc[-1])
            else:
                err = "ping_failed"

        windows.append(
            {
                "round_id": rid,
                "timestamp": str(ts_val) if ts_val is not None else "",
                "role": role,
                "n": total,
                "ok_rate": round(ok_rate, 4),
                "packet_loss_pct": round(loss_pct, 2),
                "latency_ms_median": round(lat_med, 2) if lat_med is not None else "",
                "jitter_ms": round(jit, 2) if jit is not None else "",
                "ok": ok,
                "err": err,
            }
        )

    if not windows:
        print("wifi_diag: no usable rows (nothing to aggregate).")
        return

    win_df = pd.DataFrame(windows).sort_values(["round_id", "role"])
    win_df.to_csv(OUT_WINDOWS, index=False)

    # Last window per role
    def _last_for(role: str) -> dict | None:
        sub = win_df[win_df["role"] == role]
        if sub.empty:
            return None
        return sub.iloc[-1].to_dict()

    gw = _last_for("gateway")
    ex = _last_for("external")

    # If gateway is missing OR gateway window exists but it is "missing gateway", we must be inconclusive.
    if gw is None or (str(gw.get("err") or "").strip() == "config_missing_gateway"):
        diagnosis = "inconclusive_missing_gateway"
    else:
        gw_ok = bool(gw.get("ok"))
        ex_ok = bool(ex.get("ok")) if ex is not None else True  # external missing -> treat as unknown but not auto-fail

        if (not gw_ok) and ex_ok:
            diagnosis = "likely_wifi_local_problem"
        elif gw_ok and (ex is not None) and (not ex_ok):
            diagnosis = "likely_isp_upstream_problem"
        elif gw_ok and (ex is None or ex_ok):
            diagnosis = "no_problem_detected"
        else:
            diagnosis = "inconclusive"


    gateway_last = "missing"
    external_last = "missing"

    if gw is not None:
        gateway_last = _fmt_last(
            "gateway",
            bool(gw.get("ok")),
            float(gw["latency_ms_median"]) if str(gw.get("latency_ms_median")).strip() != "" else None,
            float(gw["jitter_ms"]) if str(gw.get("jitter_ms")).strip() != "" else None,
            float(gw["packet_loss_pct"]) if str(gw.get("packet_loss_pct")).strip() != "" else None,
            str(gw.get("err") or "").strip() or None,
        )

    if ex is not None:
        external_last = _fmt_last(
            "external",
            bool(ex.get("ok")),
            float(ex["latency_ms_median"]) if str(ex.get("latency_ms_median")).strip() != "" else None,
            float(ex["jitter_ms"]) if str(ex.get("jitter_ms")).strip() != "" else None,
            float(ex["packet_loss_pct"]) if str(ex.get("packet_loss_pct")).strip() != "" else None,
            str(ex.get("err") or "").strip() or None,
        )

    summary = {
        "diagnosis": diagnosis,
        "gateway_last": gateway_last,
        "google_last": external_last,  # keep field name compatible with your report.py
        "total_windows": int(win_df["round_id"].nunique()),
    }
    pd.DataFrame([summary]).to_csv(OUT_SUMMARY, index=False)

    print(f"Saved: {OUT_SUMMARY}")
    print(f"Saved: {OUT_WINDOWS}")
    print("wifi_diag summary:", summary)


if __name__ == "__main__":
    main()
