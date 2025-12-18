# src/ping_check.py

import subprocess
import time
from typing import Dict, Optional, List, Any


def run_ping(target: str, count: int = 5, timeout: float = 1.0) -> Dict[str, Any]:
    """
    Run `ping` to the given target several times and measure latency in Python.

    For each of `count` attempts, we run a single-packet ping and:
      - measure how long the command takes (as latency),
      - treat non-zero exit codes as packet loss.

    Returns a dict with:
      - target
      - sent, received
      - latency_min_ms, latency_max_ms, latency_avg_ms
      - latency_p95_ms      (95th percentile latency, if we have samples)
      - jitter_ms           (mean abs diff between consecutive latencies)
      - latencies_ms        (list of individual successful latencies)
      - packet_loss_pct
      - error               (None or a short message if everything failed)
      - error_kind          (short classified error label, or "ok")
    """
    latencies_ms: List[float] = []
    errors: List[str] = []

    for _ in range(count):
        cmd = [
            "ping",
            "-n",              # numeric output, no reverse DNS
            "-c", "1",         # send exactly 1 ICMP echo request
            "-W", str(int(timeout)),  # timeout in seconds
            target,
        ]

        start = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except Exception as e:
            errors.append(str(e))
            continue

        elapsed_ms = (time.monotonic() - start) * 1000.0

        if completed.returncode == 0:
            latencies_ms.append(elapsed_ms)
        else:
            if completed.stderr:
                errors.append(completed.stderr.strip())
            else:
                errors.append(f"ping exited with code {completed.returncode}")

    sent = count
    received = len(latencies_ms)
    packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0

    if latencies_ms:
        latency_min_ms: Optional[float] = min(latencies_ms)
        latency_max_ms: Optional[float] = max(latencies_ms)
        latency_avg_ms: Optional[float] = sum(latencies_ms) / len(latencies_ms)

        # p95: sort and take the 95th percentile index
        sorted_lats = sorted(latencies_ms)
        idx = int(0.95 * (len(sorted_lats) - 1))
        latency_p95_ms: Optional[float] = sorted_lats[idx]

        # jitter: mean abs diff between consecutive samples
        if len(latencies_ms) >= 2:
            diffs = [
                abs(latencies_ms[i] - latencies_ms[i - 1])
                for i in range(1, len(latencies_ms))
            ]
            jitter_ms: Optional[float] = sum(diffs) / len(diffs)
        else:
            jitter_ms = None

        error: Optional[str] = None
        error_kind: str = "ok"
    else:
        latency_min_ms = latency_max_ms = latency_avg_ms = None
        latency_p95_ms = None
        jitter_ms = None

        if errors:
            error = errors[0]
            msg = error.lower()
            if "temporary failure in name resolution" in msg or "[errno -3]" in msg:
                error_kind = "ping_dns_failure"
            elif "network is unreachable" in msg:
                error_kind = "ping_unreachable"
            elif "no such file or directory" in msg and "ping" in msg:
                error_kind = "ping_tool_missing"
            elif "timed out" in msg:
                error_kind = "ping_timeout"
            else:
                error_kind = "ping_unknown_error"
        else:
            error = "all pings failed"
            error_kind = "ping_unknown_error"

    return {
        "target": target,
        "sent": sent,
        "received": received,
        "latency_min_ms": latency_min_ms,
        "latency_max_ms": latency_max_ms,
        "latency_avg_ms": latency_avg_ms,
        "latency_p95_ms": latency_p95_ms,
        "jitter_ms": jitter_ms,
        "latencies_ms": latencies_ms,
        "packet_loss_pct": packet_loss_pct,
        "error": error,
        "error_kind": error_kind,
    }
