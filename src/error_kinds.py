# src/error_kinds.py
"""
Canonical error kind constants for NetInsight.
"""

# Generic/Config
CONFIG_MISSING_GATEWAY = "config_missing_gateway"
CONFIG_MISSING_HOSTNAME = "config_missing_hostname"
CONFIG_MISSING_URL = "config_missing_url"

# Ping
PING_OK = "ok"
PING_TIMEOUT = "ping_timeout"
PING_NO_REPLY = "ping_no_reply"
PING_TOOL_MISSING = "ping_tool_missing"
PING_PERMISSION_DENIED = "ping_permission_denied"
PING_EXCEPTION = "ping_exception"
PING_FAILED = "ping_failed"
PING_UNKNOWN_HOST = "ping_unknown_host"

# DNS
DNS_OK = "ok"
DNS_GAIERROR = "dns_gaierror"
DNS_TIMEOUT = "dns_timeout"
DNS_EXCEPTION = "dns_exception"

# HTTP
HTTP_OK = "ok"
HTTP_NON_OK_STATUS = "http_non_ok_status"
HTTP_TIMEOUT = "http_timeout"
HTTP_SSL = "http_ssl_error"
HTTP_CONN_ERROR = "http_connection_error"
HTTP_REQUEST_EXCEPTION = "http_request_exception"
HTTP_EXCEPTION = "http_exception"
