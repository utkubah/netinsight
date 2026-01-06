# src/dns_check.py
"""
Simple DNS probe using socket.gethostbyname and a short timeout.
"""
import socket
import time

from .error_kinds import DNS_OK, DNS_GAIERROR, DNS_TIMEOUT, DNS_EXCEPTION


def run_dns(hostname, timeout=2.0):
    start = time.monotonic()
    ip = None
    ok = False
    error = None
    error_kind = DNS_OK

    # socket.gethostbyname doesn't accept a timeout param directly on all platforms.
    # We use setdefaulttimeout briefly to approximate a per-call timeout.
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        ip = socket.gethostbyname(hostname)
        ok = True
    except socket.gaierror as e:
        error = str(e)
        error_kind = DNS_GAIERROR
    except socket.timeout:
        error = "DNS timeout"
        error_kind = DNS_TIMEOUT
    except Exception as e:
        error = str(e)
        error_kind = DNS_EXCEPTION
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
