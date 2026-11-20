# Review: PR #224, round 1 (R1 of #80, release workflow)

Reviewed 14 Nov 2026 ~01:25 UTC on head f23624e (base f1a334a). Critical (risk:high, release workflow). Checked against plans/issue80-release-plan.md s.2 and s.7 (D-484 to D-489), CLAUDE.md and .claude/rules.

**Verdict: one fix needed (F1), then merge when CI is green.**

## Checked and correct

- Final diff touches only `.github/workflows/release.yml` and the new `scripts/release_smoke.sh`. The temporary `workflow_dispatch` (b1db322) is fully reverted by f23624e: `git diff 49911f1 f23624e` is empty and the final file has `on: push: tags: ["v*"]` only.
- Every `uses:` is pinned by full SHA (checkout v7.0.1, setup-uv v10.3.3, upload-artifact v7.0.2, download-artifact v8.0.2, pypi-publish v1.14.3), same pins as ci.yml.
- `persist-credentials: false` on all four checkouts. `enable-cache: false` on every setup-uv, so a release never restores a PR-written cache.
- Permissions: workflow default `contents: read`; `publish` has only `id-token: write` in environment `pypi`, no stored token; `github-release` is the only job with `contents: write`, and its token is in that one step's env only.
- `github.ref_name` reaches shells only through `env:` (no template injection). `matrix.os` appears only in job names.
- `build` fails unless tag == `v` + `__version__` (D-484). `publish` needs `[build, smoke]`, and `smoke` is a three-system matrix with fail-fast off, so nothing reaches PyPI unless Linux, macOS and Windows all pass (D-485).
- Smoke installs the built wheel with `uv tool install` (uv-managed Python from `.python-version`, `UV_PYTHON_PREFERENCE: only-managed`, `--torch-backend cpu` on Linux as the README says), from `$RUNNER_TEMP`; `release_smoke.sh` runs the installed binary from a `mktemp -d` folder, so the source tree cannot be imported. It checks `--version` and the same three non-empty files as CI's smoke step. No voice download (D-487).
- `github-release` uses `--verify-tag`, attaches `dist/*`, notes from the changelog (D-486). `from-pypi` on three systems retries 20 x 30 s with `--refresh` (D-485).
- Branch run 43538690796 on b1db322: build + all three installed-wheel jobs green; the Windows log shows `cpython-3.12.16-windows-x86_64-none`, `sci2audio 0.0.1.dev0`, `smoke test passed`. (So Windows checkout gives LF for `.python-version` and `__init__.py`; no CRLF problem.)
- Tools, run by me: zizmor 1.32.0 `--offline .github/workflows`: no findings (pedantic persona: only the low `concurrency-limits` help, not required). actionlint 1.7.7 with shellcheck 0.10.0 on release.yml: clean. shellcheck on `scripts/release_smoke.sh`: clean.

## F1 (fix needed): the "changelog has a section for this version" guard does not hold for 1.0.0

The awk prints from `## [1.0.0]` until the next `## [` heading. 1.0.0 is the last (oldest) section, so there is no next heading and the awk runs to the end of the file, which in Keep a Changelog form holds the link definitions (`[unreleased]: …`, `[1.0.0]: …`). Tried with a sample changelog: the notes come out as the section plus both link lines. Consequences:
1. `test -s notes.md` passes even when the 1.0.0 section is empty, because the link lines (or a single blank line) make the file non-empty. The PR body says the job "fails if that section is empty"; today it would not.
2. The release notes carry the link-definition lines (invisible on GitHub, but not the section).

Fix: also stop at a link-definition line (e.g. `inside && /^\[[^]]+\]: / { exit }`), and replace `test -s` with a check for at least one non-blank line (e.g. `grep -q '[^[:space:]]' "$RUNNER_TEMP/notes.md"`). Check it locally against R2's CHANGELOG.md and against a copy where the 1.0.0 section is empty (must fail), and say so in the PR body.

## Not required (no issue needed)

- Workflow `concurrency` (zizmor pedantic, low): two release tags at once is not a real case here.

## CI on f23624e at review time

Green: lint and layers, licences, security, tests ubuntu/macos, CodeQL. Still running: tests (windows-latest), browser (Linux, Chromium). Merge waits for "CI passed".
