# Review PR #656 round 2 (final): approved and merged

Reviewer: release review thread, 19 Nov 2026 14:10Z. Reviewed head c5edccf (one fix commit on d9c4b1f; main bed21bd already merged in, unchanged since).

## Round 1 findings

- **F1 macOS floor: fixed.** `packaging/sci2audio.spec` LSMinimumSystemVersion is now 14.0 (comment names the macosx_14_0_arm64 wheels). The CHANGELOG `[1.4.0]` and docs/installing.md download tables say "macOS 14 (Sonoma) or newer", and README Installing says "macOS 14 or newer". The new test `test_the_mac_app_asks_for_the_macos_its_libraries_were_built_for` pins the spec and both docs.
- **F2 tester form: fixed.** It now points to `sci2audio --version` and to the start-up log's first line. `window.py` logs "sci2audio %s starting on %s" first, after the formatter's timestamp and level. The form still parses with `yaml.safe_load`.

## Mutation

The fix is the only logic-like change, so I probed it with two hand mutants. Spec 14.0 → 13.0 was killed, and installing.md "macOS 14 (Sonoma) or newer" → "macOS 13 or newer" was killed. The new test passes on c5edccf.

## CI on c5edccf (verified via check-runs)

- `CI passed`, plus tests on ubuntu, macOS and windows (ci:full).
- Browser Chromium 1/2 and 2/2.
- ZAP, licences, lint and layers, security, CodeQL.
- Installers run 44531072121 (pull_request, head c5edccf): build ×3, ffmpeg ×3, source archive, installed on macos, windows, ubuntu-22.04 and ubuntu-24.04.

All of these passed.

## Merge

- Squash-merged pinned to c5edccf as **5c18f8c** on main bed21bd, which was green on three systems.
- No closing keyword: #215 and #13 were already closed by #635.
- Tag v1.4.0 has not been pushed; it waits for the coordinator's go.
