# Review PR #635, round 2 (final): installers + workflows + audio-only FFmpeg

Reviewed head 2dccc2a (fix commit b85201d, main merge 7e8c734 for the CHANGELOG conflict with #655, and two F2 corrections 6066504 and 2dccc2a forced by the installer runs; accepted, since the extra commits were CI-driven and a merge was required). Verdict: **approved and squash-merged** as bed21bd onto main 28d65ed (already merged into the branch; the squash's diff is identical to `git diff 28d65ed 2dccc2a`). #215 and #13 closed by the merge.

## Round 1 findings
- F1 fixed: `DisableDirPage=yes`, `PrivilegesRequiredOverridesAllowed` removed, `[UninstallDelete] {app}` removed; the Windows smoke installs without `/CURRENTUSER` (per-user is now the only mode) and still checks the folder is gone and the voice files, audiobooks and log stay.
- F2 fixed: the spec drops the top-level copies of libraries that also sit in a package's own library folder (torch/lib, `*.libs`, `.dylibs`) on Linux and Windows (on macOS PyInstaller's @rpath needs them, and there the nested ones are symlinks, so the duplicate check passes); `torch/bin` keeps only `torch_shm_manager`. `check_bundle` now fails on identical files ≥ 1 MB and on extra torch/bin programs. Sizes: dmg 384→381 MB, setup.exe 340→277 MB, AppImage 443→429 MB, Linux installed 1724→1217 MB.
- F3 fixed and verified: type2-runtime commit dd6cebed is tag 20251108; its `scripts/common/install-dependencies.sh` builds fuse-3.15.0.tar.xz with SHA-256 70589cfd… (the same pin) plus its `patches/libfuse/mount.c.diff`, and squashfuse 0.5.2 (tag 0.5.2 = 775b4cc). All three go into the sources tar, pinned, with README/SOURCE/THIRD_PARTY lines.
- F4 fixed: `packaging/licenses/` espeakng-loader (MIT; upstream added its LICENSE after 0.2.4, noted in the file), clr-loader (MIT), winpthreads; copied into `licenses/` and required by `check_bundle` (Windows all three, elsewhere espeakng-loader).
- T1 fixed; N1 fixed.

## Final-round checks
- Hand mutants (`plans/b635-review/mut.py`, 32 round 1 + 16 new for F1–F4 and the spec), baseline 87 passed on tests/unit/test_installers.py: **46 killed, 1 skipped** (its target line was removed by F1), **1 survives**: the spec's `top_level` forced True on macOS. Not unit-testable without PyInstaller on macOS; the macOS installer smoke (both audiobooks speak, so torch loads) is the test for it. Accepted.
- Three systems on 2dccc2a: tests ubuntu/macos/windows, CI passed, both Chromium legs success. ci:installers run 44525393781 on 2dccc2a: ffmpeg ×3, source archive, build ×3, installed on ubuntu-22.04, ubuntu-24.04, macOS, Windows all success. Labels ci:installers removed after merge.
- Nightly seeds: not applicable.
