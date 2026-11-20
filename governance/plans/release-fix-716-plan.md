# Plan: release-fix-716, the macOS app bundle starts the command line (#716)

Thread: release-fix-716, priority-bug implementation thread beside the lanes (D-732), infra lane files, Opus 5.5. Critical (packaging and release workflow, risk:high): **waits for the coordinator's approval before any code.**

Sources read: `governance/rules/implementation.yaml` (PLAN-01), CLAUDE.md (rule 8, the critical list), `.claude/rules/tests.md` (installer smoke test row), Issue #716, `packaging/sci2audio.spec`, `packaging/app.py`, `packaging/linux/AppRun`, `packaging/windows/sci2audio.iss`, `scripts/build_installer.py`, `scripts/installer_smoke.py`, `tests/unit/test_installers.py`, `.github/workflows/release.yml` and `installers.yml` (the smoke test lives there; release.yml calls it), `docs/installing.md`, `docs/release-checklist.md`, `CHANGELOG.md`, `gh release view v1.4.0`, D-829, D-830, D-702 g, D-703 b, D-732, D-863 (pending), the "release branches" ruleset (27255463) and the `pypi` environment; PyInstaller 6.22.3's `building/osx.py` and `building/api.py`.

## 1. Cause (confirmed in PyInstaller's source and the shipped Info.plist)

PyInstaller's `BUNDLE` writes `CFBundleExecutable` from the first `EXECUTABLE` entry of the TOC it gets and lets `info_plist` override it; the spec passes the COLLECT of both programs and never names the main one, and in the built TOC the command line came first. The installed `/Applications/sci2audio.app/Contents/Info.plist` (1.4.0) has `CFBundleExecutable = sci2audio`.

**Also found, the same mechanism:** the plist has `LSBackgroundOnly = true`. COLLECT inherits `console` from the *last* EXE it gets (`cli_exe`, `console=True`), BUNDLE inherits it from COLLECT, and `console` makes BUNDLE write `LSBackgroundOnly`. It does not stop the window today (pywebview turns the process into a regular app; `lsappinfo` reports it as Foreground), but it declares the app a background agent to Launch Services. The fix sets it to `false` explicitly (one line, §2 a). The coordinator may strike this item; it is not needed for #716's acceptance criteria.

**Checked by hand on this Mac (20 Nov, 23:53 local):** a copy of the installed 1.4.0 bundle with only `CFBundleExecutable` changed to `sci2audio-app` (a test bundle id, re-signed ad hoc), started with `open -a <copy>`, wrote "running in a window on http://127.0.0.1:…" to `~/Library/Logs/sci2audio/app.log` after 5 s and opened the window; `osascript -e 'tell application id "…" to quit'` stopped it within 1 s. The copy was unregistered from Launch Services and deleted. This is the behaviour the new smoke step checks.

Windows and Linux start the right program: the Start menu, desktop and post-install entries of `sci2audio.iss` point at `sci2audio-app.exe`; `AppRun` with no arguments runs `sci2audio-app`, and the Linux smoke test starts the AppImage itself with no arguments (as a person does). Their smoke tests stay as they are; a unit test pins the launcher targets (§3, test 7).

## 2. PR 1, to `main` (lane:infra, risk:high, ci:installers)

Branch `claude/release-fix-716-a4c60d` from current main. Title `release: the macOS app bundle opens the window, not the command line (#716)`. Body says "part of #716" (the patch release is #716's last criterion, PR 2), the section `## Tests promised in the plan`, licence note "none", risk, follow-ups.

a) **`packaging/sci2audio.spec`**: the BUNDLE's `info_plist` gains `"CFBundleExecutable": "sci2audio-app"` (with a comment: PyInstaller would take the first program of the folder, #716) and `"LSBackgroundOnly": False`. Both programs stay in `Contents/MacOS`; `sci2audio` stays the command line docs/installing.md names.

b) **`scripts/build_installer.py`**: `check_app(app) -> list[str]`, run by `macos_dmg` before signing; the build stops (as `check_bundle` does) when the built `Contents/Info.plist` does not name `sci2audio-app` as `CFBundleExecutable`, declares `LSBackgroundOnly`, or when `Contents/MacOS/sci2audio-app` or `Contents/MacOS/sci2audio` is missing. So every installers run (PR label, release) checks the real built plist, and the unit test (§3, test 1) checks the spec without PyInstaller.

c) **`scripts/installer_smoke.py`**: a new action `launch BUNDLE [--log FILE] [--timeout 30]` (macOS, standard library only): reads the bundle id from the bundle's `Info.plist` (plistlib), notes the size of `app.log` (default `~/Library/Logs/sci2audio/app.log`), runs `open -a BUNDLE` with no arguments (Launch Services, as Finder does), waits up to 30 s for a line with "running in a window" written **after** that offset (the earlier window self test writes the same line, so only new bytes count), then quits the app with `osascript -e 'tell application id "<id>" to quit'` and waits up to 30 s for it to stop (`pgrep -f <bundle>/Contents/MacOS/`, killed and reported as a failure if it stays). Fails with the new log lines (or "no new line") in the message.

d) **`.github/workflows/installers.yml`**, smoke job: the macOS install step also outputs `bundle=$HOME/Applications/sci2audio.app`; a new step "The app starts from Finder, through Launch Services (macOS)" runs `uv run --no-project python scripts/installer_smoke.py launch "$BUNDLE"` before the window self test. Nothing in release.yml changes (it calls installers.yml); the Windows and Linux steps stay.

e) **Docs**: `docs/installing.md`, macOS section: a line for 1.4.0 ("If sci2audio 1.4.0 does not open from Finder: start it once with `open /Applications/sci2audio.app/Contents/MacOS/sci2audio-app` in Terminal, or use `…/sci2audio ui`; 1.4.1 fixes this, #716"). `docs/release-checklist.md`, the "First start of the downloaded installers" item: the start is a double-click in Finder (macOS) and the Start menu or desktop entry in Explorer (Windows), never an executable by path (#716). `CHANGELOG.md`, Unreleased → Fixed: "The macOS app opens its window again when started from Finder or the Dock; 1.4.0 started the command line, which quit at once without a window (#716)."

f) **Ledger** `governance/ledger/prs/pr-<N>.yaml` like pr-707.yaml.

**Local build:** I try `scripts/build_installer.py` once on this Mac in the background (it needs the FFmpeg build from `packaging/ffmpeg/build.sh`, which downloads its pinned sources, and `uv sync --extra window --group installer` in this worktree). If it builds, I install the DMG to `~/Applications` like the workflow, run `installer_smoke.py launch` on it and record the result in the PR body; if the build fails for a local reason I record that and the hand check of §1. Either way the PR gets the **`ci:installers`** label at opening, so the new step runs on the hosted macOS runner before review (installers.yml does not run on a PR without it). I ask the coordinator if adding that label is not mine to do.

Size: about 40 lines of spec/script/workflow, 120 of tests, 6 of docs.

## 3. Tests promised in the plan (all in the fast suite, no build, no network)

1. `tests/unit/test_installers.py::test_the_mac_app_bundle_starts_the_app_not_the_command_line`: runs `packaging/sci2audio.spec` with stand-ins for PyInstaller's `Analysis`, `PYZ`, `EXE`, `COLLECT`, `BUNDLE` and its hooks, `sys.platform` set to `darwin`; asserts `info_plist["CFBundleExecutable"] == "sci2audio-app"`, `info_plist["LSBackgroundOnly"] is False`, and that the COLLECT passed to BUNDLE holds the programs `sci2audio-app` and `sci2audio`. Fails on today's spec.
2. `tests/unit/test_installers.py::test_a_built_mac_app_with_the_app_as_main_program_passes`: `check_app` on a minimal `sci2audio.app` in tmp_path (plist and the two files) returns no problems.
3. `tests/unit/test_installers.py::test_a_built_mac_app_that_starts_the_command_line_fails_the_build`: same with `CFBundleExecutable = sci2audio`: one problem naming #716.
4. `tests/unit/test_installers.py::test_a_built_mac_app_declared_background_only_fails_the_build`
5. `tests/unit/test_installers.py::test_a_built_mac_app_without_the_command_line_fails_the_build`
6. `tests/unit/test_installers.py::test_the_launch_check_counts_only_lines_written_after_its_start`: an `app.log` with an old "running in a window" line before the offset and none after: not started; a new line after it: started.
7. `tests/unit/test_installers.py::test_the_launch_check_fails_when_the_window_line_never_comes`: `smoke_launch` with `open`, `osascript` and `pgrep` replaced by fakes and a 0.2 s timeout raises `Failed` with "no start line"; with a fake `open` that appends the line, it passes and quits the app by its bundle id.
8. `tests/unit/test_installers.py::test_the_launch_check_starts_the_bundle_through_launch_services`: the command it runs is `["open", "-a", <bundle>]` with no arguments for the program (the CI guard against going back to an executable by path).
9. `tests/unit/test_installers.py::test_the_windows_entries_and_the_appimage_start_the_app`: `sci2audio.iss` [Icons]/[Run] entries and `AppRun`'s no-argument branch name `sci2audio-app`.
10. `tests/unit/test_installers.py::test_the_macos_smoke_test_starts_the_bundle_through_launch_services`: installers.yml's smoke job has a macOS step that runs `installer_smoke.py launch` on the bundle.

The real proof is the `installed (macos-latest)` job of the `ci:installers` run on PR 1 and the release run; neither is a pytest node.

Checks before opening: `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser" -k "not espeak"`, `uv run zizmor --offline .github/workflows`.

## 4. PR 2, the patch release 1.4.1 (proposal; the coordinator decides before I start)

Route: a `release/1.4` branch from tag v1.4.0, PR 1's squash commit cherry-picked, version 1.4.1, released by the existing tag workflow. Nothing else goes into 1.4.1. Between v1.4.0 (5c18f8c) and main, `packaging/`, `scripts/build_installer.py`, `scripts/installer_smoke.py`, `installers.yml`, `release.yml` and the two docs are identical; only `tests/unit/test_installers.py` (3 lines) and `CHANGELOG.md` differ, so the cherry-pick needs at most a CHANGELOG hand merge.

| Step | Who |
|---|---|
| 1. Create `release/1.4` at 5c18f8c (the commit of tag v1.4.0). The "release branches" ruleset (27255463, `refs/heads/release/*`) protects it at creation: squash only, linear, no deletion or force-push, `CI passed` required. | **Owner** (or the coordinator, if it judges creating a ref at a released commit part of its grant); never this thread (CLAUDE.md: never push to a release branch) |
| 2. Branch `claude/release-1.4.1` from `release/1.4`; cherry-pick PR 1's squash commit with `-x`; `__version__ = "1.4.1"`; CHANGELOG `## [1.4.1] - <release date>` with the one Fixed line and the Download table and first-start lines of 1.4.0 with the 1.4.1 file names (release.yml makes the release page from this section and checks it is dated); `docs/installing.md`'s file names 1.4.0 → 1.4.1 and the workaround line kept for people still on 1.4.0. PR into `release/1.4`, title `release: sci2audio 1.4.1, the macOS app opens its window (#716)`, `Closes #716`, labels lane:infra, risk:high, ci:installers. | Thread |
| 3. Linux CI (automatic for PRs into release/*, D-702 g); review in a separate thread; `ci:full` three-system run on the final round (D-703 b); the `ci:installers` run green on all four runners. | Thread (fix commits), review thread, coordinator (`ci:full` word) |
| 4. Squash-merge into `release/1.4`, pinned to the reviewed head. | Review thread on the coordinator's go |
| 5. Push tag `v1.4.1` on the merged release/1.4 head (as Colin pushed v1.4.0, D-829). | **Owner** |
| 6. Approve the `pypi` environment deployment (required reviewer dubidu22; its tag policy `v*` allows the tag). The workflow then publishes to PyPI and **creates the GitHub release itself** (`gh release create` from the CHANGELOG section, with installers, SHA256SUMS and attestations). | **Owner** |
| 7. Release checklist's first start: download the 1.4.1 DMG from the release page and **double-click** it in Finder on a real Mac (and the Windows setup on a PC, optional for a tester release). | **Owner** |
| 8. Forward to main: a small docs PR (thread) that moves the Unreleased Fixed line into a `[1.4.1]` section and updates docs/installing.md's file names to 1.4.1, so main's changelog and docs match the release. | Thread, reviewed |

PyPI: the 1.4.1 wheel differs from 1.4.0 only in its version (the fix is in packaging). I propose publishing it anyway: release.yml's GitHub release job needs the PyPI job, `uv tool install sci2audio` and the installers then name the same version, and changing the workflow to skip PyPI would be a second critical change. Alternative for the coordinator: none needed unless Colin prefers no PyPI 1.4.1.

Open choices for the coordinator: (1) keep or strike `LSBackgroundOnly = false` (§1); (2) whether the thread may add `ci:installers` to PR 1 and PR 2 itself; (3) the patch route of §4 and who creates `release/1.4`.

## 5. Out of scope (Issues if the coordinator wants them)

- A quit by Apple Event (Dock → Quit, `osascript … quit`) stops the app without its "stopped" log line (seen in §1); harmless, but the log then never says the app ended.
- Signing and notarisation (#637) stay as they are; the Gatekeeper steps of docs/installing.md still apply.
