import pandas as pd
from pathlib import Path

LOG_PATH = Path("data") / "netinsight_log.csv"


def load_log():
    df = pd.read_csv(LOG_PATH)

    # timestamp string → gerçek datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # hour = günün saati (0..23)
    df["hour"] = df["timestamp"].dt.hour

    return df


def hourly_ping_stats(df):
    # sadece ping ölçümleri
    ping_df = df[df["probe_type"] == "ping"].copy()

    grouped = (
        ping_df.groupby("hour")
        .agg(
            avg_latency_ms=("latency_ms", "mean"),
            packet_loss_pct=("success", lambda s: 100 * (1 - s.mean())),
            num_probes=("success", "size"),
        )
        .sort_index()
    )

    return grouped


def print_hourly_summary():
    df = load_log()
    stats = hourly_ping_stats(df)

    print("\n=== Hourly Ping Stats (0-23) ===")
    print(stats.round(2))

    # en iyi 3 saat
    best = stats.nsmallest(3, "avg_latency_ms")
    # en kötü 3 saat
    worst = stats.nlargest(3, "avg_latency_ms")

    print("\n=== Best Hours (lowest latency) ===")
    print(best.round(2))

    print("\n=== Worst Hours (highest latency) ===")
    print(worst.round(2))
def hourly_ping_stats_for_service(df, service):
    ping_df = df[(df["probe_type"] == "ping") & (df["service_name"] == service)].copy()

    if ping_df.empty:
        print(f"\n(no ping data for service: {service})")
        return None

    grouped = (
        ping_df.groupby("hour")
        .agg(
            avg_latency_ms=("latency_ms", "mean"),
            packet_loss_pct=("success", lambda s: 100 * (1 - s.mean())),
            num_probes=("success", "size"),
        )
        .sort_index()
    )
    return grouped


def print_service_hourly(df, service):
    stats = hourly_ping_stats_for_service(df, service)
    if stats is None:
        return

    print(f"\n=== Hourly Stats for {service} ===")
    print(stats.round(2))

    best = stats.nsmallest(3, "avg_latency_ms")
    worst = stats.nlargest(3, "avg_latency_ms")

    print("\nBest hours:")
    print(best.round(2))

    print("\nWorst hours:")
    print(worst.round(2))
def save_hourly_stats(df, output_path="data/hourly_stats.csv"):
    stats = hourly_ping_stats(df)
    stats.to_csv(output_path, index=True)
    print(f"Saved hourly stats to {output_path}")


def main():
    df = load_log()

    print_hourly_summary()
    save_hourly_stats(df)

if __name__ == "__main__":
    main()

