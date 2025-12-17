# netinsight/ping_test.py
import subprocess
from datetime import datetime
from typing import Dict, Optional, List


def run_ping(target: str, count: int = 5, timeout: float = 1.0) -> Dict[str, Optional[float]]:
    """
    Run `ping` to the given target several times and measure latency in Python.

    For each of `count` attempts, we run `ping -c 1` and:
      - measure how long the command takes (as latency),
      - treat non-zero exit codes as packet loss.

    Returns a dict with:
      - target
      - sent, received
      - latency_min_ms, latency_max_ms, latency_avg_ms
      - packet_loss_pct
      - error (None or a short message if everything failed)
    """
    latencies_ms: List[float] = []
    errors: List[str] = []

    for i in range(count):
        # Build a 1-ping command. This is Linux/WSL style.
        cmd = [
            "ping",
            "-n",              # numeric output, no reverse DNS
            "-c", "1",         # send exactly 1 ICMP echo request
            "-W", str(int(timeout)),  # timeout in seconds
            target,
        ]

        start = datetime.now()
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,  # we don't need the text output
                stderr=subprocess.PIPE,
                text=True,
                check=False,                # don't raise on non-zero exit
            )
        except Exception as e:
            # Something went wrong just running the command
            errors.append(str(e))
            continue

        elapsed_ms = (datetime.now() - start).total_seconds() * 1000.0

        if completed.returncode == 0:
            # Ping succeeded → record latency
            latencies_ms.append(elapsed_ms)
        else:
            # Ping failed → treat as lost packet
            if completed.stderr:
                errors.append(completed.stderr.strip())
            else:
                errors.append(f"ping exited with code {completed.returncode}")

    sent = count
    received = len(latencies_ms)
    packet_loss_pct = 100.0 * (sent - received) / sent if sent > 0 else 100.0

    if latencies_ms:
        latency_min_ms = min(latencies_ms)
        latency_max_ms = max(latencies_ms)
        latency_avg_ms = sum(latencies_ms) / len(latencies_ms)
        error: Optional[str] = None
    else:
        latency_min_ms = latency_max_ms = latency_avg_ms = None
        # If all pings failed, keep one error message (if any)
        error = errors[0] if errors else "all pings failed"

    return {
        "target": target,
        "sent": sent,
        "received": received,
        "latency_min_ms": latency_min_ms,
        "latency_max_ms": latency_max_ms,
        "latency_avg_ms": latency_avg_ms,
        "packet_loss_pct": packet_loss_pct,
        "error": error,
    }
