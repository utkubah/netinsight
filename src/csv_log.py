import csv
import os
from datetime import datetime, timezone


CSV_HEADERS = [
    "timestamp",
    "mode",
    "round_id",
    "service_name",
    "hostname",
    "url",
    "tags",
    "probe_type",
    "success",
    "latency_ms",
    "latency_p95_ms",
    "jitter_ms",
    "packet_loss_pct",
    "status_code",
    "error_kind",
    "error_message",
    "details",  # JSON string (always JSON for consistency)
]


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_row(
    mode,
    round_id,
    service_name="",
    hostname="",
    url="",
    tags="",
    probe_type="",
    success="",
    latency_ms="",
    latency_p95_ms="",
    jitter_ms="",
    packet_loss_pct="",
    status_code="",
    error_kind="",
    error_message="",
    details="",
):
    row = {k: "" for k in CSV_HEADERS}
    row["timestamp"] = utc_now_iso()
    row["mode"] = mode
    row["round_id"] = round_id
    row["service_name"] = service_name
    row["hostname"] = hostname or ""
    row["url"] = url or ""
    row["tags"] = tags or ""
    row["probe_type"] = probe_type
    row["success"] = str(bool(success)) if success != "" else ""
    row["latency_ms"] = latency_ms if latency_ms is not None else ""
    row["latency_p95_ms"] = latency_p95_ms if latency_p95_ms is not None else ""
    row["jitter_ms"] = jitter_ms if jitter_ms is not None else ""
    row["packet_loss_pct"] = packet_loss_pct if packet_loss_pct is not None else ""
    row["status_code"] = status_code if status_code is not None else ""
    row["error_kind"] = error_kind or ""
    row["error_message"] = error_message or ""
    row["details"] = details or ""
    return row


def append_rows(csv_path, rows):
    if not rows:
        return

    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)
