# src/error_kinds.py
"""
Canonical error_kind constants used across the project.

Purpose: Avoid brittle string literals scattered in the code and make
classifications consistent.
"""

# Ping error kinds
PING_OK = "ok"
PING_TIMEOUT = "ping_timeout"
PING_DNS_FAILURE = "ping_dns_failure"
PING_TOOL_MISSING = "ping_tool_missing"
PING_NO_PERMISSION = "ping_no_permission"
PING_UNREACHABLE = "ping_unreachable"
PING_UNKNOWN_ERROR = "ping_unknown_error"

# DNS error kinds
DNS_OK = "ok"
DNS_TEMP_FAILURE = "dns_temp_failure"
DNS_NXDOMAIN = "dns_nxdomain"
DNS_TIMEOUT = "dns_timeout"
DNS_OTHER = "dns_other_error"

# HTTP error kinds
HTTP_OK = "ok"
HTTP_4XX = "http_4xx"
HTTP_5XX = "http_5xx"
HTTP_TIMEOUT = "http_timeout"
HTTP_SSL = "http_ssl_error"
HTTP_CONN_RESET = "http_connection_reset"
HTTP_DNS_ERROR = "http_dns_error"
HTTP_CONN_ERROR = "http_connection_error"
HTTP_OTHER = "http_other_error"
HTTP_OTHER_STATUS = "http_other_status"
