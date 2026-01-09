# src/report.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_DIR = Path("data")


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def _read_kv_csv(path: Path) -> Dict[str, str]:
    """
    Reads metric,value style csv into dict.
    """
    rows = _read_csv_rows(path)
    out: Dict[str, str] = {}
    for r in rows:
        k = (r.get("metric") or "").strip()
        v = (r.get("value") or "").strip()
        if k:
            out[k] = v
    return out


def _safe_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(str(s).strip())
    except Exception:
        return None


def _fmt_seconds(s: Optional[str]) -> str:
    """
    Pretty-print seconds -> "Xs (Y min, Z h)".
    If not parseable, returns the raw string.
    """
    v = _safe_float(s)
    if v is None:
        return str(s or "").strip()
    mins = v / 60.0
    hours = mins / 60.0
    return f"{v:.2f}s ({mins:.2f} min, {hours:.2f} h)"


def _pick_minmax(rows: List[Dict[str, str]], key: str) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """
    Returns (min_row, max_row) based on numeric key.
    """
    vals = []
    for r in rows:
        v = _safe_float(r.get(key))
        if v is not None:
            vals.append((v, r))
    if not vals:
        return None, None
    vals.sort(key=lambda x: x[0])
    return vals[0][1], vals[-1][1]


def _section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def report_baseline() -> None:
    _section("Baseline report")

    bad_intervals = _read_csv_rows(DATA_DIR / "bad_intervals.csv")
    hourly_stats = _read_csv_rows(DATA_DIR / "hourly_stats.csv")
    total_downtime = _read_csv_rows(DATA_DIR / "total_downtime.csv")

    if not bad_intervals and not hourly_stats and not total_downtime:
        print("No baseline analysis outputs found. Run:")
        print("  python3 -m src.cli analyze baseline")
        return

    # Hourly stats (best/worst)
    if hourly_stats:
        best_lat, worst_lat = _pick_minmax(hourly_stats, "avg_latency_ms")
        best_loss, worst_loss = _pick_minmax(hourly_stats, "packet_loss_pct")

        def _fmt_hour_row(r: Optional[Dict[str, str]]) -> str:
            if not r:
                return "-"
            return (
                f"hour={r.get('hour')} "
                f"latency={r.get('avg_latency_ms')}ms "
                f"loss={r.get('packet_loss_pct')}% "
                f"n={r.get('num_probes')}"
            )

        print("Hourly:")
        print(f"  Best latency : {_fmt_hour_row(best_lat)}")
        print(f"  Worst latency: {_fmt_hour_row(worst_lat)}")
        print(f"  Best loss    : {_fmt_hour_row(best_loss)}")
        print(f"  Worst loss   : {_fmt_hour_row(worst_loss)}")

    # Top bad intervals
    if bad_intervals:
        print("\nTop bad intervals (first 3):")
        for r in bad_intervals[:3]:
            print(
                f"  {r.get('start_time')} → {r.get('end_time')} "
                f"dur={r.get('duration_seconds')}s "
                f"severity={r.get('severity')} reason={r.get('reason')} diagnosis={r.get('diagnosis')}"
            )

    # Total downtime summary (if exists)
    if total_downtime:
        r0 = total_downtime[0]
        td = (
            r0.get("total_downtime_seconds")
            or r0.get("total_downtime_sec")
            or r0.get("total_downtime")
            or ""
        )
        td_str = _fmt_seconds(td)
        if td_str:
            print(f"\nTotal downtime summary: {td_str}")


def report_wifi_diag() -> None:
    _section("Wi-Fi diag report")

    summary_path = DATA_DIR / "wifi_diag_summary.csv"
    rows = _read_csv_rows(summary_path)

    if not rows:
        print("No wifi-diag analysis outputs found. Run:")
        print("  python3 -m src.cli analyze wifi-diag")
        return

    r0 = rows[0]
    print("Summary:")
    for k, v in r0.items():
        if v is None or str(v).strip() == "":
            continue
        print(f"  {k}: {v}")


def report_service_health() -> None:
    _section("Service health report")

    summary = _read_kv_csv(DATA_DIR / "service_health_summary.csv")
    dist = _read_csv_rows(DATA_DIR / "service_health_state_distribution.csv")
    recent = _read_csv_rows(DATA_DIR / "service_health_recent.csv")

    if not summary and not dist and not recent:
        print("No service-health analysis outputs found. Run:")
        print("  python3 -m src.cli analyze service-health")
        return

    if summary:
        print("Summary:")
        for k in ["rows_total", "domains_unique", "healthy_pct", "blockedish_pct"]:
            if k in summary:
                print(f"  {k}: {summary[k]}")

    if dist:
        print("\nState distribution:")
        for r in dist:
            state = r.get("service_state") or r.get("state") or r.get("metric") or ""
            pct = r.get("pct") or r.get("value") or r.get("count") or ""
            if state:
                print(f"  {state}: {pct}")

    if recent:
        print("\nRecent (last 5):")
        for r in recent[:5]:
            print(
                f"  {r.get('timestamp')} domain={r.get('service_name')} "
                f"state={r.get('service_state')} code={r.get('http_status_code')}"
            )


def report_speedtest() -> None:
    _section("Speedtest report")

    summary_rows = _read_csv_rows(DATA_DIR / "speedtest_summary.csv")
    hourly_rows = _read_csv_rows(DATA_DIR / "speedtest_hourly.csv")

    if not summary_rows and not hourly_rows:
        print("No speedtest analysis outputs found. Run:")
        print("  python3 -m src.cli speedtest")
        print("  python3 -m src.cli analyze speedtest")
        return

    if summary_rows:
        r = summary_rows[0]
        print("Summary:")
        for k in [
            "total_runs",
            "ok_runs",
            "error_runs",
            "ping_ms_avg",
            "download_mbps_avg",
            "upload_mbps_avg",
            "download_mbps_p10",
            "download_mbps_p90",
            "upload_mbps_p10",
            "upload_mbps_p90",
        ]:
            if k in r and str(r[k]).strip() != "":
                print(f"  {k}: {r[k]}")

    if hourly_rows:
        # _pick_minmax returns (min, max). For download Mbps:
        # best = max, worst = min
        worst_dl, best_dl = _pick_minmax(hourly_rows, "download_mbps_avg")
        if best_dl and worst_dl:
            print("\nHourly download:")
            print(f"  Best : hour={best_dl.get('hour')} dl={best_dl.get('download_mbps_avg')} Mbps (n={best_dl.get('n')})")
            print(f"  Worst: hour={worst_dl.get('hour')} dl={worst_dl.get('download_mbps_avg')} Mbps (n={worst_dl.get('n')})")


def run(target: str = "all") -> None:
    t = (target or "all").strip().lower()

    if t == "baseline":
        report_baseline()
        return
    if t == "wifi-diag":
        report_wifi_diag()
        return
    if t == "service-health":
        report_service_health()
        return
    if t == "speedtest":
        report_speedtest()
        return
    if t == "all":
        report_baseline()
        report_wifi_diag()
        report_service_health()
        report_speedtest()
        return

    raise ValueError(f"Unknown report target: {target}")
