#!/usr/bin/env bash
# The checks before a PR opens (CLAUDE.md step 3, #1227): ruff, format, layers, deptry, pyright
# and the fast suite, stopping at the first that fails. The suite's output goes to a log; what
# shows is its summary and the failing tests. Runs in a clone or in one of its git worktrees,
# which use the clone's .venv with their own src first, so no second venv is made.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
if [[ -x .venv/bin/python ]]; then
  bin=.venv/bin
else
  bin="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.venv/bin"
  export PYTHONPATH="$PWD/src"
fi
[[ -x "$bin/python" ]] || { echo "no .venv: run 'uv sync' in the clone first" >&2; exit 2; }
log="$(mktemp -t precheck)"

# each check stops the script when it fails, and says "ok" only when it passed
check() {
  printf '%-10s' "$1"; shift
  if "$@" >"$log" 2>&1; then echo ok; else echo FAILED; tail -40 "$log"; exit 1; fi
}
check ruff    "$bin/ruff" check
check format  "$bin/ruff" format --check
check layers  "$bin/lint-imports"
check deptry  "$bin/deptry" src
check pyright "$bin/pyright" --pythonpath "$bin/python"
printf '%-10s' tests
if "$bin/python" -m pytest -q -p no:cacheprovider -n auto \
  -m "not slow and not benchmark and not browser" >"$log" 2>&1; then
  tail -1 "$log"
else
  grep -E '^(FAILED|ERROR) ' "$log" || true
  tail -1 "$log"
  echo "full output: $log"
  exit 1
fi
