# src/dns_check.py

import socket
import time
from typing import Any, Dict, Optional


def run_dns(hostname: str, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Resolve a hostname using socket.gethostbyname and measure resolution time.

    Returns a dict with:
      - hostname
      - ok          : bool
      - ip          : resolved IP string or None
      - dns_ms      : resolution time in ms
      - error       : error string on failure, else None
      - error_kind  : short classified error label, e.g. "ok", "dns_timeout",
                      "dns_nxdomain", "dns_temp_failure", "dns_other_error"
    """
    start = time.monotonic()
    ip: Optional[str] = None
    ok = False
    error: Optional[str] = None
    error_kind = "ok"

    try:
        # Note: socket.gethostbyname does not take a timeout directly;
        # timeout is controlled by system resolver settings. We accept
        # a timeout parameter for future use / symmetry with HTTP.
        ip = socket.gethostbyname(hostname)
        ok = True
    except socket.gaierror as e:
        error = str(e)
        ok = False
        msg = error.lower()
        if "temporary failure in name resolution" in msg:
            error_kind = "dns_temp_failure"
        elif "name or service not known" in msg or "not known" in msg:
            error_kind = "dns_nxdomain"
        else:
            error_kind = "dns_other_error"
    except socket.timeout:
        error = "DNS timeout"
        ok = False
        error_kind = "dns_timeout"
    except Exception as e:
        error = str(e)
        ok = False
        error_kind = "dns_other_error"

    dns_ms = (time.monotonic() - start) * 1000.0

    return {
        "hostname": hostname,
        "ok": ok,
        "ip": ip,
        "dns_ms": dns_ms,
        "error": error,
        "error_kind": error_kind,
    }
