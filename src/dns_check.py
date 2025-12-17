# netinsight/dns_test.py
import socket
from datetime import datetime


def run_dns(hostname, timeout=2.0):
    """
    Resolve a hostname and measure how long it takes.

    Returns a dict with:
      - hostname
      - ok (bool)
      - ip (resolved IP or None)
      - dns_ms (resolution time in ms)
      - error (str or None)
    """
    start = datetime.now()
    ip = None
    ok = False
    error = None

    # Easiest version: just call gethostbyname with a timeout.
    # We set a global timeout and reset it afterwards to keep it simple.
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        try:
            ip = socket.gethostbyname(hostname)
            ok = True
        except Exception as e:
            error = str(e)
    finally:
        socket.setdefaulttimeout(old_timeout)

    elapsed_ms = (datetime.now() - start).total_seconds() * 1000.0

    return {
        "hostname": hostname,
        "ok": ok,
        "ip": ip,
        "dns_ms": elapsed_ms,
        "error": error,
    }
