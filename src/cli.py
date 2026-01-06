# src/cli.py
"""
Simple command-line interface for NetInsight.

Examples:
  python3 -m src.cli baseline --once
  python3 -m src.cli wifi-diag --rounds 5
  python3 -m src.cli service-health -n discord.com
  python3 -m src.cli speedtest
"""

import argparse
import sys
from .logging_setup import setup_logging
from . import main as baseline_main
from . import mode_wifi_diag
from . import mode_service_health
from . import mode_speedtest

def build_parser():
    p = argparse.ArgumentParser(prog="netinsight")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("baseline")
    b.add_argument("--once", action="store_true")
    b.add_argument("--log", default=baseline_main.LOG_PATH)

    w = sub.add_parser("wifi-diag")
    w.add_argument("--rounds", type=int, default=10)
    w.add_argument("--interval", type=float, default=1.0)
    w.add_argument("--gateway", default=None)
    w.add_argument("--external", default=None)
    w.add_argument("--log", default=mode_wifi_diag.LOG_PATH)

    s = sub.add_parser("service-health")
    s.add_argument("-n", "--name", required=True)
    s.add_argument("--log", default=mode_service_health.LOG_PATH)

    sp = sub.add_parser("speedtest")

    return p

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "baseline":
        baseline_main.LOG_PATH = args.log
        if args.once:
            baseline_main.run_once()
        else:
            baseline_main.main()

    elif args.cmd == "wifi-diag":
        mode_wifi_diag.run_wifi_diag(rounds=args.rounds, interval=args.interval, gateway_host=args.gateway, external_host=args.external, log_path=args.log)

    elif args.cmd == "service-health":
        mode_service_health.run_service_health(args.name, log_path=args.log)

    elif args.cmd == "speedtest":
        mode_speedtest.run_speedtest()

if __name__ == "__main__":
    main()
