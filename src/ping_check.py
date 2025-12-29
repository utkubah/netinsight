# src/ping_check.py
"""
Very simple ping probe using system 'ping'.

This file keeps the behaviour minimal:
 - call system ping once per sample
 - measure elapsed time for successful calls
 - simple error_kind values: ok, ping_timeout, ping_dns_failure, ping_tool_missing, ping_unknown_error
"""
import subprocess
import time
import platform


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
    latencies = []
    errors = []

    system = platform.system().lower()

    for _ in range(count):
        if system.startswith("windows"):
            # -n 1: one echo request, -w timeout in ms
            t_ms = max(1, int(timeout * 1000))
            cmd = ["ping", "-n", "1", "-w", str(t_ms), target]
        else:
            # -c 1: one request, -W timeout in seconds (integer)
            t_secs = max(1, int(timeout)) if timeout > 0 else 1
            cmd = ["ping", "-c", "1", "-W", str(t_secs), target]

        start = time.time()
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError:
            # ping binary not present
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
                "error": "ping tool missing",
                "error_kind": "ping_tool_missing",
            }
        elapsed_ms = (time.time() - start) * 1000.0
        stdout = (p.stdout or "").lower()
        stderr = (p.stderr or "").lower()

        if p.returncode == 0 and "destination host unreachable" not in stdout and "destination host unreachable" not in stderr:
            latencies.append(elapsed_ms)
        else:
            # try to classify
            if "name or service not known" in stderr or "temporary failure in name resolution" in stderr:
                errors.append("dns failure")
            elif "timed out" in stdout or "timeout" in stderr or p.returncode != 0:
                errors.append("timeout")
            else:
                errors.append(stderr.strip() or stdout.strip() or f"ping exited {p.returncode}")

    sent = count
    received = len(latencies)
    loss = 100.0 * (sent - received) / sent if sent > 0 else 100.0

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
            "packet_loss_pct": loss,
            "error": None,
            "error_kind": "ok",
        }

    # no latencies -> pick first error
    err = errors[0].lower() if errors else "all pings failed"
    if "dns" in err:
        ek = "ping_dns_failure"
    elif "timeout" in err:
        ek = "ping_timeout"
    elif "permission" in err:
        ek = "ping_no_permission"
    elif "ping tool missing" in err or "not found" in err:
        ek = "ping_tool_missing"
    else:
        ek = "ping_unknown_error"

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
        "error": errors[0] if errors else None,
        "error_kind": ek,
    }
