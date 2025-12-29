# src/ping_check.py
"""
Ping probe for NetInsight.

Behavior:
 - Prefer ping3 if installed (gives fractional timeouts).
 - Otherwise try the system `ping` command.
 - If both methods fail due to permission issues (raw sockets not allowed /
   ping binary lacking privileges), fall back to a simple TCP connect probe
   (unprivileged) that measures connection time to a common port (80 or 443).
 - The TCP fallback is an approximation of reachability/latency and helps
   diagnosis when ICMP is not available.

Return dict fields:
  target, sent, received, latency_min_ms, latency_max_ms, latency_avg_ms,
  latency_p95_ms, jitter_ms, latencies_ms, packet_loss_pct, error, error_kind
"""

import time
import subprocess
import platform
import socket

# Try to import ping3 (optional)
try:
    import ping3
    HAS_PING3 = True
except Exception:
    HAS_PING3 = False


def _compute_stats(latencies):
    if not latencies:
        return None, None, None, None, None
    latency_min = min(latencies)
    latency_max = max(latencies)
    latency_avg = sum(latencies) / len(latencies)
    sorted_lats = sorted(latencies)
    idx = int(0.95 * (len(sorted_lats) - 1))
    latency_p95 = sorted_lats[idx]
    if len(latencies) >= 2:
        diffs = [abs(latencies[i] - latencies[i - 1]) for i in range(1, len(latencies))]
        jitter = sum(diffs) / len(diffs)
    else:
        jitter = None
    return latency_min, latency_max, latency_avg, latency_p95, jitter


def _tcp_probe_once(host, port, timeout):
    """Attempt a single TCP connect to host:port, return elapsed ms or None."""
    start = time.monotonic()
    s = None
    try:
        s = socket.create_connection((host, port), timeout)
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return elapsed_ms
    except socket.gaierror:
        # DNS failure
        return "dns_error"
    except Exception:
        return None
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


def _tcp_fallback(host, count, timeout):
    """Try a few TCP ports to approximate latency. Returns list of latencies (ms)."""
    latencies = []
    ports = [80, 443]
    for _ in range(count):
        got = False
        for p in ports:
            val = _tcp_probe_once(host, p, timeout)
            if val == "dns_error":
                # DNS resolution failed for TCP probe as well
                return [], "tcp_dns_failure"
            if isinstance(val, (int, float)):
                latencies.append(val)
                got = True
                break
        if not got:
            # no successful TCP connect this round; append nothing
            pass
    return latencies, None


def run_ping(target, count=5, timeout=1.0):
    """
    Run `count` ping attempts to target with `timeout` seconds per attempt.
    Returns the result dictionary.
    """
    latencies = []
    errors = []
    permission_denied = False

    # 1) Try ping3
    if HAS_PING3:
        for _ in range(count):
            try:
                r = ping3.ping(target, timeout=timeout)
            except Exception as e:
                msg = str(e).lower()
                errors.append(str(e))
                if "permission" in msg or "operation not permitted" in msg or "errno 1" in msg:
                    permission_denied = True
                    break
                # other exceptions -> treat as generic error and continue
                continue

            if r is None:
                errors.append("no response")
            elif r is False:
                # ping3 returns False for name resolution failure
                errors.append("dns failure")
            else:
                latencies.append(r * 1000.0)

        # if ping3 was used and produced latencies, proceed to stats
        if latencies:
            latency_min, latency_max, latency_avg, latency_p95, jitter = _compute_stats(latencies)
            sent = count
            received = len(latencies)
            packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0
            return {
                "target": target,
                "sent": sent,
                "received": received,
                "latency_min_ms": latency_min,
                "latency_max_ms": latency_max,
                "latency_avg_ms": latency_avg,
                "latency_p95_ms": latency_p95,
                "jitter_ms": jitter,
                "latencies_ms": latencies,
                "packet_loss_pct": packet_loss_pct,
                "error": None,
                "error_kind": "ok",
            }

        # if we hit a permission denied error while using ping3, try fallback
        if permission_denied:
            errors.append("permission denied (ping3)")
    # 2) Try system ping
    system = platform.system().lower()
    for _ in range(count):
        if system.startswith("windows"):
            timeout_ms = max(1, int(timeout * 1000))
            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), target]
        else:
            w = max(1, int(timeout)) if timeout > 0 else 1
            cmd = ["ping", "-c", "1", "-W", str(w), target]

        start = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except Exception as e:
            msg = str(e).lower()
            errors.append(str(e))
            if "permission" in msg or "operation not permitted" in msg:
                permission_denied = True
                break
            continue

        elapsed_ms = (time.monotonic() - start) * 1000.0
        stdout = (completed.stdout or "").lower()
        stderr = (completed.stderr or "").lower()

        if completed.returncode == 0 and "destination host unreachable" not in stdout and "destination host unreachable" not in stderr:
            latencies.append(elapsed_ms)
        else:
            if "name or service not known" in stderr or "temporary failure in name resolution" in stderr:
                errors.append("dns failure")
            elif "network is unreachable" in stderr:
                errors.append("network unreachable")
            elif "permission denied" in stderr or "operation not permitted" in stderr:
                errors.append("permission denied")
                permission_denied = True
                break
            else:
                errors.append(stderr.strip() or f"ping exited with code {completed.returncode}")

    # If we have latencies from system ping, use them
    if latencies:
        latency_min, latency_max, latency_avg, latency_p95, jitter = _compute_stats(latencies)
        sent = count
        received = len(latencies)
        packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0
        return {
            "target": target,
            "sent": sent,
            "received": received,
            "latency_min_ms": latency_min,
            "latency_max_ms": latency_max,
            "latency_avg_ms": latency_avg,
            "latency_p95_ms": latency_p95,
            "jitter_ms": jitter,
            "latencies_ms": latencies,
            "packet_loss_pct": packet_loss_pct,
            "error": None,
            "error_kind": "ok",
        }

    # If permission denied (either ping3 or system ping), try TCP fallback
    if permission_denied:
        lat_list, tcp_err = _tcp_fallback(target, count, timeout)
        if tcp_err == "tcp_dns_failure":
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
                "error": "DNS failure (tcp fallback)",
                "error_kind": "ping_dns_failure",
            }
        if lat_list:
            latency_min, latency_max, latency_avg, latency_p95, jitter = _compute_stats(lat_list)
            sent = count
            received = len(lat_list)
            packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0
            return {
                "target": target,
                "sent": sent,
                "received": received,
                "latency_min_ms": latency_min,
                "latency_max_ms": latency_max,
                "latency_avg_ms": latency_avg,
                "latency_p95_ms": latency_p95,
                "jitter_ms": jitter,
                "latencies_ms": lat_list,
                "packet_loss_pct": packet_loss_pct,
                "error": None,
                "error_kind": "ok",  # we succeeded using TCP fallback
            }
        # tcp fallback gave no samples
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
            "error": "permission denied for ICMP and tcp fallback failed",
            "error_kind": "ping_no_permission",
        }

    # No latencies and no explicit permission denied => analyze errors
    # Pick the first error message and classify
    if errors:
        err = errors[0].lower()
        error_text = errors[0]
        if "dns" in err:
            error_kind = "ping_dns_failure"
        elif "network unreachable" in err:
            error_kind = "ping_unreachable"
        elif "no such file or directory" in err or "command not found" in err:
            error_kind = "ping_tool_missing"
        elif "timed out" in err or "timeout" in err or "no response" in err:
            error_kind = "ping_timeout"
        else:
            error_kind = "ping_unknown_error"
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
            "error": error_text,
            "error_kind": error_kind,
        }

    # Fallback final: generic unknown error
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
        "error": "all pings failed",
        "error_kind": "ping_unknown_error",
    }
