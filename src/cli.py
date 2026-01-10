# src/cli.py
"""
Simple command-line interface for NetInsight.

Examples:
  python3 -m src.cli baseline --once
  python3 -m src.cli wifi-diag --rounds 5
  python3 -m src.cli service-health -n discord.com
  python3 -m src.cli speedtest
  python3 -m src.cli analyze baseline
  python3 -m src.cli report all
"""

import argparse
import sys

from .logging_setup import setup_logging
from . import main as baseline_main
from . import mode_wifi_diag
from . import mode_service_health
from . import mode_speedtest
from . import analyze as analyze_mod
from . import report as report_mod


def build_parser():
    p = argparse.ArgumentParser(prog="netinsight")
    sub = p.add_subparsers(dest="cmd")

    # baseline
    b = sub.add_parser("baseline")
    b.add_argument("--once", action="store_true")
    b.add_argument("--log", default=baseline_main.LOG_PATH)

    # wifi-diag
    w = sub.add_parser("wifi-diag")
    w.add_argument("--rounds", type=int, default=10)
    w.add_argument("--interval", type=float, default=1.0)
    w.add_argument("--gateway", default=None)
    w.add_argument("--external", default=None)
    w.add_argument("--log", default=mode_wifi_diag.LOG_PATH)

    # service-health
    s = sub.add_parser("service-health")
    s.add_argument("-n", "--name", required=True)
    s.add_argument("--log", default=mode_service_health.LOG_PATH)

    # speedtest
    sub.add_parser("speedtest")

    # analyze (runs scripts/* analyzers)
    a = sub.add_parser("analyze")
    a.add_argument(
        "target",
        choices=["baseline", "wifi-diag", "service-health", "speedtest", "all"],
    )

    # report (prints human-readable summary from data/*.csv outputs)
    r = sub.add_parser("report")
    r.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["baseline", "wifi-diag", "service-health", "speedtest", "all"],
    )

    return p


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    setup_logging()

    # ✅ No args: default behavior -> run baseline forever
    if len(argv) == 0:
        baseline_main.main()
        return

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "baseline":
        baseline_main.LOG_PATH = args.log
        if args.once:
            baseline_main.run_once()
        else:
            baseline_main.main()

    elif args.cmd == "wifi-diag":
        mode_wifi_diag.run_wifi_diag(
            rounds=args.rounds,
            interval=args.interval,
            gateway_host=args.gateway,
            external_host=args.external,
            log_path=args.log,
        )

    elif args.cmd == "service-health":
        mode_service_health.run_service_health(args.name, log_path=args.log)

    elif args.cmd == "speedtest":
        mode_speedtest.run_speedtest()

    elif args.cmd == "analyze":
        analyze_mod.run(args.target)

    elif args.cmd == "report":
        report_mod.run(args.target)

if __name__ == "__main__":
    main()
