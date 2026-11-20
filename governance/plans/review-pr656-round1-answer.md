# PR #656 round 1: what was fixed

Fix commit `c5edccf` on `docs/release-1.4.0`, one commit.

- F1 (macOS 14):
  - `packaging/sci2audio.spec`: `LSMinimumSystemVersion` is now "14.0", with a comment naming the macosx_14_0_arm64 wheels.
  - CHANGELOG [1.4.0] download table and docs/installing.md: "macOS 14 (Sonoma) or newer".
  - README Installing: "Macs with Apple chips (macOS 14 or newer)".
  - New test `test_the_mac_app_asks_for_the_macos_its_libraries_were_built_for` pins the spec and both documents.
  - No other macOS 12 or 13 mention is left (grep over docs, README, CHANGELOG and packaging).
- F2 (tester form): the version field's description now names `sci2audio --version` and the first line of the app's start-up log ("sci2audio 1.4.0 starting on ...", with docs/installing.md for where the log is). It no longer names the privacy page.

Checks on c5edccf:
- CI with ci:full: tests on macOS, Windows and Ubuntu, both Chromium legs, ZAP.
- ci:installers run 44531072121: build and installed on ubuntu-22.04, ubuntu-24.04, macOS and Windows. The dmg is 381 MB, now with version 1.4.0.
- Locally: test_installers 88 passed, ruff clean.
