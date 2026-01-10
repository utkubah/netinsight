"""
Thin loader that exposes configuration from config/targets.json.

Exposes:
- GATEWAY_HOSTNAME
- WIFI_DIAG_EXTERNAL_HOST
- WIFI_DIAG_EXTERNAL_URL
- SERVICES (list)
"""

import os
import json

DEFAULT_CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config", "targets.json"))

_default = {
    "GATEWAY_HOSTNAME": None,
    "WIFI_DIAG_EXTERNAL_HOST": "www.google.com",
    "WIFI_DIAG_EXTERNAL_URL": "https://www.google.com/generate_204",
    "SERVICES": [
        {
            "name": "gateway",
            "hostname": "",
            "url": "",
            "tags": ["gateway", "wifi_path", "baseline"],
            "ping": {"enabled": True, "count": 5, "timeout": 1.0},
            "dns": {"enabled": False, "timeout": 1.0},
            "http": {"enabled": False, "timeout": 2.0},
        }
    ],
}


def _load_from_json(path=DEFAULT_CONFIG_PATH):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            gw = data.get("GATEWAY_HOSTNAME")
            wifi_host = data.get("WIFI_DIAG_EXTERNAL_HOST", _default["WIFI_DIAG_EXTERNAL_HOST"])
            wifi_url = data.get("WIFI_DIAG_EXTERNAL_URL", _default["WIFI_DIAG_EXTERNAL_URL"])
            services = data.get("SERVICES", _default["SERVICES"])
            return {
                "GATEWAY_HOSTNAME": gw,
                "WIFI_DIAG_EXTERNAL_HOST": wifi_host,
                "WIFI_DIAG_EXTERNAL_URL": wifi_url,
                "SERVICES": services,
            }
    except Exception:
        # fall back to defaults if JSON invalid
        pass
    return _default.copy()


_cfg = _load_from_json()

GATEWAY_HOSTNAME = _cfg["GATEWAY_HOSTNAME"]
WIFI_DIAG_EXTERNAL_HOST = _cfg["WIFI_DIAG_EXTERNAL_HOST"]
WIFI_DIAG_EXTERNAL_URL = _cfg["WIFI_DIAG_EXTERNAL_URL"]
SERVICES = _cfg["SERVICES"]
