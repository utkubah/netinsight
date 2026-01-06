# NetInsight

NetInsight is a small Python tool that monitors and analyzes internet connection
quality, with a focus on unstable student Wi-Fi (e.g. dorms).

It runs simple network probes at regular intervals and logs **structured data**
for later analysis — instead of just printing raw ping output.

---
# NetInsight

NetInsight is a small Python tool that logs network health in a structured way
(ping, DNS, HTTP, simple bandwidth) so you can later see **when** and **why**
your internet misbehaves (Wi-Fi, ISP, blocking, app/server issues).

## Modes

- **Baseline (24/7)**  
  - Script: `src/main.py`  
  - Log: `data/netinsight_log.csv`  
  - Every 30s, runs `ping`, `dns`, `http` for each service in `targets_config.py`.  
  - Metrics: latency, jitter, packet loss, dns_ms, http_ms, HTTP status, error_kind, and
    an approximate HTTP `throughput_mbps` per request (in the `details` field).

- **Wi-Fi diag**  
  - Script: `src/mode_wifi_diag.py`  
  - Log: `data/netinsight_wifi_diag.csv`  
  - Short burst of pings to:
    - `gateway` (local router)
    - `google` (external baseline)  
  - Used to separate “Wi-Fi/local problem” from “ISP/internet problem”.

- **Speedtest**  
  - Script: `src/mode_speedtest.py`  
  - No CSV (just prints for now).  
  - Runs a single speedtest (ping + download/upload Mbps) using `speedtest-cli`.

- **Service health / blocked sites**  
  - Script: `src/mode_service_health.py`  
  - Log: `data/netinsight_service_health.csv`  
  - For each service, runs ping/dns/http once (if enabled) and classifies it as:
    - `healthy`
    - `dns_failure`
    - `service_server_error` (5xx)
    - `client_or_access_error` (4xx)
    - `possible_blocked_or_restricted` (e.g. DNS + HTTP DNS errors, 403/451, etc.)
    - `connection_issue_or_blocked`
    - `connectivity_issue_or_firewall`
    - `no_probes_configured`
    - `inconclusive`

---

## Metrics (what we log and why)

### Ping metrics (from `ping_check.py`)

Per service (if ping enabled):

- `latency_ms`  
  Average round-trip time (ms).
- `latency_p95_ms`  
  95th percentile latency — tells you how bad the high-end spikes are.
- `jitter_ms`  
  Mean absolute difference between consecutive ping samples. High jitter is
  bad for gaming, calls, and anything real-time.
- `packet_loss_pct`  
  Percentage of pings that did not get a response. >1–2% is already noticeable
  for real-time apps.
- `error_kind`  
  Coarse error classification when ping fails, e.g.:
  - `ping_dns_failure`
  - `ping_unreachable`
  - `ping_timeout`
  - `ping_unknown_error`

**How to read:**

- Low latency + low jitter + ~0% loss → great for gaming / calls.
- Low latency but **high jitter** → OK for browsing, but choppy voice/video.
- High loss → serious problems, especially if persistent.
- `ping_dns_failure` → DNS is failing *before* we can even ping the host.

---

### DNS metrics (from `dns_check.py`)

Per service (if DNS enabled):

- `latency_ms` (`dns_ms` in code)  
  How long the DNS resolver takes to return an IP.
- `error_kind`:
  - `ok`
  - `dns_temp_failure`  
    temporary resolver issues (campus DNS flaking).
  - `dns_nxdomain`  
    host does not exist / blocked / typo.
  - `dns_timeout`  
    resolver did not respond in time.
  - `dns_other_error`

**How to read:**

- Fast DNS (<50 ms) makes everything *feel* snappy.
- Slow DNS or frequent `dns_temp_failure` → pages feel sluggish even if ping is fine.
- `dns_nxdomain` for one service while others are fine → service might be blocked or misconfigured.

---

### HTTP metrics (from `http_check.py` + `main.py`)

Per service (if HTTP enabled):

- `latency_ms` (`http_ms`)  
  Total time for a GET request to complete.
- `status_code`  
  200, 301, 404, 503, etc.
- `status_class` (in `details`)  
  One of `2xx`, `3xx`, `4xx`, `5xx`, `other`, or `None` when no response.
- `bytes` (in `details`)  
  Size of response body in bytes.
- `redirects` (in `details`)  
  Number of redirect hops.
- `error_kind`  
  Classified HTTP/network errors:
  - `http_timeout`
  - `http_ssl_error`
  - `http_connection_reset`
  - `http_connection_error`
  - `http_dns_error`
  - `http_4xx` / `http_5xx`
  - `http_other_error`
- `details` also includes a **per-request throughput estimate**:

  - `throughput_mbps=<value>`  
    Computed as:

    ```text
    throughput_mbps ≈ (bytes * 8 / 1_000_000) / (http_ms / 1000)
    ```

    So if we downloaded 200 KB in 100 ms, we’d see ~16 Mbps.

**How to read:**

- If ping & DNS are fine but HTTP `latency_ms` spikes and `throughput_mbps`
  drops for most services, it suggests congestion or throttling.
- `http_dns_error` while ping is OK → DNS issues specific to HTTP (resolver, proxy).
- `http_5xx` → the service itself is unhappy (server-side).

---

## Putting it together: diagnosing “what’s wrong with my internet?”

Combining the data from:

- long-term baseline data (`netinsight_log.csv`),
- focused Wi-Fi vs ISP bursts (`netinsight_wifi_diag.csv`),
- occasional bandwidth snapshots (speedtest),
- and per-service health snapshots (`netinsight_service_health.csv`),

Netinsight can strongly suggest *where* problems are coming from.

### 1. Wi-Fi / local network problems

**Typical signs:**

- In `wifi_diag`:
  - `role=gateway`: high jitter and/or high `packet_loss_pct`.
  - `role=google`: also bad or worse (expected, since everything passes through gateway).
- In baseline:
  - Many services have elevated ping jitter/loss at the same times.
- Speedtest:
  - May also look unstable or low.

**Interpretation:**

> Your Wi-Fi / local network is unstable (congestion, weak signal,
> interference, too many users on the same AP).

---

### 2. ISP / backhaul congestion or throttling

**Typical signs:**

- In `wifi_diag`:
  - `gateway` metrics are stable (low latency, low jitter, ~0% loss).
  - `google` shows high jitter/loss or much higher latency.
- In baseline:
  - For many services, HTTP `throughput_mbps` drops significantly at certain times
    (e.g. evenings), even though ping is still OK.
- In speedtest:
  - Download/upload Mbps is much lower at busy times than at quiet times
    (e.g. 2am vs 8pm), or much lower than your contract speed.

**Interpretation:**

> Wi-Fi looks fine, but the ISP / upstream path is congested or limited.
> This can be oversubscription (too many users), traffic shaping, or poor
> peering — from your point of view it behaves like “throttling”.

---

### 3. Service-specific blocking or failures (e.g. Discord)

**Typical signs:**

- Baseline:
  - Most services: good ping, good DNS, OK HTTP, reasonable `throughput_mbps`.
  - One service (e.g. `discord.com`) shows:
    - DNS errors: `dns_temp_failure` or `dns_nxdomain`.
    - HTTP errors: `http_dns_error`, `http_connection_reset`, etc.
    - Possibly ping failures to that host only.
- Wi-Fi diag and speedtest:
  - Look fine.

**Interpretation:**

> Your general internet connection is OK, but this specific service
> is blocked, filtered, or broken (DNS or connection level), possibly
> due to firewalling, censorship, or that service’s own problems.

---

### 4. Routing / peering issues (only some services are slow)

**Typical signs:**

- Wi-Fi diag:
  - Both `gateway` and `google` look fine.
- Speedtest:
  - Shows reasonable bandwidth.
- Baseline:
  - Some services (e.g. certain streaming platforms or regions) show
    low `throughput_mbps` and higher latency.
  - Others stay fast.

**Interpretation:**

> Likely a routing / peering issue: your ISP’s paths to some networks
> are congested or suboptimal, while others are fine.

---

### 5. Application-level issues

Sometimes the network looks fine but an app still misbehaves:

- NetInsight shows:
  - good ping/jitter/loss,
  - good DNS,
  - decent HTTP throughput,
  - good speedtest bandwidth.
- But e.g. Zoom glitches or a game lags only in specific situations.

**Interpretation:**

> The problem may be in the application itself (bugs, overloaded servers,
> bad config), or in the service’s infrastructure, not your local network
> or ISP.

NetInsight’s role here is to give you enough **hard data** to say:
“Look, my Wi-Fi and ISP are healthy; this looks like an app/server issue.”

---

## CLI & usage

### Examples

python3 -m src.cli baseline --once
python3 -m src.cli wifi-diag --rounds 5
python3 -m src.cli service-health -n discord.com
python3 -m src.cli speedtest

