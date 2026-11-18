"""
sysinfo_cli - a small command-line tool used as the "application under test" for CLI automation.

Usage:
    python tools/sysinfo_cli.py info [--json]
    python tools/sysinfo_cli.py disk [--path PATH] [--min-free-gb N]
    python tools/sysinfo_cli.py count FILE [--pattern TEXT]
    python tools/sysinfo_cli.py --version

Exit codes (a CLI's "contract" that tests verify):
    0 = success
    1 = check failed (e.g. not enough free disk space)
    2 = usage error or file not found
"""
import argparse
import json
import os
import platform
import shutil
import socket
import sys

VERSION = "1.0.0"
EXIT_OK, EXIT_CHECK_FAILED, EXIT_USAGE = 0, 1, 2


def cmd_info(args):
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
        "cpu_count": os.cpu_count(),
    }
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        for key, value in info.items():
            print(f"{key:<12}: {value}")
    return EXIT_OK


def cmd_disk(args):
    if not os.path.exists(args.path):
        print(f"ERROR: path not found: {args.path}", file=sys.stderr)
        return EXIT_USAGE
    usage = shutil.disk_usage(args.path)
    free_gb = usage.free / 1024 ** 3
    print(f"path     : {args.path}")
    print(f"total_gb : {usage.total / 1024 ** 3:.1f}")
    print(f"free_gb  : {free_gb:.1f}")
    if args.min_free_gb is not None and free_gb < args.min_free_gb:
        print(f"FAIL: free space {free_gb:.1f} GB is below {args.min_free_gb} GB", file=sys.stderr)
        return EXIT_CHECK_FAILED
    print("STATUS   : OK")
    return EXIT_OK


def cmd_count(args):
    try:
        with open(args.file, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        return EXIT_USAGE
    if args.pattern:
        matches = sum(1 for line in lines if args.pattern in line)
        print(f"matches: {matches}")
    else:
        print(f"lines: {len(lines)}")
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(prog="sysinfo_cli", description="System information utility")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="show OS / Python / host details")
    p_info.add_argument("--json", action="store_true", help="output as JSON")
    p_info.set_defaults(func=cmd_info)

    p_disk = sub.add_parser("disk", help="show free disk space, optionally check a minimum")
    p_disk.add_argument("--path", default=os.path.abspath(os.sep), help="drive or folder (default: root)")
    p_disk.add_argument("--min-free-gb", type=float, help="fail (exit 1) if free space is below this")
    p_disk.set_defaults(func=cmd_disk)

    p_count = sub.add_parser("count", help="count lines, or lines containing a pattern, in a text file")
    p_count.add_argument("file")
    p_count.add_argument("--pattern", help="only count lines containing this text")
    p_count.set_defaults(func=cmd_count)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
