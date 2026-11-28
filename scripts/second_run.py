"""A text's first and second run through the text steps, and whether they read the same
(D-577): the quick look before a regression row for a text rule (#1227).

    uv run python scripts/second_run.py en "It is 3x-2 here." "A=-3"
    uv run python scripts/second_run.py de --heading "Kapitel IV.≈1"

Each text is one paragraph (a heading with --heading). Prints SAME and the reading, or DIFF
and both runs; exit status 1 if any text reads differently on its second run.
"""

from __future__ import annotations

import argparse
import sys

from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text


def both_runs(text: str, language: str, kind: BlockKind) -> tuple[str, str]:
    """The spoken text of the first run and of a second run over the first one's script."""
    document = make_document([(kind, text)], language)
    context = StepContext(language)
    first = run_steps(document, context, strict=True)
    second = run_steps(rebuilt_from_script(document, first.script()), context, strict=True)
    return spoken_text(first.script()), spoken_text(second.script())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language", help="the document's language, as en or de")
    parser.add_argument("texts", nargs="+", metavar="TEXT")
    parser.add_argument("--heading", action="store_true", help="read each text as a heading")
    args = parser.parse_args()
    kind = BlockKind.HEADING if args.heading else BlockKind.PARAGRAPH
    differs = False
    for text in args.texts:
        first, second = both_runs(text, args.language, kind)
        if first == second:
            print(f"SAME {text!r}\n  {first}")
        else:
            differs = True
            print(f"DIFF {text!r}\n  1: {first}\n  2: {second}")
    return 1 if differs else 0


if __name__ == "__main__":
    sys.exit(main())
