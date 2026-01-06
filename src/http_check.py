# src/http_check.py
"""
Simple HTTP probe using requests.
"""
import time
import requests

from .error_kinds import (
    HTTP_OK,
    HTTP_NON_OK_STATUS,
    HTTP_TIMEOUT,
    HTTP_SSL,
    HTTP_CONN_ERROR,
    HTTP_REQUEST_EXCEPTION,
    HTTP_EXCEPTION,
)


def run_http(url, timeout=3.0):
    start = time.monotonic()
    ok = False
    status_code = None
    status_class = None
    bytes_downloaded = None
    redirects = 0
    error = None
    error_kind = HTTP_OK

    try:
        resp = requests.get(url, timeout=timeout)
        status_code = resp.status_code
        status_class = f"{status_code // 100}xx"
        bytes_downloaded = len(resp.content or b"")
        redirects = len(resp.history) if hasattr(resp, "history") else 0
        ok = (200 <= status_code < 400)
        if not ok:
            error_kind = HTTP_NON_OK_STATUS
            error = f"HTTP {status_code}"
    except requests.exceptions.Timeout:
        error_kind = HTTP_TIMEOUT
        error = "HTTP timeout"
    except requests.exceptions.SSLError:
        error_kind = HTTP_SSL
        error = "SSL error"
    except requests.exceptions.ConnectionError as e:
        error_kind = HTTP_CONN_ERROR
        error = str(e)
    except requests.exceptions.RequestException as e:
        error_kind = HTTP_REQUEST_EXCEPTION
        error = str(e)
    except Exception as e:
        error_kind = HTTP_EXCEPTION
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
