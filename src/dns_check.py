# src/dns_check.py
"""
DNS probe for NetInsight.

This module uses the system resolver via `socket.gethostbyname(hostname)` and
measures how long it takes to resolve a hostname to an IPv4 address.

Metrics:
  - dns_ms:
      Time from before gethostbyname() to after it returns or raises.
      High DNS latency can make everything *feel* slow even if ping is fine.
  - ok:
      True if resolution succeeded, False otherwise.
  - ip:
      Resolved IPv4 address (string) on success, else None.
  - error_kind:
      Rough classification of failure type:
        * "ok"
        * "dns_temp_failure"  -> temporary resolver issue (e.g. campus DNS flaking)
        * "dns_nxdomain"      -> name does not exist / typo / blocked domain
        * "dns_timeout"       -> DNS request timed out
        * "dns_other_error"   -> anything else

These metrics are useful for sentences like:
  - "DNS for Discord is intermittently failing while everything else works"
  - "Bocconi's DNS resolution is consistently fast and reliable"
"""

import socket
import time
from typing import Any, Dict, Optional


def run_dns(hostname: str, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Resolve a hostname using socket.gethostbyname and measure resolution time.

    Note: socket.gethostbyname does not take a per-call timeout parameter;
    actual behaviour depends on the OS / resolver configuration. The `timeout`
    argument is accepted for symmetry and potential future use.

    Returns a dict with:
      - hostname: str
      - ok: bool
      - ip: str | None
      - dns_ms: float
      - error: str | None
      - error_kind: str
    """
    start = time.monotonic()
    ip: Optional[str] = None
    ok = False
    error: Optional[str] = None
    error_kind = "ok"

    try:
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
