#!/usr/bin/env bash
# From the repo root on the PR head: every mutant must be killed.
set -u
here=$(dirname "$0")
for m in G1 G2 G3 N1 N2 N3 U1 U2 C1; do
  python3 "$here/mutants.py" "$m"
  if uv run pytest tests/unit/test_web_markers.py tests/unit/test_web_markers_survive.py -q -x -p no:randomly -n 0 >/dev/null 2>&1; then
    echo "$m SURVIVED"; else echo "$m killed"; fi
  git checkout -q -- src/sci2audio/web/markers.py
done
