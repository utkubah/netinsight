# src/http_check.py

import time
from typing import Any, Dict, Optional

import requests
from requests import exceptions as req_exc


def run_http(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """
    Perform a simple HTTP GET using requests.get and measure total time.

    Returns a dict with:
      - url
      - ok           : bool
      - status_code  : int or None
      - http_ms      : total request time in ms
      - error        : error string on failure, else None
      - error_kind   : short label, e.g. "ok", "http_4xx", "http_5xx",
                       "http_timeout", "http_connection_error",
                       "http_connection_reset", "http_ssl_error",
                       "http_dns_error", "http_other_error"
    """
    start = time.monotonic()
    status_code: Optional[int] = None
    http_ms: Optional[float] = None
    ok = False
    error: Optional[str] = None
    error_kind = "ok"

    try:
        resp = requests.get(url, timeout=timeout)
        http_ms = (time.monotonic() - start) * 1000.0
        status_code = resp.status_code

        if 200 <= status_code < 400:
            ok = True
            error_kind = "ok"
        elif 400 <= status_code < 500:
            ok = False
            error_kind = "http_4xx"
        elif 500 <= status_code < 600:
            ok = False
            error_kind = "http_5xx"
        else:
            ok = False
            error_kind = "http_other_status"

    except req_exc.Timeout as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = "http_timeout"
    except req_exc.SSLError as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = "http_ssl_error"
    except req_exc.ConnectionError as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        msg = error.lower()
        if "connection reset by peer" in msg:
            error_kind = "http_connection_reset"
        elif "failed to resolve" in msg or "name or service not known" in msg or "temporary failure in name resolution" in msg:
            error_kind = "http_dns_error"
        else:
            error_kind = "http_connection_error"
    except req_exc.RequestException as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = "http_other_error"
    except Exception as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = "http_other_error"

    return {
        "url": url,
        "ok": ok,
        "status_code": status_code,
        "http_ms": http_ms,
        "error": error,
        "error_kind": error_kind,
    }
