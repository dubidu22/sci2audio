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
    parser.parse_args(argv)
    print("sci2audio is in pre-release: nothing to run yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
