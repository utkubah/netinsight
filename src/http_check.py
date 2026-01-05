# src/http_check.py
"""
Simple HTTP probe using requests.
"""

import time
import requests


def run_http(url, timeout=3.0):
    start = time.monotonic()
    ok = False
    status_code = None
    status_class = None
    bytes_downloaded = None
    redirects = 0
    error = None
    error_kind = "ok"

    try:
        resp = requests.get(url, timeout=timeout)
        status_code = resp.status_code
        status_class = f"{status_code // 100}xx"
        bytes_downloaded = len(resp.content or b"")
        redirects = len(resp.history) if hasattr(resp, "history") else 0
        ok = (200 <= status_code < 400)
        if not ok:
            error_kind = "http_non_ok_status"
            error = f"HTTP {status_code}"
    except requests.exceptions.Timeout:
        error_kind = "http_timeout"
        error = "HTTP timeout"
    except requests.exceptions.SSLError:
        error_kind = "http_ssl_error"
        error = "SSL error"
    except requests.exceptions.ConnectionError as e:
        error_kind = "http_connection_error"
        error = str(e)
    except requests.exceptions.RequestException as e:
        error_kind = "http_request_exception"
        error = str(e)
    except Exception as e:
        error_kind = "http_exception"
        error = str(e)

    http_ms = (time.monotonic() - start) * 1000.0

    return {
        "url": url,
        "ok": ok,
        "status_code": status_code,
        "status_class": status_class,
        "http_ms": http_ms,
        "bytes": bytes_downloaded,
        "redirects": redirects,
        "error_kind": error_kind,
        "error": error,
    }
