"""
Service/target configuration for NetInsight.

We keep it simple: just data.

Gateway is NOT hardcoded anymore:
- Set GATEWAY_HOSTNAME to None and we auto-detect it at runtime
- Or set env var NETINSIGHT_GATEWAY_IP="192.168.1.1"
"""

GATEWAY_HOSTNAME = None

WIFI_DIAG_EXTERNAL_HOST = "www.google.com"
WIFI_DIAG_EXTERNAL_URL = "https://www.google.com/generate_204"

SERVICES = [
    # Local / baseline
    {
        "name": "gateway",
        "hostname": GATEWAY_HOSTNAME,
        "url": "",
        "tags": ["gateway", "wifi_path", "baseline"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns": {"enabled": False, "timeout": 1.0},
        "http": {"enabled": False, "timeout": 2.0},
    },
    {
        "name": "google",
        "hostname": "www.google.com",
        "url": "https://www.google.com/generate_204",
        "tags": ["baseline", "public_web"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 3.0},
    },
    {
        "name": "cloudflare",
        "hostname": "1.1.1.1",
        "url": "https://1.1.1.1/",
        "tags": ["baseline", "public_dns"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns": {"enabled": False, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 3.0},
    },

    # Bocconi / university
    {
        "name": "bocconi_www",
        "hostname": "www.unibocconi.it",
        "url": "https://www.unibocconi.it/en/",
        "tags": ["bocconi", "university"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # Video calls
    {
        "name": "zoom",
        "hostname": "zoom.us",
        "url": "https://zoom.us/",
        "tags": ["video_call"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "teams",
        "hostname": "teams.microsoft.com",
        "url": "https://teams.microsoft.com/",
        "tags": ["video_call"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "meet",
        "hostname": "meet.google.com",
        "url": "https://meet.google.com/",
        "tags": ["video_call"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # Streaming / media
    {
        "name": "youtube",
        "hostname": "www.youtube.com",
        "url": "https://www.youtube.com/",
        "tags": ["streaming", "video"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "spotify",
        "hostname": "open.spotify.com",
        "url": "https://open.spotify.com/",
        "tags": ["streaming", "audio"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # Dev / productivity
    {
        "name": "github",
        "hostname": "github.com",
        "url": "https://github.com/",
        "tags": ["dev"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns": {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # Firewall-ish / region-sensitive examples
    {
        "name": "discord",
        "hostname": "discord.com",
        "url": "https://discord.com/",
        "tags": ["social", "region_sensitive", "firewall_test"],
        "ping": {"enabled": True, "count": 3, "timeout": 2.0},
        "dns": {"enabled": True, "timeout": 2.5},
        "http": {"enabled": True, "timeout": 5.0},
    },
]
