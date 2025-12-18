# NetInsight

NetInsight is a small Python tool to monitor and analyze internet connection quality
in Bocconi dorms. It periodically runs:

- Ping tests to measure latency and packet loss
- DNS lookup tests
- HTTP GET requests to a stable endpoint

All results are timestamped and logged. From this data we compute:

- Average latency and packet loss
- Downtime periods
- Time-of-day patterns for instability

Planned extras: highlighting good/bad hours, detecting latency spikes,
CSV export, and a simple UI for visualization.



### TODO / Future Modes

### TODO / Future Modes

Introduce multiple **diagnostic modes** on top of the current baseline logger to make NetInsight feel more like a network “lab” than a simple ping script. Planned modes include: 

(1) a **Service Health & Blocked-Site mode** that focuses on a small set of services (e.g. Discord, YouTube, Bocconi, GitHub) and aggressively probes them to answer “is this service actually down globally, or just blocked/broken on my network?”, combining status codes, latency and `error_kind` to distinguish true outages from DNS blocking, connection resets or TLS issues. 

(2) A **Wi-Fi vs ISP diagnosis mode**, which pings the local gateway and a stable external baseline in high-frequency bursts, logging jitter and packet loss separately for `role=gateway` and `role=external` to infer whether problems come from dorm Wi-Fi congestion or from the wider ISP path. 

(3) A **Speedtest mode**, run on demand, that logs latency, jitter and approximate download throughput to a dedicated CSV, providing a simple “overall connection quality” snapshot. 

(4) A **24/7 Pattern / Time-of-Day mode**, which runs continuously and aggregates metrics per hour and per service (e.g. median latency, jitter, failure rate, quality scores), so we can build heatmaps of “good vs bad hours” in the dorm and quantify how performance changes over the day. 

(5) An **Incident Capture mode**, where the user can trigger a short high-frequency burst when they feel lag (gaming, Zoom, etc.), tagging all measurements with an `incident_id` and optional note; this creates focused “lag snapshots” that can later be compared to normal periods. 

(6) Scenario-specific **Profile modes** (e.g. “Gaming”, “Video Calls”, “Streaming”) that reuse the same probes but summarize them into per-scenario quality scores using different weights and thresholds, so NetInsight can answer questions like “is this dorm Wi-Fi good enough for competitive gaming at 9pm?” rather than just raw latency numbers.

