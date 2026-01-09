# src/analyze.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

BASELINE_PIPELINE = [
    "quality_score.py",
    "detect_bad_intervals.py",
    "detect_downtime.py",
    "analyze_time_of_day.py",
]

WIFI_DIAG_PIPELINE = [
    "analyze_wifi_diag.py",
]

SERVICE_HEALTH_PIPELINE = [
    "analyze_service_health.py",
]

SPEEDTEST_PIPELINE = [
    "analyze_speedtest.py",
]

def _run_script(script_name: str) -> bool:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"[analyze] skip (missing): scripts/{script_name}")
        return False

    print(f"[analyze] run: scripts/{script_name}")
    try:
        subprocess.run([sys.executable, str(script_path)], cwd=str(REPO_ROOT), check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[analyze] FAIL: {script_name} (exit={e.returncode})")
        return False

def run(target: str) -> None:
    t = target.strip().lower()

    if t == "baseline":
        for s in BASELINE_PIPELINE:
            _run_script(s)
        return

    if t == "wifi-diag":
        for s in WIFI_DIAG_PIPELINE:
            _run_script(s)
        return

    if t == "service-health":
        for s in SERVICE_HEALTH_PIPELINE:
            _run_script(s)
        return

    if t == "speedtest":
        for s in SPEEDTEST_PIPELINE:
            _run_script(s)
        return

    if t == "all":
        run("baseline")
        run("wifi-diag")
        run("service-health")
        run("speedtest")
        return

    raise ValueError(f"Unknown analyze target: {target}")
