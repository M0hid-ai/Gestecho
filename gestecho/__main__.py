"""Command-line entry point: `python -m gestecho`."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gestecho", description="Tap your desk. Windows responds.")
    parser.add_argument("--tray", action="store_true", help="start hidden in the system tray")
    parser.add_argument("--list-devices", action="store_true", help="print usable microphones and exit")
    parser.add_argument("--soak", type=int, metavar="N", help="run N synthetic taps through the pipeline and exit")
    args = parser.parse_args(argv)

    if args.list_devices:
        from . import devices

        default = devices.default_input()
        for dev in devices.list_inputs():
            mark = "*" if default and dev.key == default.key else " "
            print(f"{mark} {dev.label}")
        return 0
    if args.soak:
        from .soak import run as soak

        return soak(args.soak)

    from .ui.app import run

    return run(start_in_tray=args.tray)


if __name__ == "__main__":
    sys.exit(main())
