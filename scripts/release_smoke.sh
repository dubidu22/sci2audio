#!/usr/bin/env bash
# Runs the installed sci2audio command (from `uv tool install`, not the source tree) on one
# corpus PDF, as a person would: the release workflow calls it for the built wheel before
# publishing and for the release from PyPI after (#80, D-485). Offline: no voice download.
#
#   bash scripts/release_smoke.sh <expected version>
set -euo pipefail

expected="$1"
repo=$(cd "$(dirname "$0")/.." && pwd)
pdf="$repo/tests/corpus/papers/joss2021-waskom-seaborn.pdf"

bin=$(uv tool dir --bin)
if command -v cygpath > /dev/null; then bin=$(cygpath -u "$bin"); fi  # Git Bash on Windows
sci2audio="$bin/sci2audio"

work=$(mktemp -d)
cd "$work"  # outside the checkout: nothing can be imported from the source tree

shown=$("$sci2audio" --version)
echo "$shown"
test "$shown" = "sci2audio $expected"

"$sci2audio" script "$pdf" -o "$work/out" --work-folder "$work/work" --ignore-settings
for suffix in script.txt report.json report.md; do
  test -s "$work/out/joss2021-waskom-seaborn.$suffix"
done
echo "smoke test passed: sci2audio $expected"
