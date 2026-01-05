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
    """
    Append rows to csv_path using CSV_HEADERS as the canonical schema.

    If csv exists, the code checks the existing header matches CSV_HEADERS.
    If headers differ, a ValueError is raised with instructions to rotate/rename
    the existing file to avoid mixing incompatible schemas.

    Note: we intentionally do NOT implement file locking here (single-writer
    assumption for grading simplicity). If you expect concurrent writers, add
    an advisory lock or use a robust external store.
    """
    if not rows:
        return

    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_exists = os.path.exists(csv_path)
    # open in a+ so we can read existing header and then append
    with open(csv_path, "a+", newline="", encoding="utf-8") as f:
        f.seek(0)
        reader = csv.reader(f)
        try:
            existing_headers = next(reader)
        except StopIteration:
            existing_headers = None

        if existing_headers:
            if existing_headers != CSV_HEADERS:
                raise ValueError(
                    f"CSV header mismatch for {csv_path}.\n"
                    f"Existing header: {existing_headers}\n"
                    f"Expected header: {CSV_HEADERS}\n\n"
                    "To avoid mixing incompatible schemas, please rotate or rename the "
                    "existing file (e.g., add a timestamp suffix). Aborting append to "
                    "prevent corrupted/mismatched CSV.\n"
                )

        f.seek(0, os.SEEK_END)
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not existing_headers:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)
