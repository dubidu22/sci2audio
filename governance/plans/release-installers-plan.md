# Release batch "Installers for testers": plan (#215, #13, #525, release 1.4.0)

Thread: app/release lane implementation, started 19 Nov 2026 07:00Z (D-795, D-796). Base: main b6355cc. Critical (packaging, release, CI, new dependency with licences): plan waits for the coordinator's approval; review Opus high. Out of scope (D-795): public plugin interface (#216, #203), update check (#217).

Goal (Colin, 06:54Z): "get to the point faster, where i can tell others about it, let them install it and gain feedback." So this batch optimises for a tester who double-clicks a download, not for a polished store product.

## 0. What was checked before planning

- Packaging today: wheel only (hatchling). `release.yml` on a `v*` tag: version and dated CHANGELOG checks, `uv build`, wheel smoke on three systems (`scripts/release_smoke.sh`, `sci2audio script` on a corpus PDF), PyPI trusted publishing in environment `pypi`, GitHub release from the CHANGELOG section, install from PyPI on three systems. The v1.0.0 run (15 Nov 08:43Z) shows the `pypi` environment **requires dubidu22's approval** (approvals API: "dubidu22 approved pypi").
- Interface start: `sci2audio ui` binds 127.0.0.1:0, prints a one-time start link (token → cookie), opens the default browser (`web/launch.py`). No window shell exists; no pywebview anywhere.
- Voice files: downloaded only on request, pinned by revision and sha256 (`voices/download.py`): English Kokoro (Apache-2.0) + spaCy `en_core_web_sm` (MIT), German Kokoro Thorsten (Apache-2.0). `HF_HUB_OFFLINE=1` is set at start (`voices/runtime.py`). Models live in the platformdirs folder, outside any program folder.
- Measured here (Linux x86_64, `uv sync --no-dev --frozen`, CPU torch): the run-time environment is **1.5 GB unpacked**: torch 747 MB, imageio-ffmpeg 165 MB, spaCy 121 MB, transformers 58 MB, blis 39 MB, babel 33 MB, numpy 57 MB, espeakng-loader 21 MB, the rest small.
- pywebview 6.2.1 (BSD-3-Clause) resolves to: Windows pythonnet 3.2.1 + clr-loader + cffi + pycparser + bottle + proxy-tools; macOS pyobjc-core and five pyobjc frameworks 13.0 + bottle + proxy-tools; Linux only bottle + proxy-tools (it needs GTK/PyGObject or Qt there, see §2.3). PyInstaller 6.22.3 + pyinstaller-hooks-contrib 2026.10.
- #525: `test_events_keep_the_stream_alive_and_end_when_the_server_stops` is the only quarantined test (win32). 0/40 failed alone on Windows; it fails only under `-n auto` load. Likely cause: the fixed 0.5 s `threading.Timer` that stops the server can fire before the first keep-alive is read.
- Nightly on main 96de4a3 (18 Nov): only `browser (firefox, ubuntu-latest)` red, a reported-only leg (rules 1.4.6).

## 1. Decisions in one table

| | Recommendation | Main alternative rejected |
|---|---|---|
| Freezing | **PyInstaller 6.x, onedir**, two executables in one bundle: `sci2audio` (console CLI) and `sci2audio-app` (windowed) | Briefcase (less proven with torch, its own packaging conventions), Nuitka (compile time with torch, no gain), "small launcher that installs from PyPI on first start" (a 1.5 GB network install the user did not knowingly start, fragile) |
| macOS | `.app` ad-hoc signed, in a `.dmg` made with `hdiutil`; Apple Silicon only | notarised build (needs the paid Apple Developer Program) |
| Windows | **Inno Setup 6** per-user installer `setup.exe` (no admin, no UAC), Start-menu entry, uninstaller; x64 | MSI via WiX (more work, admin install), plain zip (no Start-menu entry, no uninstall) |
| Linux | **AppImage** (x86_64), built on ubuntu-22.04 (glibc 2.35); opens the interface in the default browser (q1) | Qt window (§2.3), Flatpak (v2) |
| Window | **pywebview** (D-47, D-45): WKWebView on macOS, WebView2 on Windows; optional extra `sci2audio[window]`, so the PyPI install stays as it is | Electron/Tauri (second toolchain), Qt WebEngine (+~300 MB) |
| Voice files | **Not bundled**; the existing consent download on the Voices page stays the only network use (q2) | bundling the English pack (+~330 MB per installer) |
| Signing | **No paid certificates**; ad-hoc on macOS, unsigned on Windows, SHA256SUMS + GitHub build-provenance attestations for all; the steps past Gatekeeper and SmartScreen in the notes (q4) | paid Apple/Windows certificates |
| Version | **1.4.0** (q3) | 1.1.0, 2.0.0 |

## 2. Installers per system

### 2.1 macOS (`sci2audio-1.4.0-macos-arm64.dmg`)

- PyInstaller `BUNDLE` → `sci2audio.app` (Contents/MacOS holds `sci2audio-app` as the bundle executable and the `sci2audio` CLI). `Info.plist`: `CFBundleIdentifier io.github.dubidu22.sci2audio`, version from `__version__`, `LSMinimumSystemVersion 12.0`, `NSHighResolutionCapable`. No entitlements, no network or file-access usage strings needed (files come through the open dialog).
- Signing: ad-hoc (`codesign --force --deep --sign -`), needed for arm64 code to run at all. Not notarised, so a downloaded copy is quarantined: on macOS 15 and later the person opens it once, is refused, then clicks **System Settings → Privacy & Security → Open Anyway** (Sequoia removed the Control-click bypass). The notes also give the Terminal line `xattr -dr com.apple.quarantine /Applications/sci2audio.app`.
- Apple Silicon only: torch ≥ 2.3 publishes no macOS x86_64 wheels (sci2audio needs torch ≥ 2.6), so Intel Macs cannot run sci2audio at all, from PyPI either. The notes say so.
- Size estimate: 250–350 MB download (torch on macOS is smaller than on Linux; measured in PR 2 and written into the notes).

### 2.2 Windows (`sci2audio-1.4.0-windows-x64-setup.exe`)

- PyInstaller onedir, `sci2audio-app.exe` built with `console=False`, plus `sci2audio.exe` (console).
- Inno Setup 6 script `packaging/windows/sci2audio.iss`: `PrivilegesRequired=lowest`, installs to `%LOCALAPPDATA%\Programs\sci2audio`, Start-menu shortcut, optional desktop shortcut, LZMA2 compression, licence page showing GPL-3.0 + the bundled-licences summary. The **uninstaller removes the program folder only**: never Documents\sci2audio, the models folder, settings or the library (a test checks this; deleting user files is a critical path).
- Inno Setup itself is fetched in CI from its official URL pinned by sha256 (no package manager in the trust path). Its licence allows free use; the installer stub it adds is covered by that licence (row in THIRD_PARTY_LICENSES.md).
- WebView2: Evergreen runtime is part of Windows 11 and current Windows 10. If it is missing, the app opens the interface in the default browser instead and says why (§3), rather than shipping the 100+ MB runtime installer.
- Unsigned: SmartScreen shows "Windows protected your PC" → **More info → Run anyway**. Free signing for open-source projects (SignPath Foundation) needs an application and a code-signing policy page: filed for v2.
- Size estimate: 400–550 MB download.

### 2.3 Linux (`sci2audio-1.4.0-linux-x86_64.AppImage`) and the window question (q1)

pywebview on Linux needs GTK + WebKitGTK through PyGObject, or Qt WebEngine. WebKitGTK cannot be bundled reliably (its helper processes are found at paths compiled into the library), PyGObject must match the system's GLib, and Qt WebEngine adds ~300 MB and needs `--no-sandbox` inside an AppImage. So:

- **Recommended (L1):** the AppImage starts the server and opens the interface in the default browser, as `sci2audio ui` does. Because there is no terminal and no window to close, two small additions in the web lane: a **"Quit sci2audio"** item at the foot of the rail when running without a window, and the server **stops by itself after 15 minutes without any request while no job runs** (the Listen page already saves the position while playing, so playback keeps it alive). This deviates from #215 AC-2 ("no browser needed") on Linux only; the coordinator decides or puts it to Colin.
- L2: Qt window (PySide6 + QtWebEngine, LGPL-3.0): meets AC-2, about doubles the Linux download, sandbox off.
- L3: no Linux installer in 1.4.0; Linux testers use `uv tool install sci2audio` (already smoke-tested on PyPI).
- A Linux window properly done is a Flatpak on the GNOME runtime (which ships WebKitGTK): filed for v2.
- Built with `appimagetool` (MIT) pinned by sha256, using the static type-2 runtime, so it does not need libfuse2 (smoke-tested on ubuntu-24.04, which lacks it). Desktop file and icon inside. Size estimate: 500–600 MB.

## 3. The app window (PR 1)

New module `src/sci2audio/web/window.py` (the web layer owns the shell; pywebview joins the "only web imports the web framework" forbidden contract for every other layer) and a gui-script entry `sci2audio-app = sci2audio.web.window:main`.

- Start: bind and configure exactly as `run()` does (127.0.0.1, port 0, fresh token); uvicorn runs in a background thread, the pywebview window on the main thread (macOS requires it) loads `config.start_url`. Closing the window stops the server through the same `state.stopping` / `board.shutdown` path as Ctrl-C today.
- Closing while an audiobook is being made: a confirm dialog ("Closing sci2audio stops the audiobook being made. Sentences already spoken are kept; making it again continues."), English or German by the interface language. No job: closes at once.
- Links outside 127.0.0.1 (licence pages, the issues link) open in the system browser, never in the window (pywebview `OPEN_EXTERNAL_LINKS_IN_BROWSER`); downloads of the app's own files are allowed.
- Offline (AC-215.3): the web engines' own reputation checks are switched off: WebView2 SmartScreen (`IsReputationCheckingRequired = false`, or the `msSmartScreenProtection` feature flag if pywebview exposes no hook) and WKWebView's fraudulent-website warning. A unit test checks the settings are applied; the Linux network-namespace smoke (§5) proves the program itself needs no network.
- No terminal: a start-up log (rotating, 1 MB, platformdirs log folder; no document text, no file names, no token) and, if the server cannot start or the window engine fails, a native dialog naming the log file; on Windows without WebView2 and on Linux it falls back to the default browser (L1).
- Test hook: `sci2audio-app --selftest REPORT.json` starts normally, waits for the page to load, reads `document.title`, the `lang` attribute and that the rail is drawn through `evaluate_js`, writes them with the start URL's port into REPORT.json, closes the window and exits 0. Only that flag enables it.
- Tests (fast suite, no real window): pywebview replaced by a fake module: the window gets the start URL, close with and without a running job, external links, engine settings, log contents, selftest report, browser fallback. Real windows are exercised by the smoke tests of PR 2.
- Licence rows: pywebview, pythonnet, clr-loader, cffi, pycparser, bottle, proxy-tools, pyobjc-core and frameworks (each checked at the source, SPDX in the PR body).

## 4. Licences and the source offer (AC-215.4)

- The bundle carries `licenses/`: generated in the build from the frozen environment with pip-licenses (already a dev tool) plus THIRD_PARTY_LICENSES.md; the build **fails on AGPL, SSPL, non-commercial or unknown**, with the same allow-list exception for espeakng-loader as CI's licences job. Python (PSF-2.0), the Inno Setup stub and the AppImage runtime get their own rows.
- **Changed by D-798 (19 Nov 07:33Z):** the FFmpeg inside imageio-ffmpeg is a full BtbN "gpl" build linking about 70 external libraries (x264, x265, libvpx, SRT, Vulkan, ...; 165 MB on Linux), whose complete corresponding source the installers could not offer. So the installers workflow builds a **minimal audio-only FFmpeg** per system from pinned source tarballs (FFmpeg + LAME; versions and SHA256 in the repo; LGPL-2.1-or-later with libmp3lame LGPL), cached per system; the bundle points `IMAGEIO_FFMPEG_EXE` at it and leaves imageio's binary out. The fast output tests and the speaking smoke test run against that build. The sources tar is exactly FFmpeg + LAME + espeak-ng + the build script. Installers get about 100–150 MB smaller. PyPI installs are unchanged (D-120).
- (Superseded by the line above) GPL corresponding source: the installers redistribute GPL binaries (FFmpeg from imageio-ffmpeg, espeak-ng from espeakng-loader), which D-120 said needs the source offered. The release attaches `sci2audio-1.4.0-sources.tar` with the sci2audio sdist, the FFmpeg and espeak-ng source archives matching the bundled versions (pinned by sha256), and the uv.lock; the notes and the app's Privacy/licences page point to it.

## 5. Smoke tests on three systems (#13) and CI wiring

One reusable workflow `.github/workflows/installers.yml` (`workflow_call`, `workflow_dispatch`, and the PR label `ci:installers`, started like `ci:full`). `release.yml` calls it, so the release builds exactly what was tested. GitHub Actions minutes are free here, so every check below runs on every installer build.

Per system (macos-latest, windows-latest, ubuntu-22.04 build, smoke on ubuntu-22.04 and ubuntu-24.04):

1. Build the bundle and the installer; upload as artifact (7 days).
2. **Install it as a person does**: macOS mount the dmg and copy the app to `~/Applications`; Windows run `setup.exe /VERYSILENT /CURRENTUSER`; Linux `chmod +x` and run the AppImage directly.
3. `sci2audio --version` from the installed copy equals the tag/package version.
4. `sci2audio script` on the corpus PDF (as `release_smoke.sh`), from the installed copy.
5. **Speak**: voice files downloaded once with the program's own `voices download --yes` into a cached models folder (actions/cache keyed by the pinned revisions), then `sci2audio convert` on a short English and a short German text: an M4B exists and has audio. This is where missing data files of misaki, espeak-ng, spaCy, kokoro and ffmpeg would show; nothing else catches them.
6. **Offline** (Linux): steps 4 and 5 again inside `unshare --net` (no network interface at all). macOS and Windows: run with the proxy variables pointing at a closed port (weaker; stated as such).
7. **Window**: `sci2audio-app --selftest` on macOS and Windows (the runners have a desktop session): the report shows the page loaded on 127.0.0.1 with the right title and language. Windows also runs the browser tests' main-flow subset with Playwright **attached to the real WebView2 window** over CDP (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port`, set by the harness only), which is #13 AC-2. macOS WKWebView has no automation port; the WebKit browser legs already cover that engine. Linux: the server answers on the printed start URL and the browser fallback is invoked (a stub browser in the test).
8. **Uninstall** (Windows): silent uninstall; the program folder is gone, and the models folder, settings and a project folder created in step 5 are untouched.

Release order on a tag: build wheel + build installers → wheel smoke + installer smoke (all three systems) → publish to PyPI (Colin's approval tap, §9) → GitHub release with wheel, sdist, installers, SHA256SUMS.txt, sources tar and build-provenance attestations (`actions/attest-build-provenance`) → install from PyPI on three systems. Nothing is published unless every installer passed.

Workflow tests in `tests/unit/test_ci_workflows.py` (job order, pinned action SHAs, the publish job needing the installer smokes, zizmor clean).

## 6. #525 (the quarantined test), before the tag

Fix in the test, no wall-clock budget: read the event stream line by line and set `stopping` only after the first keep-alive has been read; then assert the stream ends and holds no `end` event. Remove the quarantine marker.

Fix criteria: (a) the test fails if the server-stop path is broken (a hand mutant that ignores `stopping` must turn it red); (b) 40 isolated runs on Windows green (isolate run, real pass counts in #525); (c) two `ci:full` runs of the whole fast suite with `-n auto` green on Windows; (d) `uv run pytest -m quarantined --collect-only -q` collects none. Non-critical (test only), Opus medium review.

## 7. Version number (q3)

**1.4.0.** PyPI has 1.0.0; 1.1.0 was never published (D-721) and main holds v1.1 German reading, the v1.3 Working Reader and now the v1.4 installers. 1.4.0 matches the milestone names and the decision log's wording ("v1.4 published", D-721, D-722). 2.0.0 would clash with the new v2 milestone, which holds the deferred work. The CHANGELOG's single `[Unreleased]` section becomes `## [1.4.0] - <date>` with a lead paragraph saying 1.1 to 1.3 were not published separately. Classifier "Development Status" moves from 2 - Pre-Alpha to 4 - Beta.

## 8. What the release notes must say

1. One paragraph: what sci2audio does, offline, English and German, the first release meant for other people, feedback wanted.
2. Download table: which file for which system (Apple Silicon Mac / Windows 10–11 x64 / Linux x86_64), sizes, SHA256, and "Intel Macs are not supported (PyTorch has no Intel Mac builds)".
3. First start, per system: the Gatekeeper "Open Anyway" steps (and the xattr line), the SmartScreen "More info → Run anyway" steps, `chmod +x` for the AppImage; why the warnings appear (no paid certificate) and how to check the download (SHA256SUMS, `gh attestation verify`).
4. The voice download on first use: what it fetches, from where (huggingface.co, github.com), sizes, that it is the only time sci2audio uses the internet and only when asked.
5. Where files go (audiobooks, models, settings, log) and that uninstalling keeps them, with how to remove them by hand.
6. Highlights since 1.0.0 (German voice and rules, the Working Reader, footnotes by mark, warnings for unreadable pages, …), from the CHANGELOG.
7. Known limits: Linux opens in the browser (if L1), no update check, no plugin interface, the open issues worth knowing.
8. How to give feedback: the "Tester report" issue form (new in PR 3: system, installer, what happened, the log file), and the GPL source download.

## 9. PRs, order and review

| PR | Lane(s) | Content | Critical | Est. size |
|---|---|---|---|---|
| 0 | web (tests only) | #525 test fix, quarantine lifted | no | ~40 lines |
| 1 | web + infra (`pyproject.toml`/`uv.lock` for the `window` extra and entry point) | §3 app window, Linux browser mode (q1), licence rows, import contract | yes | ~600 lines incl. tests |
| 2 | infra + new `packaging/` + `scripts/` | §2 installers, §4 licence bundle and sources tar, §5 `installers.yml`, `release.yml`, app icon (drawn in-repo, our licence) | yes | ~1,000 lines |
| 3 | docs + version | 1.4.0 bump, CHANGELOG date, README "Installing" with the installers, `docs/installing.md` (the first-start steps), release checklist update, "Tester report" issue form | yes (release) | ~250 lines |

- Order: PR 0 now (no shared files with PR 1); PR 1; PR 2 developed on top of PR 1 and opened when PR 1 merges; PR 3 last. Web and infra lanes are idle (memory 06:49Z); none of B9/B13/B14 touches these files.
- Each PR: Linux CI green before review; critical ones also my own `ci:full` run (PR 2 additionally a full `ci:installers` run) green before review; one fix commit per round; a ledger line in `ledger/implementation.md` per PR. I never merge or force-push.
- After PR 3 merges: the tag `v1.4.0` on the merge commit (q6), the release workflow does the rest.
- Cleanup with the release: #426 closed as superseded, milestone v1.1 closed, release/1.1 left as is (D-721).

## 10. Hand steps for Colin (kept to what cannot be automated)

1. **Approve the `pypi` deployment** in the release run (one tap in GitHub, or the mail GitHub sends). The environment requires his approval, as the v1.0.0 run showed; removing that protection is possible but not recommended for a publish that cannot be undone.
2. Nothing else is required: no paid accounts, no tokens (PyPI trusted publishing is already set up and worked for 1.0.0).
3. Optional, ~10 minutes: open the dmg from the `ci:installers` artifact or the release on his M4 once, because CI cannot reproduce Gatekeeper's quarantine path.

## 11. Deferred, filed in milestone v2 when PR 1 opens

Windows signing through SignPath Foundation; Apple notarisation (needs the paid programme: Colin's call); Linux window via Flatpak; Windows arm64; file associations ("Open with sci2audio"); one running instance at a time (a second start opens its own server today); smaller download (Kokoro through ONNX instead of torch); .deb/.rpm packages.

## 12. Open questions for the coordinator

- **q1 Linux window:** L1 browser mode with Quit + idle stop (recommended), L2 Qt window, or L3 no Linux installer. L1 amends #215 AC-2 for Linux.
- **q2 Voice files:** not bundled, consent download on first use (recommended), or bundle the English pack.
- **q3 Version:** 1.4.0 (recommended).
- **q4 Signing:** no paid certificates for 1.4.0; SignPath and notarisation filed for v2 (recommended).
- **q5 Release checklist hand items** (listening test, screen-reader pass, speed on the M4): skipped for this tester release as under D-721, with mutation and ZAP started by me through workflow dispatch and their results in the release issue (recommended). Without that, items 1 to 3 of §10 grow by about an hour of Colin's time.
- **q6 Tag:** pushed by the review thread on the coordinator's go after PR 3 merges (recommended), or by the coordinator.
- **q7 Fallback pre-approval:** if PyInstaller cannot freeze the uv-managed Python 3.12.16 (python-build-standalone), PR 2 uses actions/setup-python 3.12 for the installer builds only. D-378's reason for avoiding runner Pythons (HTML parsing differences) goes away once B14 #609 vendors the parser; the wheel smoke and CI keep uv-managed Python.
