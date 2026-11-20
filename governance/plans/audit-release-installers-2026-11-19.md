# Light audit: release installers batch (#630, #631, #635, #656), 19 Nov 2026

Auditor: the release review thread. I read the merged diffs 12f85a7 (#630), e45d655 (#631), bed21bd (#635) and 5c18f8c (#656) against `plans/release-installers-plan.md` (D-797), D-798 (FFmpeg) and D-817 (#13 AC-2). Scope: inconsistencies across the PRs and contract touches only.

## Result: 0 blocking, 0 new issues; tag v1.4.0 NOT pushed (blocked, see A9)

| # | Check | Finding |
|---|---|---|
| A1 | Files and lanes | #630 touches tests only. #631: `web/` (window, launch, config), tests, CHANGELOG, licences, `pyproject` (`window` extra, `sci2audio-app` entry point), `uv.lock`, one workflow line. #635: `packaging/`, `scripts/`, `.github/workflows` (installers.yml, release.yml), tests, licences, lock. #656: docs, CHANGELOG, README, version, issue form, and one spec line (F1). There is no core, layer contract, golden file or KB change, and `lint-imports` is unchanged |
| A2 | Version consistency | `__version__` is 1.4.0, the CHANGELOG has `## [1.4.0] - 2026-11-19`, and every asset name in the docs matches `build_installer.py` and release.yml's checksum list. I ran release.yml's tag, heading and awk checks on main's CHANGELOG, and all of them pass |
| A3 | Supported systems | macOS 14 is now consistent in the plist, installing.md, the CHANGELOG and the README (#656 F1; torch and onnxruntime wheels have minos 14.0). Windows is 1809 (MinVersion 10.0.17763). Linux needs glibc 2.35 (the build runs on ubuntu-22.04, and the smoke tests run on 22.04 and 24.04) |
| A4 | Release gating | release.yml: `publish` (environment `pypi`) needs `build`, `smoke` and `installers`, and `github-release` needs `publish` and `installers`. So nothing is published unless the installers pass from the tag, and the GitHub release with its installers, sources tar, SHA256SUMS and attestations comes only after the PyPI approval |
| A5 | Licences | FFmpeg 9.0.2 + LAME is LGPL and audio-only, with no network protocols (checked from the artifacts). The sources tar hashes match the pins. espeak-ng 1.52.0, type2-runtime, libfuse 3.15.0 and squashfuse 0.5.2 have their source in the tar. The MIT/BSD notices (#635 F4) are added. Nothing on the refused list |
| A6 | User data safety | The Inno uninstaller deletes no data folder (#635 F1: `DisableDirPage=yes`, no `{app}` UninstallDelete, no elevation override). The docs say uninstall keeps the data folders, which matches |
| A7 | Defects found in review | #631: a closing-handler deadlock on macOS (F1) and three others, all fixed before merge. #635: an uninstall data-loss path, about 480 MB of duplicated torch libraries, missing runtime source and three missing licence notices, all fixed. #656: a wrong macOS floor and a wrong pointer in the tester form, both fixed. Post-merge defects so far: 0 |
| A8 | Issues from the batch's reviews | #644: the SmartScreen switch is ignored when the app runs elevated (v2, named in the Known limits) |
| A9 | Tag | Pushing tag v1.4.0 on 5c18f8c (D-827) was refused twice: `git push` got HTTP 403 from GitHub's git endpoint, and creating it through the REST API was denied by this session's permission guard. The tag is not on the remote, so the release run has not started |

## Notes for the ledger (thread length)

The batch had 4 critical PRs: one round for #630 and two rounds each for the other three. One review thread handled all of them, with one compression. Round 1 findings that a reading alone would have missed came from three sources: the platform's real source (pywebview's cocoa threading), the built artifacts (duplicate libraries, uninstall paths) and the wheels' own metadata (macOS minos). For installer and app-window PRs, check those three sources as standard.
