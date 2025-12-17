# netinsight/http_test.py
from datetime import datetime

import requests


def run_http(url, timeout=3.0):
    """
    Perform a simple HTTP GET to the given URL and measure how long it takes.

    Returns a dict with:
      - url
      - ok (bool)
      - status_code (int or None)
      - http_ms (request time in ms)
      - error (str or None)
    """
    start = datetime.now()
    status_code = None
    ok = False
    error = None

    try:
        resp = requests.get(url, timeout=timeout)
        status_code = resp.status_code
        ok = True
    except Exception as e:
        error = str(e)

    elapsed_ms = (datetime.now() - start).total_seconds() * 1000.0

    return {
        "url": url,
        "ok": ok,
        "status_code": status_code,
        "http_ms": elapsed_ms,
        "error": error,
    }
