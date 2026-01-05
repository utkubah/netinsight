# src/dns_check.py
"""
Simple DNS probe using socket.gethostbyname and a short timeout.

"""

import socket
import time


def run_dns(hostname, timeout=2.0):
    start = time.monotonic()
    ip = None
    ok = False
    error = None
    error_kind = "ok"

    # socket.gethostbyname doesn't accept a timeout param directly on all platforms.
    # We use setdefaulttimeout briefly to approximate a per-call timeout.
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        ip = socket.gethostbyname(hostname)
        ok = True
    except socket.gaierror as e:
        error = str(e)
        error_kind = "dns_gaierror"
    except socket.timeout:
        error = "DNS timeout"
        error_kind = "dns_timeout"
    except Exception as e:
        error = str(e)
        error_kind = "dns_exception"
    finally:
        socket.setdefaulttimeout(old)

    dns_ms = (time.monotonic() - start) * 1000.0
    return {
        "hostname": hostname,
        "ok": ok,
        "ip": ip,
        "dns_ms": dns_ms,
        "error_kind": error_kind,
        "error": error,
    }
