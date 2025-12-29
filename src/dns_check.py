# src/dns_check.py
"""
DNS probe for NetInsight.

If dnspython (dns.resolver) is available, use it so we have a per-call timeout
(lifetime). Otherwise fall back to socket.gethostbyname() which uses the system
resolver and may block according to OS settings.
"""

import time
import socket

try:
    import dns.resolver
    HAS_DNSPY = True
except Exception:
    HAS_DNSPY = False


def run_dns(hostname, timeout=2.0):
    """
    Resolve hostname and return a dict:
      hostname, ok (bool), ip (or None), dns_ms (float), error, error_kind
    """
    start = time.monotonic()
    ip = None
    ok = False
    error = None
    error_kind = "ok"

    if HAS_DNSPY:
        resolver = dns.resolver.Resolver()
        try:
            ans = resolver.resolve(hostname, "A", lifetime=timeout)
            ip = ans[0].to_text()
            ok = True
        except dns.resolver.NXDOMAIN as e:
            error = str(e)
            ok = False
            error_kind = "dns_nxdomain"
        except dns.resolver.Timeout as e:
            error = str(e)
            ok = False
            error_kind = "dns_timeout"
        except dns.resolver.NoNameservers as e:
            error = str(e)
            ok = False
            error_kind = "dns_temp_failure"
        except Exception as e:
            error = str(e)
            ok = False
            error_kind = "dns_other_error"
    else:
        # fallback: socket.gethostbyname (no per-call timeout control)
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
