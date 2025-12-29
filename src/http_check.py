# src/http_check.py
"""
HTTP probe for NetInsight.
"""

import time
import logging
import requests
from requests import exceptions as req_exc

logger = logging.getLogger(__name__)

from error_kinds import (
    HTTP_OK,
    HTTP_4XX,
    HTTP_5XX,
    HTTP_TIMEOUT,
    HTTP_SSL,
    HTTP_CONN_RESET,
    HTTP_DNS_ERROR,
    HTTP_CONN_ERROR,
    HTTP_OTHER,
    HTTP_OTHER_STATUS,
)


def run_http(url, timeout=3.0):
    start = time.monotonic()
    status_code = None
    status_class = None
    http_ms = None
    bytes_downloaded = None
    redirects = None
    ok = False
    error = None
    error_kind = HTTP_OK

    try:
        resp = requests.get(url, timeout=timeout)
        http_ms = (time.monotonic() - start) * 1000.0
        status_code = resp.status_code
        bytes_downloaded = len(resp.content) if resp.content is not None else None
        redirects = len(resp.history) if hasattr(resp, "history") else None

        if 200 <= status_code < 300:
            status_class = "2xx"
            ok = True
            error_kind = HTTP_OK
        elif 300 <= status_code < 400:
            status_class = "3xx"
            ok = True
            error_kind = HTTP_OK
        elif 400 <= status_code < 500:
            status_class = "4xx"
            ok = False
            error_kind = HTTP_4XX
        elif 500 <= status_code < 600:
            status_class = "5xx"
            ok = False
            error_kind = HTTP_5XX
        else:
            status_class = "other"
            ok = False
            error_kind = HTTP_OTHER_STATUS

    except req_exc.Timeout as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = HTTP_TIMEOUT
    except req_exc.SSLError as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = HTTP_SSL
    except req_exc.ConnectionError as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        msg = (error or "").lower()
        if "connection reset by peer" in msg:
            error_kind = HTTP_CONN_RESET
        elif "failed to resolve" in msg or "name or service not known" in msg or "temporary failure in name resolution" in msg:
            error_kind = HTTP_DNS_ERROR
        else:
            error_kind = HTTP_CONN_ERROR
    except req_exc.RequestException as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = HTTP_OTHER
    except Exception as e:
        http_ms = (time.monotonic() - start) * 1000.0
        ok = False
        error = str(e)
        error_kind = HTTP_OTHER

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
