# Review PR #656 round 1 (release 1.4.0: version, CHANGELOG, install guide, tester form)

Reviewer: release review thread, 19 Nov 2026. Head d9c4b1f (main bed21bd merged in). Diff against main: 7 files, +207/−9, no code besides `__version__`.

Verdict: **changes requested** (2 findings).

## Checked and correct

- Version 1.4.0 in `src/sci2audio/__init__.py`; release.yml's tag check (`test "$TAG" = "v$version"`) and dated-heading grep pass on this CHANGELOG (run locally with the workflow's own commands).
- release.yml's awk extraction of `## [1.4.0]` gives 131 lines and stops at `## [1.0.0]`; the new `###` subheadings do not end it early. Link refs `[Unreleased]` and `[1.4.0]` correct.
- Asset names in docs and notes match `scripts/build_installer.py` and release.yml (`-macos-arm64.dmg`, `-windows-x64-setup.exe`, `-linux-x86_64.AppImage`, `-sources.tar`).
- Sizes match round 2 of #635 (381/277/429 MB). Voice sizes from `download_plan()`: en 354.7 MB, de 327.8 MB ("about 355" and "about 330").
- Folder table matches platformdirs (data, roaming config, log, cache) and the Windows smoke path `%LOCALAPPDATA%\sci2audio\Logs\app.log`; Documents/sci2audio matches `web/config.py`.
- Windows MinVersion 10.0.17763 = 1809. Linux floor glibc 2.35 = ubuntu-22.04 build runner (Debian 12 2.36, Fedora 36 2.35).
- Idle stop 15 min (`launch.IDLE_STOP`), WebView2 fallback to the browser with Quit, uninstall keeps data (no UninstallDelete since #635 round 2), `--appimage-extract-and-run`, `licenses` folder, CLI paths match installers.yml.
- Known-limits SmartScreen text matches #644 / D-817.
- Labels `inbox` and `tester-report` exist; the issue form is valid YAML with the fields GitHub needs.
- `packaging/tools.env` exists (release checklist).

## Findings

**F1 (must fix): macOS 12 is not a supported floor; the bundled PyTorch needs macOS 14.**
`uv.lock` has torch 2.15.0 only as `macosx_14_0_arm64` wheels (onnxruntime 1.31.1 too). I downloaded `torch-2.15.0-cp312-cp312-macosx_14_0_arm64.whl` and read the Mach-O headers: `libc10.dylib` and `_C.cpython-312-darwin.so` have `LC_BUILD_VERSION minos 14.0`. On macOS 12 or 13 the app would open and then fail as soon as torch loads. Fix:
- `packaging/sci2audio.spec`: `LSMinimumSystemVersion` "12.0" → "14.0" (Finder then refuses with the system's own "needs a newer macOS" message).
- `docs/installing.md` and CHANGELOG `[1.4.0]` download table: "macOS 14 (Sonoma) or newer".
- README "Installing": say macOS 14 or newer for Apple-chip Macs (the uv install hits the same wheels).

**F2 (must fix): the tester form says the version is on the privacy page; it is not.**
`privacy.html` has no version (checked every template variable). Point to what exists: the first line of the start-up log (`sci2audio 1.4.0 starting on ...`) and `sci2audio --version`, or just ask for the installer's file name.

## Next round

F1 touches `packaging/sci2audio.spec`, so round 2 (final) needs, on the fix head: Linux CI, the `ci:full` three-system run and a `ci:installers` run (the macOS installer smoke covers the plist). Mutation: no logic changed; nothing to mutate beyond the version string, which release.yml's tag check guards.
