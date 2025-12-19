# src/targets_config.py
"""
Service/target configuration for NetInsight.

We keep it simple:
- One list: SERVICES
- For each service:
    - name      : short identifier (used in logs)
    - hostname  : used for ping + DNS
    - url       : used for HTTP GET
    - tags      : simple labels (for later analysis)
    - ping      : { "enabled": bool, "count": int, "timeout": float }
    - dns       : { "enabled": bool, "timeout": float }
    - http      : { "enabled": bool, "timeout": float }

No functions here – just data. main.py decides how to use it.
"""

SERVICES = [
    # ---------------------------------------------------------------------
    # Local / infrastructure / baselines
    # ---------------------------------------------------------------------
    {
        "name": "gateway",
        "hostname": "127.0.1.1",           # ok make sure this value is selected automatically
        "url": "http://127.0.1.1/",
        "tags": ["gateway", "wifi_path", "baseline"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns":  {"enabled": False, "timeout": 1.0},   # IP, so DNS is pointless
        "http": {"enabled": True, "timeout": 2.0},
    },
    {
        "name": "google",
        "hostname": "www.google.com",
        "url": "https://www.google.com/generate_204",
        "tags": ["baseline", "public_web"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 3.0},
    },
    {
        "name": "cloudflare",
        "hostname": "1.1.1.1",
        "url": "https://1.1.1.1/",
        "tags": ["baseline", "public_dns"],
        "ping": {"enabled": True, "count": 5, "timeout": 1.0},
        "dns":  {"enabled": False, "timeout": 2.0},   # IP, DNS lookup not useful
        "http": {"enabled": True, "timeout": 3.0},
    },

    # ---------------------------------------------------------------------
    # Bocconi / university
    # ---------------------------------------------------------------------
    {
        "name": "bocconi_www",
        "hostname": "www.unibocconi.it",
        "url": "https://www.unibocconi.it/en/",
        "tags": ["bocconi", "university"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # ---------------------------------------------------------------------
    # Video calls – Zoom, Teams, Meet
    # ---------------------------------------------------------------------
    {
        "name": "zoom",
        "hostname": "zoom.us",
        "url": "https://zoom.us/",
        "tags": ["video_call"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "teams",
        "hostname": "teams.microsoft.com",
        "url": "https://teams.microsoft.com/",
        "tags": ["video_call"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "meet",
        "hostname": "meet.google.com",
        "url": "https://meet.google.com/",
        "tags": ["video_call"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # ---------------------------------------------------------------------
    # Streaming / media
    # ---------------------------------------------------------------------
    {
        "name": "youtube",
        "hostname": "www.youtube.com",
        "url": "https://www.youtube.com/",
        "tags": ["streaming", "video"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "netflix",
        "hostname": "www.netflix.com",
        "url": "https://www.netflix.com/",
        "tags": ["streaming", "video"],
        "ping": {"enabled": False, "count": 3, "timeout": 1.5}, #does not allow it
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "spotify",
        "hostname": "open.spotify.com",
        "url": "https://open.spotify.com/",
        "tags": ["streaming", "audio"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # ---------------------------------------------------------------------
    # Dev / productivity
    # ---------------------------------------------------------------------
    {
        "name": "github",
        "hostname": "github.com",
        "url": "https://github.com/",
        "tags": ["dev"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },
    {
        "name": "stack_overflow",
        "hostname": "stackoverflow.com",
        "url": "https://stackoverflow.com/",
        "tags": ["dev"],
        "ping": {"enabled": True, "count": 3, "timeout": 1.5},
        "dns":  {"enabled": True, "timeout": 2.0},
        "http": {"enabled": True, "timeout": 4.0},
    },

    # ---------------------------------------------------------------------
    # Social / flaky / region-sensitive / firewall tests
    # ---------------------------------------------------------------------
    {
        "name": "x_com",
        "hostname": "x.com",
        "url": "https://x.com/",
        "tags": ["social", "flaky_candidate"],
        "ping": {"enabled": True, "count": 3, "timeout": 2.0},
        "dns":  {"enabled": True, "timeout": 2.5},
        "http": {"enabled": True, "timeout": 5.0},
    },
    {
        "name": "discord", #interesting case
        "hostname": "discord.com",
        "url": "https://discord.com/",
        "tags": ["social", "region_sensitive", "firewall_test"],
        "ping": {"enabled": True, "count": 3, "timeout": 2.0},
        "dns":  {"enabled": True, "timeout": 2.5},
        "http": {"enabled": True, "timeout": 5.0},
    },
    {
        "name": "instagram",
        "hostname": "www.instagram.com",
        "url": "https://www.instagram.com/",
        "tags": ["social"],
        "ping": {"enabled": True, "count": 3, "timeout": 2.0},
        "dns":  {"enabled": True, "timeout": 2.5},
        "http": {"enabled": True, "timeout": 5.0},
    },
    {
        "name": "tiktok",
        "hostname": "www.tiktok.com",
        "url": "https://www.tiktok.com/",
        "tags": ["social", "region_sensitive"],
        "ping": {"enabled": True, "count": 3, "timeout": 2.0},
        "dns":  {"enabled": True, "timeout": 2.5},
        "http": {"enabled": True, "timeout": 5.0},
    },
]
