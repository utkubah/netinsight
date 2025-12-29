# src/http_check.py
"""
HTTP probe for NetInsight.

Performs a simple GET request with requests and classifies errors.
Returns a dict with keys:
  url, ok, status_code, status_class, http_ms, bytes, redirects, error, error_kind
"""

import time
import requests
from requests import exceptions as req_exc


def run_http(url, timeout=3.0):
    start = time.monotonic()
    status_code = None
    status_class = None
    http_ms = None
    bytes_downloaded = None
    redirects = None
    ok = False
    error = None
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
            ok = True
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
        msg = (error or "").lower()
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
