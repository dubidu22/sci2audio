"""The corpus comparison: what `sci2audio script` writes for every corpus sample, here and at
a ref, and which output files differ (`.claude/rules/project.md`, #1227).

    uv run python scripts/corpus_diff.py              # against origin/main
    uv run python scripts/corpus_diff.py HEAD~1       # against any ref
    uv run python scripts/corpus_diff.py --keep DIR   # keep both outputs in DIR

The ref is checked out in a temporary git worktree and run with this checkout's Python, so
both sides use the same dependencies. Exit status 1 if an output file differs.
"""

from __future__ import annotations

import argparse
import difflib
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "corpus"
SHOWN = 12  # changed lines shown per script file
GIT = shutil.which("git") or "git"


def samples() -> list[Path]:
    """Every sample document of the corpus: the papers and the other formats' samples."""
    found = sorted((CORPUS / "papers").glob("*"))
    for pattern in ("*/*.md", "*/*.txt", "*/*.epub"):
        found += sorted(CORPUS.glob(pattern))
    return [
        path
        for path in found
        if path.is_file()
        and path.name not in ("LICENSES.md", "README.md")
        and path.parent.name != "truth"
    ]


def write_scripts(source_root: Path, out: Path) -> list[str]:
    """Run `sci2audio script` from `source_root/src` on every sample into `out`; the failures."""
    environment = {**os.environ, "PYTHONPATH": str(source_root / "src")}
    failed = []
    for sample in samples():
        work = out.with_name(out.name + "-work") / sample.stem
        command = [sys.executable, "-m", "sci2audio.cli", "script", str(sample), "-o", str(out)]
        command += ["--work-folder", str(work), "--ignore-settings", "-q"]
        result = subprocess.run(  # noqa: S603 (this Python, no shell)
            command, env=environment, capture_output=True, text=True
        )
        if result.returncode != 0:
            failed.append(f"{sample.name}: {result.stderr.strip().splitlines()[-1:]}")
    return failed


def compare(here: Path, there: Path) -> list[str]:
    """The output files that differ or exist on one side only, with a few changed lines."""
    lines = []
    names = {p.name for side in (here, there) for p in side.iterdir() if p.is_file()}
    for name in sorted(names):
        mine, theirs = here / name, there / name
        if not mine.exists() or not theirs.exists():
            lines.append(f"only {'at the ref' if theirs.exists() else 'here'}: {name}")
        elif mine.read_bytes() != theirs.read_bytes():
            lines.append(f"differs: {name}")
            if name.endswith(".script.txt"):
                old = theirs.read_text(encoding="utf-8").splitlines()
                new = mine.read_text(encoding="utf-8").splitlines()
                changed = [
                    f"    {line}"
                    for line in difflib.unified_diff(old, new, lineterm="", n=0)
                    if line[:1] in "+-" and not line.startswith(("+++", "---"))
                ]
                lines += changed[:SHOWN] + (["    …"] if len(changed) > SHOWN else [])
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ref", nargs="?", default="origin/main")
    parser.add_argument("--keep", type=Path, help="keep both outputs in this folder")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="corpus-diff-") as temporary:
        base = args.keep or Path(temporary)
        here, there, tree = base / "here", base / "ref", Path(temporary) / "ref-tree"
        added = subprocess.run(  # noqa: S603 (git, no shell)
            [GIT, "-C", str(ROOT), "worktree", "add", "-q", "--detach", str(tree), args.ref],
            capture_output=True,
            text=True,
        )
        if added.returncode != 0:
            print(f"cannot check out {args.ref}: {added.stderr.strip()}", file=sys.stderr)
            return 2
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                ours = pool.submit(write_scripts, ROOT, here)
                theirs = pool.submit(write_scripts, tree, there)
                failures = ours.result() + theirs.result()
        finally:
            remove = [GIT, "-C", str(ROOT), "worktree", "remove", "--force", str(tree)]
            subprocess.run(remove, check=False)  # noqa: S603 (git, no shell)
        report = compare(here, there)
        total = sum(1 for p in here.iterdir() if p.is_file())
        for line in failures:
            print(f"failed: {line}")
        print("\n".join(report) if report else f"identical: all {total} output files")
        return 1 if report or failures else 0


if __name__ == "__main__":
    sys.exit(main())
