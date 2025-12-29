# src/targets_config.py
"""
Service/target configuration for NetInsight.

Keep it simple:
 - SERVICES is a list of dicts. Each dict can have:
   - name, hostname, url, tags
   - ping: {enabled, count, timeout}
   - dns:  {enabled, timeout}
   - http: {enabled, timeout}
"""

SERVICES = [
    # Local / infrastructure / baseline
    {
        "name": "gateway",
        "hostname": "127.0.1.1", #make this changable
        "url": "http://127.0.1.1/",
        "tags": ["gateway", "wifi_path", "baseline"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns": {"enabled": False, "timeout": 1.0},
        "http": {"enabled": True, "timeout": 2.0},
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

    # Social / firewall candidates
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
