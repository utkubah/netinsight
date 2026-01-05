# src/ping_check.py
"""
Uses the system 'ping' command. 
Returns a dict with keys:
  target, sent, received, packet_loss_pct, latencies_ms,
  latency_min_ms, latency_max_ms, latency_avg_ms, latency_p95_ms,
  jitter_ms, elapsed_ms, error_kind, error
"""

import platform
import re
import subprocess
import time

# simple regex to parse time=12.3 ms or time<1ms
_TIME_RE = re.compile(r"time[=<]\s*([0-9]+(?:\.[0-9]+)?)\s*ms", re.IGNORECASE)


def run_ping(target, count=3, timeout=1.0):
    sent = int(count)
    latencies = []
    error = None
    error_kind = "ok"

    system = platform.system().lower()

    # Build a simple ping command depending on OS
    if system.startswith("win"):
        cmd = ["ping", "-n", str(sent), "-w", str(int(timeout * 1000)), target]
        # allow extra time for subprocess timeout
        cmd_timeout = sent * (timeout + 1) + 3
    else:
        # macOS and Linux: use -c for count; let timeout be managed per-call where possible
        cmd = ["ping", "-c", str(sent), target]
        cmd_timeout = sent * (timeout + 1) + 3

    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=cmd_timeout)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # extract all time=xxx ms patterns
        matches = _TIME_RE.findall(out)
        for m in matches:
            try:
                latencies.append(float(m))
            except Exception:
                pass

        # detect permission issues (common strings)
        low = out.lower()
        if "permission denied" in low or "operation not permitted" in low:
            error_kind = "ping_permission_denied"
            error = "ICMP permission denied for this process."

        received = len(latencies)

        if received == 0 and error_kind == "ok":
            # no replies seen
            if proc.returncode != 0:
                # if returncode non-zero but some output exists, mark failed
                error_kind = "ping_failed"
                error = (proc.stderr or proc.stdout or f"ping exited {proc.returncode}").strip()
            else:
                error_kind = "ping_no_reply"
                error = "No ping replies received."

    except FileNotFoundError:
        error_kind = "ping_tool_missing"
        error = "System 'ping' command not found."
        received = 0
    except subprocess.TimeoutExpired:
        error_kind = "ping_timeout"
        error = "Ping command timed out."
        received = 0
    except Exception as e:
        error_kind = "ping_exception"
        error = str(e)
        received = 0

    elapsed_ms = (time.monotonic() - start) * 1000.0

    # compute basic stats
    if latencies:
        lat_sorted = sorted(latencies)
        latency_min = lat_sorted[0]
        latency_max = lat_sorted[-1]
        latency_avg = sum(lat_sorted) / len(lat_sorted)
        idx = int(0.95 * (len(lat_sorted) - 1))
        latency_p95 = lat_sorted[idx]
        # jitter: average absolute difference of consecutive samples (original order)
        diffs = []
        for i in range(1, len(latencies)):
            diffs.append(abs(latencies[i] - latencies[i - 1]))
        jitter = (sum(diffs) / len(diffs)) if diffs else 0.0
    else:
        latency_min = latency_max = latency_avg = latency_p95 = jitter = None

    received = len(latencies)
    packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0

    return {
        "target": target,
        "sent": sent,
        "received": received,
        "packet_loss_pct": packet_loss_pct,
        "latencies_ms": latencies,
        "latency_min_ms": latency_min,
        "latency_max_ms": latency_max,
        "latency_avg_ms": latency_avg,
        "latency_p95_ms": latency_p95,
        "jitter_ms": jitter,
        "elapsed_ms": elapsed_ms,
        "error_kind": error_kind,
        "error": error,
    }
