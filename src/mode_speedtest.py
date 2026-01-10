# src/mode_speedtest.py
"""
Speedtest mode for NetInsight.

Uses speedtest-cli, might encounter errors because of the library

Runs one speedtest (ping + download/upload Mbps) and appends a row to:
  data/netinsight_speedtest.csv

This keeps speedtest usable in CLI + analyze pipeline.
"""

import csv
import logging
import os
from datetime import datetime, timezone
import speedtest

from .logging_setup import setup_logging

LOG = logging.getLogger("netinsight.speedtest")

MODE_NAME = "speedtest"
LOG_PATH = os.path.join("data", "netinsight_speedtest.csv")

CSV_HEADERS = [
    "timestamp",
    "mode",
    "ping_ms",
    "download_mbps",
    "upload_mbps",
    "server_name",
    "server_country",
    "server_sponsor",
    "server_id",
    "server_host",
    "error",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rotate_if_header_mismatch(path: str, expected_header: list[str]) -> None:
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            first = f.readline().strip()
    except Exception:
        return

    if not first:
        return

    existing = [h.strip() for h in first.split(",")]
    if existing == expected_header:
        return

    # rotate
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rotated = path.replace(".csv", f"_{ts}.csv")
    os.rename(path, rotated)
    LOG.warning("Rotated %s -> %s (header mismatch)", path, rotated)


def _append_row(path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _rotate_if_header_mismatch(path, CSV_HEADERS)

    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            w.writeheader()
        w.writerow(row)


def run_speedtest(log_path: str = LOG_PATH):
    """
    Returns dict with ping/download/upload, or None on failure.
    Always writes a row to CSV (with error filled if failed).
    """
    setup_logging()

    row = {
        "timestamp": _utc_now_iso(),
        "mode": MODE_NAME,
        "ping_ms": None,
        "download_mbps": None,
        "upload_mbps": None,
        "server_name": "",
        "server_country": "",
        "server_sponsor": "",
        "server_id": "",
        "server_host": "",
        "error": "",
    }


    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        dl_bps = st.download()
        ul_bps = st.upload()
        res = st.results.dict()

        server = res.get("server") or {}
        ping = res.get("ping")

        row["ping_ms"] = ping
        row["download_mbps"] = dl_bps / 1_000_000.0
        row["upload_mbps"] = ul_bps / 1_000_000.0
        row["server_name"] = str(server.get("name", "") or "")
        row["server_country"] = str(server.get("country", "") or "")
        row["server_sponsor"] = str(server.get("sponsor", "") or "")
        row["server_id"] = str(server.get("id", "") or "")
        row["server_host"] = str(server.get("host", "") or "")

        _append_row(log_path, row)

        LOG.info(
            "speedtest ok: ping=%.1fms dl=%.2fMbps ul=%.2fMbps server=%s/%s",
            float(row["ping_ms"]) if row["ping_ms"] is not None else -1.0,
            float(row["download_mbps"]) if row["download_mbps"] is not None else -1.0,
            float(row["upload_mbps"]) if row["upload_mbps"] is not None else -1.0,
            row["server_name"],
            row["server_country"],
        )
        return {
            "ping_ms": row["ping_ms"],
            "download_mbps": row["download_mbps"],
            "upload_mbps": row["upload_mbps"],
            "server": server,
        }

    except Exception as e:
        msg = f"speedtest failed: {e}"
        row["error"] = msg
        _append_row(log_path, row)
        LOG.error(msg)
        return None


def main():
    run_speedtest()


if __name__ == "__main__":
    main()
