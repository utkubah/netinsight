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
