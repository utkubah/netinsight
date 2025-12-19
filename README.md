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


### Probes & Metrics

NetInsight currently runs three types of probes on each configured service:

- **Ping**
- **DNS**
- **HTTP(S) GET**

Each probe produces a small set of metrics that are logged to CSV (and later
aggregated/analyzed). The goal is that from these raw numbers we can build
sentences a human actually cares about, like *"Zoom should be fine right now"*
or *"Discord looks DNS-blocked on this network"*.

#### Ping metrics

For each target NetInsight sends multiple single-packet pings and measures
latency in Python:

- `latency_avg_ms`: average round-trip time.
- `latency_min_ms`, `latency_max_ms`: best and worst samples.
- `latency_p95_ms`: 95th percentile latency (how bad the spikes are).
- `jitter_ms`: mean absolute difference between consecutive samples.
- `packet_loss_pct`: % of lost packets.
- `error_kind`: high-level failure type if all packets fail
  (e.g. `ping_timeout`, `ping_unreachable`, `ping_dns_failure`).

Rules of thumb for interpretation:

- `latency_avg_ms < 40 ms`, `jitter_ms < 10 ms`, `packet_loss_pct < 1%`  
  → **great** for gaming and video calls.
- `latency_avg_ms 40–80 ms`, `jitter_ms < 20 ms`, `packet_loss_pct < 2%`  
  → **fine** for video calls / casual gaming.
- `jitter_ms > 30 ms` or `packet_loss_pct > 5%`  
  → real-time apps (Valorant, Zoom) will feel **choppy/unstable** even if avg latency looks OK.
- `error_kind = ping_timeout` or `ping_unreachable`  
  → host is not reachable at ICMP level (could be down, could be blocking ping).

Example outcomes that analysis code can build:

- *"Latency and jitter to Google are low and stable → good conditions for Zoom."*
- *"High jitter and ~10% packet loss to Discord suggest unstable Wi-Fi or congestion."*

#### DNS metrics

DNS probes use the system resolver via `socket.gethostbyname(hostname)`:

- `dns_ms`: time to resolve the hostname (ms).
- `ok`: whether resolution succeeded.
- `ip`: resolved IPv4 address on success.
- `error_kind`:
  - `dns_temp_failure` – temporary resolver failure (e.g. campus DNS issue).
  - `dns_nxdomain` – name does not exist / typo / possibly blocked.
  - `dns_timeout` – DNS request timed out.
  - `dns_other_error` – anything else.

Patterns that matter:

- Many services `ok` but one host shows frequent `dns_temp_failure` or `dns_nxdomain`  
  → that host might be **blocked or misconfigured**.
- High `dns_ms` (e.g. >200 ms) across the board while ping is fine  
  → **slow DNS** making the web feel sluggish.

Example outcomes:

- *"DNS resolution for Discord is intermittently failing while other sites are fine → likely DNS-based blocking or flaky resolver."*
- *"Bocconi's DNS is consistently fast (<50 ms) and reliable."*

#### HTTP metrics

HTTP probes perform a GET request with `requests`:

- `http_ms`: total time from before the request to response/exception.
- `status_code`: HTTP status (e.g. 200, 301, 404, 503) or `None` on network failure.
- `status_class`: derived from status code:
  - `"2xx"` – success,
  - `"3xx"` – redirect,
  - `"4xx"` – client error,
  - `"5xx"` – server error,
  - `"other"` – unusual statuses,
  - `None` – no HTTP response at all.
- `bytes`: size of the response body in bytes.
- `redirects`: number of redirects followed.
- `error_kind`: high-level failure info:
  - `http_timeout`, `http_ssl_error`, `http_connection_reset`, `http_connection_error`,
  - `http_dns_error`, `http_4xx`, `http_5xx`, `http_other_status`, `http_other_error`.

Useful patterns:

- `ping` OK, `dns` OK, but HTTP shows `http_5xx` for many services  
  → servers or upstream providers are having issues.
- `ping` OK, but HTTP shows `http_dns_error` to one domain  
  → DNS or censorship problem specific to that domain.
- `ping` and HTTP high latency to *many* targets at the same time  
  → ISP or Wi-Fi is congested / unstable.

Example outcomes:

- *"HTTP to Netflix is fast and returns 2xx → streaming service is reachable and responsive."*
- *"Discord HTTP requests fail with http_dns_error and ping occasionally sees ping_dns_failure → Discord likely blocked at DNS level on this network."*
- *"Gateway HTTP times out while Google and YouTube are fast → router is not serving HTTP but internet is otherwise healthy."*


### TODO / Future Modes

Introduce multiple **diagnostic modes** on top of the current baseline logger to make NetInsight feel more like a network “lab” than a simple ping script. Planned modes include: 

(1) a **Service Health & Blocked-Site mode** that focuses on a small set of services (e.g. Discord, YouTube, Bocconi, GitHub) and aggressively probes them to answer “is this service actually down globally, or just blocked/broken on my network?”, combining status codes, latency and `error_kind` to distinguish true outages from DNS blocking, connection resets or TLS issues. Main mode can advice user to activate 
this specific service health mode 

(2) A **Wi-Fi vs ISP diagnosis mode**, which pings the local gateway and a stable external baseline in high-frequency bursts, logging jitter and packet loss separately for `role=gateway` and `role=external` to infer whether problems come from dorm Wi-Fi congestion or from the wider ISP path. 

(3) A **Speedtest mode**, run on demand, that logs latency, jitter and approximate download throughput to a dedicated CSV, providing a simple “overall connection quality” snapshot. Possible userface(?)

(4) A **24/7 Pattern / Time-of-Day mode**, which runs continuously and aggregates metrics per hour and per service (e.g. median latency, jitter, failure rate, quality scores), so we can build heatmaps of “good vs bad hours” in the dorm and quantify how performance changes over the day. 

(5) An **Incident Capture mode**, where the user can trigger a short high-frequency burst when they feel lag (gaming, Zoom, etc.), tagging all measurements with an `incident_id` and optional note; this creates focused “lag snapshots” that can later be compared to normal periods. 

(6) Scenario-specific **Profile modes** (e.g. “Gaming”, “Video Calls”, “Streaming”) that reuse the same probes but summarize them into per-scenario quality scores using different weights and thresholds, so NetInsight can answer questions like “is this dorm Wi-Fi good enough for competitive gaming at 9pm?” rather than just raw latency numbers.



## Project Layout

- `src/main.py`  
  Baseline 24/7 logger. Every `INTERVAL_SECONDS`, runs ping + DNS + HTTP for
  all `SERVICES` from `targets_config.py` and appends to `data/netinsight_log.csv`
  with `mode=baseline`.

- `src/targets_config.py`  
  Definitions of monitored services (name, hostname, url, tags, per-probe
  settings like ping count / timeout).

- `src/ping_check.py`  
  ICMP ping probe using the system `ping` command, computing latency stats,
  jitter, packet loss, and `error_kind`.

- `src/dns_check.py`  
  DNS probe using `socket.gethostbyname`, measuring `dns_ms` and classifying
  failures (`dns_temp_failure`, `dns_nxdomain`, etc.).

- `src/http_check.py`  
  HTTP/HTTPS GET probe using `requests`, measuring `http_ms`, `status_code`,
  `status_class`, response size, redirects, and `error_kind`.

- `src/mode_wifi_diag.py`  
  Wi-Fi vs ISP diagnostic mode. Short, high-frequency ping burst to a Wi-Fi
  gateway and an external baseline, logged to `data/netinsight_wifi_diag.csv`
  with `mode=wifi_diag`.

- `src/mode_speedtest.py`  
  One-off speedtest mode using the `speedtest` module (speedtest-cli), logging
  throughput and ping to `data/netinsight_speedtest.csv` with `mode=speedtest`.

- `tests/`  
  Pytest tests for the probe functions and baseline `run_once()` smoke tests.

### Data files

- `data/netinsight_log.csv`  
  Baseline 24/7 measurements (ping/DNS/HTTP to all services).

- `data/netinsight_wifi_diag.csv`  
  Wi-Fi vs ISP diagnostic bursts (ping only, per role).

- `data/netinsight_speedtest.csv`  
  On-demand speedtest snapshots (ping + download/upload Mbps).
