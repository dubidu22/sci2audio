# Review PR #718, round 1 (release fix #716)

Thread: review-infra-b-i2 (Opus 5.5), the infra lane's review thread. Head reviewed: 4ae2227. Date: 2026-11-21.
**Critical: yes** (CRIT-01: packaging and the installers workflow, `.github/workflows/installers.yml`; labels `bug`, `lane:infra`, `risk:high`, `ci:installers`). Plan `plans/release-fix-716-plan.md`, approved as D-865 (LSBackgroundOnly false kept; the thread adds `ci:installers`; the v1.4.1 patch is PR 2).

**Verdict: approved** (0 must-fix, 0 should-fix, 4 notes).

## Verified

- Scope: 8 files, all in the plan: `packaging/sci2audio.spec`, `scripts/build_installer.py`, `scripts/installer_smoke.py`, `.github/workflows/installers.yml`, `docs/installing.md`, `docs/release-checklist.md`, `CHANGELOG.md` and `tests/unit/test_installers.py`. There is no change to `release.yml`, which calls `installers.yml`. The base is `main` 9ad6d11, after the merge commit d85cf52. The body says "Part of #716", because the patch release is PR 2.
- (1) The spec: the BUNDLE `info_plist` sets `"CFBundleExecutable": "sci2audio-app"` and `"LSBackgroundOnly": False`, and its comment gives the why.
  - In PyInstaller's `building/osx.py` (the uv cache copy), the generated keys, `LSBackgroundOnly = True` among them when `console` is set, come first. `info_plist_dict.update(self.info_plist)` then lets the spec's values win.
  - Test 1 runs the real spec with stand-ins on `darwin`. The COLLECT passed to BUNDLE still holds both programs, `sci2audio` and `sci2audio-app`.
- (2) `build_installer.check_app()` reads the built `Contents/Info.plist` and reports three things: a main program other than `sci2audio-app`, a truthy `LSBackgroundOnly`, and a missing `Contents/MacOS/sci2audio-app` or `sci2audio`. `macos_dmg()` calls it first, before `codesign`, and raises `SystemExit` with the problems. Tests 2 to 5 pin each case.
- (3) `installer_smoke.launch`:
  - It runs `["/usr/bin/open", "-a", <bundle>]` with nothing else (test 8).
  - It notes `app.log`'s size first and reads only the bytes after that offset, with `\r\n` normalised (test 6). The Windows CRLF case is pinned with bytes.
  - It waits for the start line with a 30 s default timeout, and fails with "no start line … new lines: …" or "open -a did not return within 60 s" (test 7).
  - It quits by bundle id with `osascript … to quit`, and only while `pgrep` finds the bundle's program, since an Apple Event to a stopped app would start it. If the app is still running after the timeout it runs `pkill` and fails.
  - It uses the standard library only (`plistlib`, `subprocess`, `time`).
  - **Hosted-runner evidence**, installers run 44843463064 on 4ae2227, job `installed (macos-latest)` (136666260936), step "The app starts from Finder, through Launch Services (macOS)":
    - `00:50:49.52Z ##[group]Run uv run --no-project python scripts/installer_smoke.py launch "$BUNDLE"` with `BUNDLE: /Users/runner/Applications/sci2audio.app`;
    - `00:50:49.96Z installer_smoke: $ open -a /Users/runner/Applications/sci2audio.app`;
    - `00:50:55.92Z installer_smoke: Launch Services started the app in a window, and it quit`.
    - The window self test follows at 00:50:56 ("the window opened the interface on 127.0.0.1", 00:51:02).
    - All 12 jobs of that run succeeded: ffmpeg ×3, source archive, build ×3, installed on ubuntu-22.04, ubuntu-24.04, windows-latest and macos-latest. So `check_app` passed on the built macOS bundle too.
  - The PR body also reports the local check: the shipped 1.4.0 bundle fails the launch check after 30 s, and the built one passes.
- (4) `installers.yml`: the macOS install step also writes `bundle=$HOME/Applications/sci2audio.app`, and the new macOS-only step passes it through `env:` (no `${{ }}` in `run:`) before the window self test. Test 10 pins the step. `uv run zizmor --offline .github/workflows`: no findings.
- (5) Promised tests:
  - The ten node IDs exist, and the body lists them under the exact heading. Governance pr checks is green.
  - `tests/unit/test_installers.py` gives 98 passed.
  - With `main`'s spec, test 1 fails with `KeyError: 'CFBundleExecutable'`; I checked by swapping the spec in the review worktree and then restoring it.
  - Test 9 pins the three `sci2audio.iss` entries (Start menu, desktop, post-install) on `{app}\sci2audio-app.exe` and AppRun's no-argument branch on `sci2audio-app`.
- (6) Docs:
  - `docs/installing.md` gains the 1.4.0 workaround line (`open …/MacOS/sci2audio-app` or `…/sci2audio ui`), as #716's criterion asks.
  - The release-checklist item says the first start is a double-click in Finder and the Start menu or desktop entry in Explorer, never a program by its path.
  - `CHANGELOG.md` has the Unreleased → Fixed line.
- (7) Local run in a fresh `/tmp/review-718` at 4ae2227:
  - ruff check: clean. ruff format --check: 389 files formatted.
  - lint-imports: 3 kept. deptry src: no issues. zizmor: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8734 passed, 2 failed, 6 skipped, 6 xfailed; see N4.
- CI: the three-system run on 4ae2227 is green per the coordinator. The Linux checks and governance pr checks are green.
- Licences: none.

## Findings

### Notes
- N1: `installers.yml:10`: the reflow of the header comment left one line of 165 characters. This is cosmetic; it can be rewrapped in PR 2 or later.
- N2: `installer_smoke.quit_app` runs `osascript` with `timeout=60` and does not catch `TimeoutExpired`. A hung `osascript` ends the step with a traceback instead of a `Failed` message. It still fails, so no change is needed now.
- N3: test 10 pins the launch step's content but not its place before the window self test. The run log shows that order, and the plan asks for it. One `index()` comparison in the test would pin it.
- N4: the local fast suite had two failures, both in files this PR does not touch: `tests/unit/test_extraction_pdf_process.py::test_the_watch_stops_a_child_that_grows_past_the_limit` and `tests/unit/test_textprep_utterances.py::test_a_long_text_without_a_full_stop_is_cut_in_linear_time`.
  - The machine's load average was 78 at the time, with other threads running. Run alone, both pass (2 passed in 2.1 s). CI passed on the same head.
  - Both are timing-sensitive. They may be the two unnamed failures that #712's author saw in a local run. If either fails again without load, D-374 applies.

Verdict: approved. Merge on the coordinator's go, pinned to 4ae2227. The three-system run and the `ci:installers` run on that head are green. Merge `main` in first if it has moved (critical PR).
