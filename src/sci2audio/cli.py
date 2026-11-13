"""Command line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from sci2audio import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sci2audio",
        description="Turn scientific texts into faithful, offline audiobooks.",
    )
    parser.add_argument("--version", action="version", version=f"sci2audio {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    ui = commands.add_parser(
        "ui", help="open the sci2audio interface in your browser (it stays on this computer)"
    )
    ui.add_argument(
        "--no-browser", action="store_true", help="only print the link; do not open a browser"
    )
    args = parser.parse_args(argv)
    if args.command == "ui":
        from sci2audio.web import run  # loads the web framework only for this command

        return run(open_browser=not args.no_browser)
    print("sci2audio is in pre-release: run `sci2audio ui` to open the interface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
