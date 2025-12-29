# src/ping_check.py
"""
Simple, robust ping probe.

Design choices (minimal but reliable):
- First attempt a DNS resolution using socket.gethostbyname(). If that fails,
  we immediately return a DNS-specific error (no reliance on ping's stderr).
- Then run the platform-appropriate system `ping` single-packet commands `count`
  times and measure elapsed time for successful attempts.
- Success is determined by `returncode == 0` (no fragile stdout text parsing).
- If no successful samples, we decide whether it is a timeout (elapsed >= timeout
  threshold) or a generic error. We return canonical error_kind constants.

This keeps behavior deterministic across locales and avoids brittle text parsing.
"""

import platform
import subprocess
import time
import socket

from error_kinds import (
    PING_OK,
    PING_TIMEOUT,
    PING_DNS_FAILURE,
    PING_TOOL_MISSING,
    PING_UNKNOWN_ERROR,
    PING_UNREACHABLE,
    PING_NO_PERMISSION,
)

def _stats_from_latencies(latencies):
    if not latencies:
        return None, None, None, None, None
    lat_min = min(latencies)
    lat_max = max(latencies)
    lat_avg = sum(latencies) / len(latencies)
    sorted_l = sorted(latencies)
    p95 = sorted_l[int(0.95 * (len(sorted_l) - 1))]
    if len(latencies) >= 2:
        diffs = [abs(latencies[i] - latencies[i - 1]) for i in range(1, len(latencies))]
        jitter = sum(diffs) / len(diffs)
    else:
        jitter = None
    return lat_min, lat_max, lat_avg, p95, jitter


def run_ping(target, count=5, timeout=1.0):
    """
    Run 'count' single-packet pings to target with per-ping timeout (seconds).
    Returns a dict with metrics and canonical error_kind.
    """
    # 1) Pre-resolve hostname so we reliably detect DNS failures
    try:
        socket.gethostbyname(target)
    except Exception as e:
        return {
            "target": target,
            "sent": count,
            "received": 0,
            "latency_min_ms": None,
            "latency_max_ms": None,
            "latency_avg_ms": None,
            "latency_p95_ms": None,
            "jitter_ms": None,
            "latencies_ms": [],
            "packet_loss_pct": 100.0,
            "error": str(e),
            "error_kind": PING_DNS_FAILURE,
        }

    system = platform.system().lower()
    latencies = []
    errors = []

    for _ in range(count):
        if system.startswith("windows"):
            t_ms = max(1, int(timeout * 1000))
            cmd = ["ping", "-n", "1", "-w", str(t_ms), target]
        else:
            # many Unix `ping` implementations expect integer seconds for -W
            t_secs = max(1, int(timeout)) if timeout > 0 else 1
            cmd = ["ping", "-c", "1", "-W", str(t_secs), target]

        start = time.time()
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError:
            return {
                "target": target,
                "sent": count,
                "received": 0,
                "latency_min_ms": None,
                "latency_max_ms": None,
                "latency_avg_ms": None,
                "latency_p95_ms": None,
                "jitter_ms": None,
                "latencies_ms": [],
                "packet_loss_pct": 100.0,
                "error": "system ping tool not found",
                "error_kind": PING_TOOL_MISSING,
            }
        except PermissionError as e:
            # rare, but indicate permission issue
            return {
                "target": target,
                "sent": count,
                "received": 0,
                "latency_min_ms": None,
                "latency_max_ms": None,
                "latency_avg_ms": None,
                "latency_p95_ms": None,
                "jitter_ms": None,
                "latencies_ms": [],
                "packet_loss_pct": 100.0,
                "error": str(e),
                "error_kind": PING_NO_PERMISSION,
            }

        elapsed_ms = (time.time() - start) * 1000.0

        # success if returncode == 0 (reliable across OSes)
        if p.returncode == 0:
            latencies.append(elapsed_ms)
        else:
            # store stderr/stdout for debugging but avoid parsing localized messages
            out = (p.stdout or "").strip()
            err = (p.stderr or "").strip()
            errors.append(err or out or f"ping exited {p.returncode}")

    sent = count
    received = len(latencies)
    packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0

    if latencies:
        mn, mx, avg, p95, jitter = _stats_from_latencies(latencies)
        return {
            "target": target,
            "sent": sent,
            "received": received,
            "latency_min_ms": mn,
            "latency_max_ms": mx,
            "latency_avg_ms": avg,
            "latency_p95_ms": p95,
            "jitter_ms": jitter,
            "latencies_ms": latencies,
            "packet_loss_pct": packet_loss_pct,
            "error": None,
            "error_kind": PING_OK,
        }

    # no successful samples: decide on a conservative error classification
    first_err = errors[0] if errors else "all pings failed"
    # If elapsed time suggests timeout, prefer a timeout label
    # (We cannot rely on parsing localized text.)
    if abs(elapsed_ms - (timeout * 1000.0)) <= 50 or elapsed_ms >= (timeout * 1000.0):
        ek = PING_TIMEOUT
    else:
        ek = PING_UNKNOWN_ERROR

    return {
        "target": target,
        "sent": sent,
        "received": 0,
        "latency_min_ms": None,
        "latency_max_ms": None,
        "latency_avg_ms": None,
        "latency_p95_ms": None,
        "jitter_ms": None,
        "latencies_ms": [],
        "packet_loss_pct": 100.0,
        "error": first_err,
        "error_kind": ek,
    }
