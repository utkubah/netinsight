# src/dns_check.py
"""
DNS probe for NetInsight.

Prefer dnspython for timeouts and precise exceptions. If dnspython is not
installed, fall back to socket.gethostbyname() but note that the per-call
timeout cannot be enforced in that fallback on some platforms.
"""

import time
import socket
import warnings
import logging

logger = logging.getLogger(__name__)

try:
    import dns.resolver
    HAS_DNSPY = True
except Exception:
    HAS_DNSPY = False

from error_kinds import DNS_OK, DNS_TEMP_FAILURE, DNS_NXDOMAIN, DNS_TIMEOUT, DNS_OTHER


def run_dns(hostname, timeout=2.0):
    start = time.monotonic()
    ip = None
    ok = False
    error = None
    error_kind = DNS_OK

    if HAS_DNSPY:
        resolver = dns.resolver.Resolver()
        try:
            ans = resolver.resolve(hostname, "A", lifetime=timeout)
            ip = ans[0].to_text()
            ok = True
            error_kind = DNS_OK
        except dns.resolver.NXDOMAIN as e:
            error = str(e)
            ok = False
            error_kind = DNS_NXDOMAIN
        except dns.resolver.Timeout as e:
            error = str(e)
            ok = False
            error_kind = DNS_TIMEOUT
        except dns.resolver.NoNameservers as e:
            error = str(e)
            ok = False
            error_kind = DNS_TEMP_FAILURE
        except Exception as e:
            error = str(e)
            ok = False
            error_kind = DNS_OTHER
    else:
        # Fallback: socket.gethostbyname (no per-call timeout control).
        # Emit a runtime warning so maintainers know the fallback caveat.
        warnings.warn(
            "dnspython not installed: run_dns() is using socket.gethostbyname() fallback "
            "which may ignore per-call timeouts on some platforms.",
            RuntimeWarning,
        )
        logger.debug("dnspython not available, using socket.gethostbyname fallback for DNS")
        try:
            ip = socket.gethostbyname(hostname)
            ok = True
            error_kind = DNS_OK
        except socket.gaierror as e:
            error = str(e)
            ok = False
            msg = error.lower()
            if "temporary failure in name resolution" in msg:
                error_kind = DNS_TEMP_FAILURE
            elif "name or service not known" in msg or "not known" in msg:
                error_kind = DNS_NXDOMAIN
            else:
                error_kind = DNS_OTHER
        except Exception as e:
            error = str(e)
            ok = False
            error_kind = DNS_OTHER

    dns_ms = (time.monotonic() - start) * 1000.0
    return {
        "hostname": hostname,
        "ok": ok,
        "ip": ip,
        "dns_ms": dns_ms,
        "error": error,
        "error_kind": error_kind,
    }
