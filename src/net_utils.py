import os
import platform
import socket
import struct
import subprocess


def get_default_gateway_ip():
    """
    Best-effort default gateway detection.
    - If NETINSIGHT_GATEWAY_IP is set, use it.
    - Linux: parse /proc/net/route
    - macOS: route -n get default
    - Windows: ipconfig parse
    Returns IP string or None.
    """
    env_ip = os.environ.get("NETINSIGHT_GATEWAY_IP")
    if env_ip:
        return env_ip.strip()

    system = platform.system().lower()

    if system == "linux":
        try:
            with open("/proc/net/route", "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                destination = parts[1]
                gateway_hex = parts[2]
                if destination != "00000000":
                    continue
                gw = socket.inet_ntoa(struct.pack("<L", int(gateway_hex, 16)))
                return gw
        except Exception:
            return None

    if system == "darwin":
        try:
            out = subprocess.check_output(["route", "-n", "get", "default"], stderr=subprocess.STDOUT, text=True)
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("gateway:"):
                    return line.split("gateway:")[-1].strip()
        except Exception:
            return None

    if system.startswith("win"):
        try:
            out = subprocess.check_output(["ipconfig"], stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore")
            # crude parse: first IPv4-looking token after "Default Gateway"
            for line in out.splitlines():
                if "Default Gateway" in line:
                    pieces = line.split(":")
                    if len(pieces) >= 2:
                        candidate = pieces[-1].strip()
                        if candidate.count(".") == 3:
                            return candidate
            return None
        except Exception:
            return None

    return None
