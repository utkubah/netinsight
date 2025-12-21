# src/mode_speedtest.py
"""
Minimal Speedtest mode for NetInsight.

Runs a single speedtest using the `speedtest` Python module (speedtest-cli)
and prints ping, download and upload speeds.

Usage:
    python src/mode_speedtest.py
"""

import speedtest


def main():
    st = speedtest.Speedtest()
    st.get_servers()
    st.get_best_server()

    download_bps = st.download()
    upload_bps = st.upload()
    results = st.results.dict()

    server = results.get("server") or {}
    server_name = server.get("name")
    server_sponsor = server.get("sponsor")
    ping_ms = results.get("ping")

    download_mbps = download_bps / 1_000_000.0
    upload_mbps = upload_bps / 1_000_000.0

    print(f"Speedtest server: {server_name} ({server_sponsor})")
    print(f"Ping:     {ping_ms:.1f} ms")
    print(f"Download: {download_mbps:.2f} Mbps")
    print(f"Upload:   {upload_mbps:.2f} Mbps")


if __name__ == "__main__":
    main()
