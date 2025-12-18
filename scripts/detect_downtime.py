
import pandas as pd
from pathlib import Path

LOG_PATH = Path("data") / "netinsight_log.csv"
OUTPUT_PATH = Path("data") / "downtimes.csv"

# Parametreler: burayı istersen sonra ince ayar yaparsın
MIN_CONSEC_FAILURES = 3          # en az kaç ardışık fail olursa downtime saysın
MAX_GAP_SECONDS = 90             # iki fail arası 90 sn'den fazlaysa ayrı event olsun
PROBE_TYPE = "ping"              # sadece ping'e bakıyoruz (istersen http yaparsın)


def load_log() -> pd.DataFrame:
    df = pd.read_csv(LOG_PATH)

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])

    # sadece seçtiğimiz probe tipine bak
    df = df[df["probe_type"] == PROBE_TYPE].copy()

    # timestamp'e göre sırala
    df = df.sort_values(["service_name", "timestamp"]).reset_index(drop=True)
    return df


def detect_downtimes_for_service(df: pd.DataFrame, service: str) -> list[dict]:
    svc_df = df[df["service_name"] == service].reset_index(drop=True)

    events: list[dict] = []
    current_start = None
    last_ts = None
    fail_count = 0

    for _, row in svc_df.iterrows():
        ts = row["timestamp"]
        ok = bool(row["success"])

        if not ok:
            # failure
            if current_start is None:
                # yeni event başlıyor
                current_start = ts
                fail_count = 1
            else:
                # aynı event mi yoksa arada büyük boşluk var mı
                if (ts - last_ts).total_seconds() <= MAX_GAP_SECONDS:
                    fail_count += 1
                else:
                    # eski event'i kapat
                    if fail_count >= MIN_CONSEC_FAILURES:
                        events.append(
                            {
                                "service_name": service,
                                "probe_type": PROBE_TYPE,
                                "start_time": current_start,
                                "end_time": last_ts,
                                "duration_seconds": (last_ts - current_start).total_seconds(),
                                "num_failures": fail_count,
                            }
                        )
                    # yeni event başlat
                    current_start = ts
                    fail_count = 1
        else:
            # success
            if current_start is not None:
                # devam eden bir downtime var mı kontrol et
                if fail_count >= MIN_CONSEC_FAILURES:
                    events.append(
                        {
                            "service_name": service,
                            "probe_type": PROBE_TYPE,
                            "start_time": current_start,
                            "end_time": last_ts,
                            "duration_seconds": (last_ts - current_start).total_seconds(),
                            "num_failures": fail_count,
                        }
                    )
            # her halükarda resetle
            current_start = None
            fail_count = 0

        last_ts = ts

    # dosya bitti ama open event kalmış olabilir
    if current_start is not None and fail_count >= MIN_CONSEC_FAILURES:
        events.append(
            {
                "service_name": service,
                "probe_type": PROBE_TYPE,
                "start_time": current_start,
                "end_time": last_ts,
                "duration_seconds": (last_ts - current_start).total_seconds(),
                "num_failures": fail_count,
            }
        )

    return events


def detect_all_downtimes(df: pd.DataFrame) -> pd.DataFrame:
    all_events: list[dict] = []

    for service in sorted(df["service_name"].unique()):
        svc_events = detect_downtimes_for_service(df, service)
        all_events.extend(svc_events)

    if not all_events:
        return pd.DataFrame(
            columns=[
                "service_name",
                "probe_type",
                "start_time",
                "end_time",
                "duration_seconds",
                "num_failures",
            ]
        )

    events_df = pd.DataFrame(all_events)
    events_df = events_df.sort_values("start_time").reset_index(drop=True)
    return events_df


def print_summary(events: pd.DataFrame) -> None:
    if events.empty:
        print("\nNo downtime events detected with current thresholds.")
        return

    print("\n=== Detected downtime events ===")
    print(events.to_string(index=False))

    totals = compute_total_downtime(events)

    print("\n=== Total downtime per service ===")
    print(totals.to_string(index=False))

def compute_total_downtime(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(
            columns=["service_name", "total_downtime_seconds", "num_events"]
        )

    totals = (
        events
        .groupby("service_name")
        .agg(
            total_downtime_seconds=("duration_seconds", "sum"),
            num_events=("start_time", "count"),
        )
        .sort_values("total_downtime_seconds", ascending=False)
        .reset_index()
    )
    return totals



def main():
    df = load_log()
    events = detect_all_downtimes(df)

    # save events
    events.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved downtime events to {OUTPUT_PATH}")

    # compute total downtime
    totals = compute_total_downtime(events)
    totals_output_path = Path("data") / "total_downtime.csv"
    totals.to_csv(totals_output_path, index=False)
    print(f"Saved total downtime summary to {totals_output_path}")

    # terminal output
    print_summary(events)

if __name__ == "__main__":
    main()
