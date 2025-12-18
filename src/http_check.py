# src/http_check.py
"""
HTTP probe for NetInsight.

This module performs a simple HTTP(S) GET using `requests` and measures how
fast the request completes and how the server responds.

Metrics:
  - http_ms:
      Total time from before requests.get() to after we get a response or error.
      High http_ms with low ping can mean the server or path is slow.
  - status_code:
      HTTP status (e.g. 200, 301, 404, 503) or None on network failure.
  - status_class:
      Coarse class derived from status_code:
        * "2xx"   -> success
        * "3xx"   -> redirects
        * "4xx"   -> client errors (not found, forbidden, etc.)
        * "5xx"   -> server errors
        * "other" -> anything else (e.g. 1xx or weird status)
        * None    -> no HTTP response at all (DNS / connection error)
  - bytes:
      Size of the response body in bytes (approx). Gives a sense of how big
      the content is; useful later when reasoning about throughput.
  - redirects:
      Number of redirect hops followed by requests (len(resp.history)).
  - ok:
      True for 2xx/3xx, False otherwise.
  - error_kind:
      Classified network/transport failure when we don't get a clean response:
        * "http_timeout"
        * "http_ssl_error"
        * "http_connection_reset"
        * "http_connection_error"
        * "http_dns_error"
        * "http_4xx", "http_5xx", "http_other_status"
        * "http_other_error"
  - error:
      Raw exception string (if any), useful for debugging.

Together with ping/DNS, this lets us say things like:
  - "HTTP to Netflix is OK but ping is blocked (ICMP disabled)."
  - "Discord fails at DNS layer: http_dns_error despite healthy ping."
  - "Gateway is timing out on HTTP while Google is fast -> router not serving HTTP."
"""

import time
from typing import Any, Dict, Optional

import requests
from requests import exceptions as req_exc


def run_http(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """
    Perform a simple HTTP GET using requests.get and measure total time.

    Returns a dict with:
      - url: str
      - ok: bool
      - status_code: int | None
      - status_class: str | None
      - http_ms: float | None
      - bytes: int | None
      - redirects: int | None
      - error: str | None
      - error_kind: str
    """
    start = time.monotonic()
    status_code: Optional[int] = None
    status_class: Optional[str] = None
    http_ms: Optional[float] = None
    bytes_downloaded: Optional[int] = None
    redirects: Optional[int] = None
    ok = False
    error: Optional[str] = None
    error_kind = "ok"

    try:
        resp = requests.get(url, timeout=timeout)
        http_ms = (time.monotonic() - start) * 1000.0
        status_code = resp.status_code
        bytes_downloaded = len(resp.content)
        redirects = len(resp.history)

        if 200 <= status_code < 300:
            status_class = "2xx"
            ok = True
            error_kind = "ok"
        elif 300 <= status_code < 400:
            status_class = "3xx"
            ok = True  # redirects usually still mean "reachable"
            error_kind = "ok"
        elif 400 <= status_code < 500:
            status_class = "4xx"
            ok = False
            error_kind = "http_4xx"
        elif 500 <= status_code < 600:
            status_class = "5xx"
            ok = False
            error_kind = "http_5xx"
        else:
            status_class = "other"
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
        "status_class": status_class,
        "http_ms": http_ms,
        "bytes": bytes_downloaded,
        "redirects": redirects,
        "error": error,
        "error_kind": error_kind,
    }
