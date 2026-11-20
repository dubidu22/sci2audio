# Review PR #635, round 1: installers + workflows + audio-only FFmpeg (#215, #13; critical)

Reviewer: installers release review thread (Opus high), 19 Nov 2026. Reviewed head 7a60fc1, base e45d655 (main merged in). Main is now fb48c1c (#621, #645, #647); `git merge-tree` clean, no shared files besides CHANGELOG.md.

Verdict: **changes requested**: F1–F4, T1 (11 tests), N1. One fix commit; then Linux CI, ci:full and ci:installers on the fix head (round 2 is final).

## What holds (checked)

- **FFmpeg is audio-only LGPL** (artifacts of run 44507750405, all three systems): `-L` prints LGPL-2.1-or-later; configuration has no `--enable-gpl`, `--enable-nonfree` or `--enable-version3`; `--disable-network`, protocols `file,pipe` only (`-protocols`); Linux binary links only libc, libm, libz; Windows ffmpeg.exe imports system DLLs only (static MinGW). The fast suite runs against it on all three systems before freezing.
- **Source archive matches the build:** the `sources` artifact holds ffmpeg-9.0.2.tar.xz, lame-3.100.tar.gz and espeak-ng-1.52.0.tar with exactly the SHA-256 of `sources.env`, plus the same `build.sh`. Commit 4870adf is tag 1.52.0 (`git ls-remote`), and espeakng-loader 0.2.4's library reports `espeak_Info` = 1.52.0. A release build reads no FFmpeg cache.
- **No voices bundled:** AppImage extracted: no .pt/.pth/.safetensors/.onnx, no en_core_web_* (only espeak-ng's own phoneme data). imageio_ffmpeg's binaries are absent; `licenses/` holds LICENSE, THIRD_PARTY_LICENSES.md, Python, FFmpeg, LAME, python-packages.txt, SOURCE.txt.
- **Workflow security:** `contents: read`; every action pinned to a SHA; `persist-credentials: false`; no secrets; PR runs only from this repository and only with the `ci:installers` label; no `${{ }}` of PR-controlled text in a `run:` (step outputs and the tag go through `env:`); uploads scoped to `ffmpeg-out/`, `sources-out/`, `installers/` with 7-day retention; tool downloads checked by SHA-256 (a mismatch fails the step under `bash -e`); the release `github-release` job alone gets `contents: write`, `id-token: write`, `attestations: write`; `publish` needs `installers`.
- **Linux app mode:** Quit stops the installed AppImage (stand-in browser and Playwright step); idle stop is covered by PR 1's tests.
- **Record of earlier failures matches the diff:** runs 44485080787 (macOS self test hang → `run_js` in #631; Windows WebView2 Playwright step) and 44489395707, 44493735824, 44494698588, 44499053555 (all only the Windows WebView2 Playwright step), removed by 7a60fc1 per D-817/#654.

## Findings

**F1 (blocker, deletes user files): the Windows uninstaller can delete a person's Documents\sci2audio.** `sci2audio.iss` shows the folder page (Inno's `DisableDirPage=auto` shows it on a first install) and, with the default `AppendDefaultDirName=yes`, a person who browses to Documents gets `Documents\sci2audio`, the very folder sci2audio keeps audiobooks and projects in (`default_output_folder`, `default_projects_root`). `[UninstallDelete] Type: filesandordirs; Name: "{app}"` then deletes that whole folder on uninstall; a typed existing folder (e.g. `C:\Users\me\Documents`) is deleted the same way. `PrivilegesRequiredOverridesAllowed=dialog` also lets the installer run elevated for all users, against the plan's per-user/no-admin install, and the post-install launch would then start the app elevated (where WebView2 ignores the SmartScreen switch, #644).
Fix: `DisableDirPage=yes` (always `{autopf}\sci2audio`, i.e. `%LOCALAPPDATA%\Programs\sci2audio`); remove `PrivilegesRequiredOverridesAllowed`; remove the `[UninstallDelete]` entry for `{app}` (the uninstaller removes every file it installed and then the empty folder; if anything must go, name it exactly). Tests in test_installers.py: `DisableDirPage=yes`, no `PrivilegesRequiredOverridesAllowed`, and no `filesandordirs` entry whose Name is `{app}` or any folder above or equal to it. The Windows smoke uninstall step keeps checking the folder is gone.

**F2 (size): the frozen folder holds torch's libraries twice and torch's test programs.** In the Linux bundle `_internal/libtorch_cpu.so` (440 MB), `libtorch_python.so` (33 MB), `libc10.so`, `libgomp.so.1` are regular-file copies of `_internal/torch/lib/...` (≈ 475 MB), and `torch/bin` (53 MB: `test_jit`, `test_api`, `protoc` twice) is never used at run time. The AppImage's squashfs deduplicates, but the dmg and setup.exe do not, and every installed copy carries ≈ 530 MB extra.
Fix: one copy of each library (find which analysis adds the top-level copies; PyInstaller 6 relocates with symlinks where a top-level path is needed) and leave `torch/bin` out. `check_bundle` fails on two files over 1 MB with the same content and on a `torch/bin` folder (unit tests for both). PR body: the three installer sizes and installed sizes before and after.

**F3 (licence, as D-798): the AppImage's runtime is LGPL code without its source.** The PR's own licence row says the static type-2 runtime links libfuse 3 (LGPL-2.1) and squashfuse; every AppImage starts with that binary, so the AppImage redistributes statically linked LGPL code, the same obligation D-798 met for FFmpeg.
Fix: `sources_archive.sh` adds the type2-runtime source at the commit of release 20251108 (`git archive`, pinned by SHA-256 in `tools.env` or `sources.env`) and the libfuse 3 (and squashfuse) source archives in the versions that runtime build uses, each pinned by SHA-256; README.txt, SOURCE.txt and the THIRD_PARTY row name them. Test: `test_every_download_is_pinned_by_its_sha256` covers the new pins.

**F4 (licence notices): three MIT/BSD notices are not shipped.** `NOT_CHECKED` leaves espeakng-loader (and clr-loader on Windows) out of `python-packages.txt`, and their wheels carry no licence file, so their MIT notices are nowhere in the bundle; the static winpthreads in the Windows ffmpeg.exe (MIT and BSD-3-Clause) needs its notice too.
Fix: their licence texts in the repository (e.g. `packaging/licenses/espeakng-loader-LICENSE`, `clr-loader-LICENSE`, `winpthreads-COPYING`, copied from the projects' repositories at the pinned versions, with source URLs) copied into `licenses/` by `licences()`; `check_bundle` requires them (Windows: all three; others: espeakng-loader). Tests extended.

**T1: 11 of 32 hand mutants survive** (`plans/b635-review/mut.py <worktree>`, baseline 41 passed on tests/unit/test_installers.py). Add a test for each:
1. `licences()` without `--fail-on=...` (pip-licenses would no longer refuse anything): assert the command carries `--fail-on` with `REFUSED` (stub `subprocess.run`).
2. `window_problems` with `rail is False` instead of `is not True`: a report with `rail` missing must be named.
3. `smoke_window` ignoring the exit code: a stub app that writes a good report and exits 1 must fail.
4. `smoke_browser` ignoring Quit's status: a stub where Quit answered 404 must fail.
5. `visit` keeping the token in `start`: the report must not contain the start link's query.
6. `smoke_cli` without the version check: a stub program printing another version must fail.
7. `smoke_cli` without the MP3 check: a stub that writes only the M4B must fail.
8. `sources_archive.sh` skipping the espeak-ng hash, and 9. `build.sh` skipping its hash check: a test that runs each script with a tampered archive in the downloads folder (bash available on all CI systems; skip on Windows if needed) and expects exit 1 and the "SHA-256 ..., expected" message.
10. `release.yml` attesting only the wheel: the attestation's `subject-path` must be `dist/*`.
11. the Windows smoke step without `test ! -e "$FOLDER"`: the workflow test checks the uninstall step keeps that line and the model/audiobook/log checks.

**N1:** `packaging/linux/sci2audio.desktop` has `Categories=AudioVideo;Audio;`; add `Education;` to match the macOS plist (`public.app-category.education`). No test needed.
