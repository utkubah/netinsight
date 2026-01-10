# src/cli.py
"""
Simple command-line interface for NetInsight.

Examples:
  python3 -m src.cli baseline --once
  python3 -m src.cli wifi-diag --rounds 5
  python3 -m src.cli service-health -n discord.com
  python3 -m src.cli speedtest
  python3 -m src.cli analyze all
  python3 -m src.cli report all
  python3 -m src.cli clean --yes
"""

import argparse
import sys
import logging
from pathlib import Path

from .logging_setup import setup_logging
from . import main as baseline_main
from . import mode_wifi_diag
from . import mode_service_health
from . import mode_speedtest
from . import analyze as analyze_mod
from . import report as report_mod

LOG = logging.getLogger("netinsight.cli")


def build_parser():
    p = argparse.ArgumentParser(prog="netinsight")
    # (len(argv) == 0 will run baseline_main.main()).
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

    # analyze (runs analyzers for a target)
    a = sub.add_parser("analyze")
    a.add_argument(
        "target",
        choices=["baseline", "wifi-diag", "service-health", "speedtest", "all"],
    )

    # report (prints human-readable summary)
    r = sub.add_parser("report")
    r.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["baseline", "wifi-diag", "service-health", "speedtest", "all"],
    )

    # clean: delete CSV files in the data folder
    c = sub.add_parser("clean", help="Delete CSV files from the data directory (interactive by default)")
    c.add_argument("--data-dir", default="data", help="Directory containing CSV files (default: data)")
    c.add_argument("--pattern", default="*.csv", help="Glob pattern for files to delete (default: '*.csv')")
    c.add_argument("--yes", "-y", action="store_true", help="Proceed without prompting")
    c.add_argument("--dry-run", action="store_true", help="List files without deleting them")
    c.add_argument("--verbose", action="store_true", help="Verbose output for deletions")

    return p


def clean_data_dir(data_dir="data", pattern="*.csv", yes=False, verbose=False):
    """
    Delete files matching pattern in data_dir.

    Returns the number of files deleted (or that would be deleted in dry-run).
    """
    p = Path(data_dir).expanduser()
    if not p.exists() or not p.is_dir():
        print(f"No data directory found at {p}")
        return 0

    files = sorted([f for f in p.glob(pattern) if f.is_file()])

    if not files:
        print(f"No files matching '{pattern}' in {p}")
        return 0

    print(f"Found {len(files)} file(s) in {p} matching '{pattern}':")
    for f in files:
        print("  " + str(f))


    if not yes:
        try:
            resp = input(f"Delete {len(files)} file(s) from {p}? [y/N]: ").strip().lower()
        except EOFError:
            print("No input available; aborting.")
            return 0
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 0

    deleted = 0
    for f in files:
        try:
            f.unlink()
            deleted += 1
            if verbose:
                print(f"Deleted {f}")
        except Exception as e:
            print(f"Failed to delete {f}: {e}")

    print(f"Deleted {deleted}/{len(files)} file(s).")
    return deleted


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    setup_logging()

    # ✅ No args: default behavior -> run baseline forever (keeps prior behavior)
    if len(argv) == 0:
        baseline_main.main()
        return

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "baseline":
        # Keep compatibility with existing baseline CLI behavior
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

    elif args.cmd == "clean":
        clean_data_dir(
            data_dir=args.data_dir,
            pattern=args.pattern,
            yes=args.yes,
            verbose=args.verbose,
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
