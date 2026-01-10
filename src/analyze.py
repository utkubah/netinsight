import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Pipelines
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

REQUIRES = {
    # baseline chain
    "quality_score.py": ["data/netinsight_log.csv"],
    "detect_bad_intervals.py": ["data/quality_rows.csv"],
    "detect_downtime.py": ["data/quality_rows.csv"],
    "analyze_time_of_day.py": ["data/quality_rows.csv"],
    # other modes
    "analyze_wifi_diag.py": ["data/netinsight_wifi_diag.csv"],
    "analyze_service_health.py": ["data/netinsight_service_health.csv"],
    "analyze_speedtest.py": ["data/netinsight_speedtest.csv"],
}

def _missing_inputs(script_name: str) -> list[str]:
    reqs = REQUIRES.get(script_name, [])
    missing = []
    for rel in reqs:
        p = REPO_ROOT / rel
        if not p.exists():
            missing.append(rel)
    return missing

def _run_script(script_name: str) -> bool:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"[analyze] skip (missing script): scripts/{script_name}")
        return False

    missing = _missing_inputs(script_name)
    if missing:
        print(f"[analyze] skip (missing input): {script_name} needs {missing}")
        return False

    print(f"[analyze] run: scripts/{script_name}")
    try:
        subprocess.run([sys.executable, str(script_path)], cwd=str(REPO_ROOT), check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[analyze] FAIL: {script_name} (exit={e.returncode})")
        return False

def _run_pipeline(pipeline: list[str]) -> None:
    """
    Run scripts in order, but don't spam FAIL when prerequisites are missing.
    Example: If quality_score doesn't run, downstream scripts will be skipped
    because quality_rows.csv won't exist.
    """
    for s in pipeline:
        _run_script(s)

def run(target: str) -> None:
    t = target.strip().lower()

    if t == "baseline":
        _run_pipeline(BASELINE_PIPELINE)
        return

    if t == "wifi-diag":
        _run_pipeline(WIFI_DIAG_PIPELINE)
        return

    if t == "service-health":
        _run_pipeline(SERVICE_HEALTH_PIPELINE)
        return

    if t == "speedtest":
        _run_pipeline(SPEEDTEST_PIPELINE)
        return

    if t == "all":
        run("baseline")
        run("wifi-diag")
        run("service-health")
        run("speedtest")
        return

    raise ValueError(f"Unknown analyze target: {target}")
