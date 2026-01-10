# NetInsight



NetInsight is a compact Python tool to monitor and analyze internet connection quality, built with a focus on unstable student Wi-Fi (e.g., dorm networks). Instead of only printing raw ping output, NetInsight records structured probe data (ping, DNS, HTTP and occasional bandwidth tests), computes reproducible quality metrics and statistical diagnostics, and produces human-readable reports.

---

## Quick summary

NetInsight:

* Runs periodic probes and logs structured rows (`data/netinsight_log.csv`).
* Scores each probe with a **0–100** quality score and classifies rows into `good/ok/bad`.
* Produces ready-to-use analyses and CSVs: hourly summaries, downtime detection, statistically-detected **bad intervals**, Wi-Fi vs ISP diagnostics, per-service health checks, and speedtest summaries.
* Provides a small CLI to run collection modes, analyzers, and a human report.

---

## What it does

* **Baseline logger** (24/7): runs ping / DNS / HTTP for each configured service and writes one row per probe to `data/netinsight_log.csv`.
* **Quality scoring**: converts raw probe metrics into a 0–100 score and `good/ok/bad` tier; saves `data/quality_rows.csv`, hourly and service aggregates.
* **Bad interval detection**: sliding/rolling windows detect statistically anomalous low-score periods and merge adjacent bad windows into human-friendly intervals (`data/bad_intervals.csv`).
* **Downtime detection**: finds multi-probe downtimes from consecutive ping failures; writes `data/downtimes.csv` and `data/total_downtime.csv`.
* **Wi-Fi diagnostic**: short bursts comparing `gateway` vs external baseline to help decide Wi-Fi vs ISP problems.
* **Service health**: single-domain runs (ping/DNS/HTTP) that classify a service as `healthy`, `dns_failure`, `possible_blocked_or_restricted`, etc.
* **Speedtest**: snapshot bandwidth tests via `speedtest-cli` and summary analysis.

---

## Modes (what to run)

Each mode is implemented under `src/` and writes CSVs under `data/`.

### Baseline (24/7 logger)

* Script: `src/main.py`
* CLI: `python3 -m src.cli baseline [--once] [--log <path>]`
* Log: `data/netinsight_log.csv`
* Notes: default `INTERVAL_SECONDS = 30` (changeable in `src/main.py`). Each round writes `mode="baseline"` and a `round_id`.

### Wi-Fi diagnostic

* Script: `src/mode_wifi_diag.py`
* CLI: `python3 -m src.cli wifi-diag --rounds N --interval S [--gateway IP] [--external HOST]`
* Log: `data/netinsight_wifi_diag.csv`
* Purpose: short burst comparing gateway vs an external host to distinguish local Wi-Fi problems from ISP/upstream problems.

### Service health / blocked-site

* Script: `src/mode_service_health.py`
* CLI: `python3 -m src.cli service-health -n <domain>`
* Log: `data/netinsight_service_health.csv`
* Purpose: single-domain checks and classification (healthy / dns_failure / blockedish / connection_issue / etc.).

### Speedtest

* Script: `src/mode_speedtest.py`
* CLI: `python3 -m src.cli speedtest` (requires `speedtest-cli`)
* Log: `data/netinsight_speedtest.csv` (if enabled)
* Purpose: one-off bandwidth snapshot (ping, download/upload Mbps).

---

## Analyses (scripts/)

* `scripts/quality_score.py` — compute per-row `score` and `tier`, write `data/quality_rows.csv`, `data/quality_hourly.csv`, `data/quality_by_service.csv`.
* `scripts/detect_bad_intervals.py` — sliding windows; flag and merge bad windows → `data/bad_intervals.csv`.
* `scripts/detect_downtime.py` — detect downtime events → `data/downtimes.csv`, `data/total_downtime.csv`.
* `scripts/analyze_time_of_day.py` — hourly ping stats → `data/hourly_stats.csv`.
* `scripts/analyze_wifi_diag.py` — summarize wifi_diag runs → `data/wifi_diag_windows.csv`, `data/wifi_diag_summary.csv`. Robust to missing columns and missing gateway.
* `scripts/analyze_service_health.py` — summarize `netinsight_service_health.csv`.
* `scripts/analyze_speedtest.py` — summarize speedtest runs → `data/speedtest_summary.csv`, `data/speedtest_hourly.csv`.

There is an `src/analyze.py` helper that runs the right set of scripts for `baseline | wifi-diag | service-health | speedtest | all`.

---

## CLI & usage examples

Run from repository root.

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# optional: for speedtest
pip install speedtest-cli
```

### Examples

```bash
# Show help
python3 -m src.cli --help

# Baseline — continuous (Ctrl+C to stop)
python3 -m src.cli 

# Baseline — single round
python3 -m src.cli baseline --once

# Short Wi-Fi diagnostic (5 rounds, 1s apart)
python3 -m src.cli wifi-diag --rounds 5 --interval 1

# Wi-Fi diag with explicit gateway (useful if auto-detect fails, esp. on macOS)
python3 -m src.cli wifi-diag --gateway 192.168.1.1 --rounds 5 --interval 1

# Service health check
python3 -m src.cli service-health -n discord.com

# Speedtest
python3 -m src.cli speedtest

# Run analyzers
python3 -m src.cli analyze baseline
python3 -m src.cli analyze all

# Print a human summary report
python3 -m src.cli report wifi-diag
python3 -m src.cli report all
```

---

## Outputs and where to look

Generated CSVs (under `data/`):

* `data/netinsight_log.csv` — raw baseline rows
* `data/quality_rows.csv` — enriched rows with `score` and `tier`
* `data/quality_hourly.csv` — hourly aggregates (avg, p10/p90, good/bad %)
* `data/quality_by_service.csv` — per-service aggregates
* `data/bad_intervals.csv` — detected bad intervals (see columns below)
* `data/downtimes.csv`, `data/total_downtime.csv` — down events & totals
* `data/netinsight_wifi_diag.csv`, `data/wifi_diag_windows.csv`, `data/wifi_diag_summary.csv`
* `data/netinsight_service_health.csv`, `data/service_health_*`
* `data/netinsight_speedtest.csv`, `data/speedtest_*`

**Important `bad_intervals.csv` columns**:

```
start_time, end_time, duration_seconds,
mean_score, mean_score_delta, mean_score_z,
bad_pct, n_samples, num_windows,
severity, reason, affected_services_count,
top_services_by_bad_pct, top_services_by_count,
gateway_involved, diagnosis
```

Use `severity + reason + top_services_by_bad_pct` to direct your investigation.

> Note: CSV outputs are runtime artifacts and are **not tracked by git**.

---

## How to read the main analysis outputs (practical advice)
* **Start**: run `python3 -m src.cli report` — it prints best/worst hours, top bad intervals, downtime totals, Wi-Fi diag summary, service health and speedtest summaries.
* **Bad intervals (`bad_intervals.csv`)**:

  * `reason` can be `low_mean`, `high_bad`, or `low_mean+high_bad`.
  * `mean_score_z` shows how many standard deviations interval mean is below baseline (negative is worse).
  * `gateway_involved=True` + many `affected_services_count` → likely gateway/local or network-wide issue.
  * `top_services_by_bad_pct` lists services with highest fraction of `bad` rows (eg: `discord(100%),gateway(100%),youtube(78%)`).
* **Downtime**: `total_downtime_seconds` high for `gateway` = router problems; for a service = repeated outages.
* **Wi-Fi diag**:

  * gateway poor & external good → Wi-Fi/local problem.
  * gateway good & external poor → ISP/backhaul problem.
  * gateway missing → `inconclusive_missing_gateway` (see troubleshooting).
* **Service health**: recent checks and `service_state` indicate blocked / DNS / HTTP issues.

---

## Troubleshooting

### 1) Timezone & timestamps

* **Default analysis timezone:** `Europe/Rome`.
* It needs to be adjusted for people who live in a different timezone. 

Files to change the timezone (if needed):
* `scripts/quality_score.py`, `scripts/detect_bad_intervals.py`, `scripts/analyze_speedtest.py` — each defines a `TIMEZONE` variable.

### 2) Gateway auto-detection

*  If autodetection fails there are possible workarounds:

  * Provide gateway explicitly: `--gateway 192.168.1.1` to `wifi-diag`.
  * Or set the gateway manually in targets.json and disable persist_gateway function.


### 3) Not enough samples for windows

* `detect_bad_intervals.py` uses `MIN_SAMPLES = 30`. If you have too short a log, either collect more data or reduce `MIN_SAMPLES` for testing.

---

## Scoring & detection parameters (defaults)

**Row scoring (in `scripts/quality_score.py`)**

* Ping:

  * latency decay constant: `200 ms` (score ∝ `exp(-lat/200)`).
  * jitter decay constant: `20 ms` (score ∝ `exp(-jit/20)`).
  * packet loss decay: `2%` (score ∝ `exp(-loss/2)`).
  * Weights (when loss present): `latency 55%`, `jitter 30%`, `loss 15%`. If loss missing weights are renormalized.
* DNS: `exp(-dns_ms / 50)`.
* HTTP: `exp(-http_ms / 300)`. Penalize 5xx (×0.4) and 4xx (×0.7).
* Tiers: `good >= 80`, `ok >= 50`, else `bad`.

**Bad intervals (in `scripts/detect_bad_intervals.py`)**

* `WINDOW_MINUTES = 5`, `STEP_MINUTES = 1`, `MIN_SAMPLES = 30`.
* Statistical rule: `window_score_z = (mean_score - global_mean)/global_std`. Flag if `window_score_z <= -K_STD` **or** `bad_pct >= BAD_PCT_THRESHOLD`.

  * Defaults: `K_STD = 1.0`, `BAD_PCT_THRESHOLD = 50.0`.
* Severity thresholds (z): `SEV_1_Z = -1.0`, `SEV_2_Z = -1.5`, `SEV_3_Z = -2.0`.
* Bad% severity thresholds: `SEV_1_BAD_PCT = 50.0`, `SEV_2_BAD_PCT = 60.0`, `SEV_3_BAD_PCT = 80.0`.

Tweak these in the scripts for different sensitivity.

---

## Developer notes — where to tweak

* `src/main.py` — baseline `INTERVAL_SECONDS` and CSV headers.
* `scripts/quality_score.py` — scoring math, weights and `TIMEZONE`.
* `scripts/detect_bad_intervals.py` — windowing and thresholds.
* `src/net_utils.py` — gateway detection (add macOS/Windows fallback).
* `src/analyze.py`, `src/report.py` — adjust pipeline/report output as needed.

---

## Security & privacy notes

* Raw logs include hostnames, URLs and request details (and occasionally error messages). Treat `data/` as potentially sensitive: **do not commit raw logs** to git.
* Restrict filesystem access to `data/` (e.g., secure the server, use proper permissions).
* If you transmit CSVs externally, strip or obfuscate sensitive fields (hostnames/URLs/details) unless necessary.
* Consider simple retention and rotation (rotate old logs) and consent/notice where required.


## License
MIT License — see `LICENSE`