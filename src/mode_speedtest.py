# src/mode_speedtest.py
"""Minimal Speedtest wrapper with robust logging and error handling."""

import logging
import sys

logger = logging.getLogger(__name__)


def _configure_logging():
    try:
        # Python 3.8+ supports force to reconfigure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True,
        )
    except TypeError:
        # Older Python: remove handlers and configure to stdout
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])


def main():
    _configure_logging()
    try:
        import speedtest
    except Exception as e:
        logger.error("speedtest module not available: %s", e)
        return

    try:
        st = speedtest.Speedtest()
        st.get_servers()
        st.get_best_server()
        download_bps = st.download()
        upload_bps = st.upload()
        results = st.results.dict()
    except Exception as e:
        logger.exception("Speedtest failed: %s", e)
        return

    server = results.get("server") or {}
    server_name = server.get("name")
    server_sponsor = server.get("sponsor")
    ping_ms = results.get("ping")

    download_mbps = download_bps / 1_000_000.0 if download_bps else 0.0
    upload_mbps = upload_bps / 1_000_000.0 if upload_bps else 0.0

    logger.info("Speedtest server: %s (%s)", server_name, server_sponsor)
    logger.info("Ping:     %.1f ms", ping_ms if ping_ms is not None else 0.0)
    logger.info("Download: %.2f Mbps", download_mbps)
    logger.info("Upload:   %.2f Mbps", upload_mbps)


if __name__ == "__main__":
    main()
