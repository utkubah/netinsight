# src/net_utils.py
"""
Simple, robust default gateway detection (no walrus operator).

Order:
 1) NETINSIGHT_GATEWAY_IP env var
 2) If WSL: prefer 127.0.1.1 then 127.0.0.1 when present
 3) /proc/net/route (kernel default route)
 4) `ip route get 1.1.1.1` -> take 'via <ip>' if present
 5) `ip route show default` -> take 'default via <ip>'
 6) `route -n` fallback
 7) None if nothing found

This is simple and deterministic, designed to be easy to debug on WSL.
"""
import os
import platform
import socket
import struct
import subprocess
import logging

LOG = logging.getLogger("netinsight.net_utils")


def _is_wsl():
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r", encoding="utf-8") as f:
                v = f.read().lower()
            if "microsoft" in v or "wsl" in v:
                return True
        if os.path.exists("/proc/sys/kernel/osrelease"):
            with open("/proc/sys/kernel/osrelease", "r", encoding="utf-8") as f:
                v = f.read().lower()
            if "microsoft" in v or "wsl" in v:
                return True
    except Exception:
        pass
    return False


def _loopback_candidate_present(addr):
    """Return True if addr appears in /etc/hosts or on loopback interface."""
    try:
        # /etc/hosts
        if os.path.exists("/etc/hosts"):
            with open("/etc/hosts", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if addr in line:
                        return True
        # ip addr show lo
        try:
            out = subprocess.check_output(["ip", "addr", "show", "lo"], stderr=subprocess.STDOUT, text=True)
            if addr in out:
                return True
        except Exception:
            # ip might not be available; ignore
            pass
    except Exception:
        pass
    return False


def _parse_proc_net_route():
    """
    Parse /proc/net/route and return gateway IP (string) or None.
    Kernel's default route (Destination 00000000) contains gateway in hex.
    """
    path = "/proc/net/route"
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            dest_hex = parts[1]
            gw_hex = parts[2]
            if dest_hex != "00000000":
                continue
            try:
                gw_ip = socket.inet_ntoa(struct.pack("<L", int(gw_hex, 16)))
                if gw_ip and gw_ip != "0.0.0.0":
                    return gw_ip
            except Exception:
                continue
    except Exception:
        LOG.debug("Error reading /proc/net/route", exc_info=True)
    return None


def _parse_ip_route_get_via():
    """
    Run `ip route get 1.1.1.1` and return the 'via' IP if present, else None.
    Example output:
      "1.1.1.1 via 192.168.240.1 dev eth0 src 192.168.246.72 uid 1000"
    """
    try:
        out = subprocess.check_output(["ip", "route", "get", "1.1.1.1"], stderr=subprocess.STDOUT, text=True)
    except Exception:
        return None
    for line in out.splitlines():
        line = line.strip()
        if " via " in line:
            parts = line.split()
            # find token after 'via'
            try:
                idx = parts.index("via")
                candidate = parts[idx + 1]
                if candidate.count(".") == 3 and candidate != "0.0.0.0":
                    return candidate
            except Exception:
                continue
    return None


def _parse_ip_route_default():
    """Return gateway from 'ip route show default' or None."""
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], stderr=subprocess.STDOUT, text=True)
    except Exception:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("default") and " via " in line:
            parts = line.split()
            try:
                idx = parts.index("via")
                candidate = parts[idx + 1]
                if candidate.count(".") == 3 and candidate != "0.0.0.0":
                    return candidate
            except Exception:
                continue
    return None


def _parse_route_n():
    """Fallback parse of 'route -n' output; return gateway or None."""
    try:
        out = subprocess.check_output(["route", "-n"], stderr=subprocess.STDOUT, text=True)
    except Exception:
        return None
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Kernel") or line.startswith("Destination"):
            continue
        cols = line.split()
        if len(cols) >= 2:
            dest = cols[0]
            gw = cols[1]
            flags = cols[3] if len(cols) > 3 else ""
            if dest == "0.0.0.0" or "UG" in flags:
                if gw.count(".") == 3 and gw != "0.0.0.0":
                    return gw
    return None


def get_default_gateway_ip():
    """
    Return the default gateway IP or None.
    Simple, deterministic logic suitable for WSL: prefer kernel default,
    but in WSL prefer loopback candidates if present.
    """
    # 1) Env override
    env = os.environ.get("NETINSIGHT_GATEWAY_IP")
    if env:
        LOG.debug("Using NETINSIGHT_GATEWAY_IP=%s", env)
        return env.strip()

    # 2) WSL loopback preference
    try:
        if _is_wsl():
            for cand in ("127.0.1.1", "127.0.0.1"):
                if _loopback_candidate_present(cand):
                    LOG.debug("WSL detected - using loopback candidate: %s", cand)
                    return cand
    except Exception:
        LOG.debug("WSL detection failed", exc_info=True)

    # 3) /proc/net/route (kernel default route) - authoritative when present
    try:
        gw = _parse_proc_net_route()
        if gw:
            LOG.debug("Kernel default gateway (from /proc/net/route): %s", gw)
            return gw
    except Exception:
        LOG.debug("Reading /proc/net/route failed", exc_info=True)

    # 4) ip route get via
    gw = _parse_ip_route_get_via()
    if gw:
        LOG.debug("'ip route get' via candidate: %s", gw)
        return gw

    # 5) ip route show default
    gw = _parse_ip_route_default()
    if gw:
        LOG.debug("'ip route show default' candidate: %s", gw)
        return gw

    # 6) route -n fallback
    gw = _parse_route_n()
    if gw:
        LOG.debug("'route -n' candidate: %s", gw)
        return gw

    # 7) not found
    LOG.debug("No default gateway detected")
    return None
