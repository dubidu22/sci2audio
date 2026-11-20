# PR #635 round 1: what was fixed

Fix commit `b85201d` on `infra/installers`, then three more commits on the same branch:

- 7e8c734, a merge of main: the PR had a CHANGELOG conflict with #655 and CI would not start;
- 6066504 and 2dccc2a, two F2 corrections that the ci:installers runs called for (see F2).

Reviewed head: **2dccc2a**.

## F1 (blocker): the uninstaller can no longer delete a folder of the person's

- `packaging/windows/sci2audio.iss`: `DisableDirPage=yes` (always `%LOCALAPPDATA%\Programs\sci2audio`), `PrivilegesRequiredOverridesAllowed` removed, the whole `[UninstallDelete]` section removed. The uninstaller removes the files it installed and then the folder if it is empty.
- `installers.yml`: the smoke install drops `/CURRENTUSER`, since there is no dialog left to answer. The uninstall step still checks `test ! -e "$FOLDER"`, so a file left behind fails it.
- Test `test_the_windows_installer_is_per_user_and_its_uninstaller_keeps_the_persons_files` asserts four things:
  - `PrivilegesRequired=lowest`;
  - no `PrivilegesRequiredOverridesAllowed`;
  - `DisableDirPage=yes`;
  - no `[UninstallDelete]`, `filesandordirs` or `[InstallDelete]`.

## F2: one copy of each library

- `packaging/sci2audio.spec` `one_copy()`:
  - drops the top-level copy of a library that a package keeps in its own library folder: torch/lib, `<name>.libs` (auditwheel, delvewheel) or `.dylibs` (delocate). This happens on Linux and Windows only. The packages load their libraries from there: RUNPATH `$ORIGIN` on Linux, and on Windows the DLL directory that torch and delvewheel's patch add.
  - drops torch/bin on every system, **except `torch_shm_manager`**.
- `check_bundle` fails in three cases:
  - a file of 1 MB or more that is in the bundle twice (`duplicates()`, by size then SHA-256, symlinks skipped);
  - anything in torch/bin other than `torch_shm_manager`;
  - a missing `torch_shm_manager` on Linux and macOS.
- Three things the runs found, each fixed in its own commit:
  - **`torch_shm_manager`:** `torch/__init__.py` raises "Unable to find torch_shm_manager" at import on Linux and macOS. My first local rebuild without it could not load the voice. The file is 48 kB.
  - **numpy.libs on Windows** (6066504): the new duplicate check stopped the Windows build on OpenBLAS (20 MB), which was both at the top and in numpy.libs. Hence the general library-folder rule above.
  - **macOS keeps its top-level copies** (2dccc2a): PyInstaller sets every binary's @rpath on macOS to the top of the folder, so `installed (macos-latest)` failed on 6066504 with "Library not loaded: @rpath/libtorch_python.dylib". On macOS only torch/bin goes. check_bundle passes there, so PyInstaller already leaves no second real copy over 1 MB on macOS.
- Tests:
  - `test_torchs_test_programs_fail_the_build` (3 systems);
  - `test_torch_keeps_the_one_program_it_needs_at_import`;
  - `test_a_large_file_twice_in_the_bundle_fails_the_build`;
  - `test_only_large_files_with_the_same_bytes_are_duplicates`;
  - `test_the_spec_knows_where_packages_keep_their_libraries` (6 cases);
  - `test_the_spec_keeps_one_copy_of_torchs_libraries_and_leaves_torch_bin_out`, which runs the spec's own functions through `ast`, with and without the top-level drop.

Sizes, before (ci:installers run 44507750405 on 7a60fc1) and after (run 44525393781 on 2dccc2a):

| | before | after |
|---|---|---|
| dmg | 384 MB | 381 MB |
| setup.exe | 340 MB | 277 MB |
| AppImage | 443 MB | 429 MB |
| Linux installed folder (local build) | 1724 MB | 1217 MB |

The workflow does not measure the installed folder on Windows and macOS. The Windows folder loses the same torch copies as Linux plus OpenBLAS.

## F3: the AppImage runtime's sources

- `sources.env` pins three more sources:
  - type2-runtime 20251108 (`git archive` of dd6cebed…, SHA-256 8024be0a…);
  - libfuse 3.15.0 (the release tarball, 70589cfd…, the hash the runtime's own script checks);
  - squashfuse 0.5.2 (`git archive` of 775b4cc7…, 9e5cc32e…).
- `sources_archive.sh` makes the git archives with a new `archive()` function, checks all six hashes and copies all six. README.txt names each one, its licence and the runtime's libfuse patch.
- `SOURCE.txt` and the THIRD_PARTY row (appimagetool and runtime) name the runtime, libfuse 3 (LGPL-2.1) and squashfuse (BSD-2-Clause), and point to the sources tar.
- Tests:
  - `test_every_download_is_pinned_by_its_sha256` now covers `LIBFUSE_URL`;
  - `test_each_source_from_git_is_a_pinned_commit_and_hash` covers espeak-ng, the runtime and squashfuse;
  - `test_the_sources_name_the_runtime_the_appimage_uses` checks that the runtime version matches tools.env's runtime URL, plus SOURCE.txt and the THIRD_PARTY row.
- Local run of `sources_archive.sh 1.4.0` with the real downloads: all six archives, build.sh, sources.env and README.txt are in the tar.

## F4: licence texts that the packages do not ship

`packaging/licenses/` holds three files plus a README.md that gives the source URL of each:

- `espeakng-loader-LICENSE` (MIT). Note: upstream added its LICENSE on 2025-11-01 at 0ddc87a, after the 0.2.4 release at 146599e. The README says so.
- `clr-loader-LICENSE` (MIT, tag v0.3.1).
- `winpthreads-COPYING` (MIT and BSD-3-Clause, mingw-w64 9720fc62).

`licences(dest, ffmpeg, version, system)` copies them in. `check_bundle` requires espeakng-loader on every system, and clr-loader and winpthreads on Windows. Tests:

- `test_a_bundle_without_a_vendored_licence_text_fails` (5 cases);
- `test_the_windows_only_licence_texts_are_not_asked_for_elsewhere`;
- `test_the_vendored_licence_texts_are_the_projects_own`;
- `test_the_licences_folder_holds_every_text_and_refuses_what_ci_refuses`.

## T1: the 11 mutants

`mut.py` against b85201d: every mutant is killed. "iss deletes appdata" is skipped because its target line no longer exists. The tests, by mutant number:

1. `test_the_licences_folder_holds_every_text_and_refuses_what_ci_refuses`: stubs `subprocess.run` and checks for `--fail-on={REFUSED}`.
2. A new case in `test_each_wrong_thing_in_the_window_report_is_named`: a report without `rail`.
3. `test_the_window_check_fails_when_the_app_ends_badly_after_a_good_report`.
4. `test_the_browser_check_needs_quit_to_be_accepted`: 202 passes; 404 and a missing value fail.
5. `test_the_stand_in_browser_presses_quit_and_never_writes_the_token`: a real 127.0.0.1 server; the report holds no `?` and no token.
6. `test_the_command_line_check_fails_on_another_version`.
7. `test_the_command_line_check_fails_when_only_the_m4b_is_written`, plus a passing case.
8. `test_the_sources_archive_refuses_an_archive_whose_hash_differs`: one case per archive, all six, against the real script with a stand-in sources.env and no network. `test_the_sources_archive_holds_every_pinned_archive` is the passing case.
9. `test_the_ffmpeg_build_refuses_an_archive_whose_hash_differs` (ffmpeg, lame).
10. `test_the_release_attests_every_file_it_publishes` (`subject-path: dist/*`).
11. `test_the_uninstall_check_keeps_every_part`.

The bash tests are skipped on Windows.

## N1

`Categories=AudioVideo;Audio;Education;`

## Checks

- Clean: ruff, format, lint-imports (3 kept), deptry, zizmor.
- `test_installers.py`: 81 passed.
- Fast suite (local 3.13): 8148 passed, with the 4 known 3.13-only failures.
- On 2dccc2a, every check is green:
  - CI with ci:full: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, both Chromium legs, and the reported-only Firefox and WebKit legs;
  - ZAP;
  - ci:installers run 44525393781, on ubuntu-22.04, ubuntu-24.04, macOS and Windows: the build, both audiobooks online and offline, the window and browser checks, Linux Playwright, and the Windows uninstall (the folder is gone; the voice files, audiobooks and log stay).
- 6066504 also had `browser 1/2`, `ZAP` and `installed (ubuntu-24.04)` fail in apt: security.ubuntu.com refused connections while Playwright's system packages were installing. They were re-run once and are green on 2dccc2a.
