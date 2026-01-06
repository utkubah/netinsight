# src/mode_speedtest.py
"""
Small wrapper around speedtest-cli. If the module is missing, logs a helpful message.
"""

import logging
from .logging_setup import setup_logging

LOG = logging.getLogger("netinsight.speedtest")


def run_speedtest():
    try:
        import speedtest
    except Exception as e:
        LOG.error("speedtest not available: %s", e)
        return None

    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        dl = st.download()
        ul = st.upload()
        res = st.results.dict()
        server = res.get("server") or {}
        ping = res.get("ping")
        result = {
            "download_mbps": dl / 1_000_000.0,
            "upload_mbps": ul / 1_000_000.0,
            "ping_ms": ping,
            "server": server,
        }
        LOG.info("speedtest: %s", result)
        return result
    except Exception as e:
        LOG.error("speedtest failed: %s", e)
        return None


def main():
    setup_logging()
    run_speedtest()


if __name__ == "__main__":
    main()
