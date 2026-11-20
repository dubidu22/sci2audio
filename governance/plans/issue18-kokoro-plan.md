# Plan: issue #18, Kokoro English voice (VA-01, VA-02, VA-03, VA-05, PE-07)

Thread "Add the Kokoro voice", 12 Nov 2026. Critical (`risk:high`: new run-time dependencies, copied third-party code, the voice plugin contract, network download, nightly workflow). Waits for the coordinator's approval before any code.

Binds: D-47 (download only on user action, "everything for offline use"), D-48 (PyTorch, CI on CPU torch), D-50 (English first), D-52 (copy Abogen's contract types and Kokoro plugin, MIT notice kept), F-15 (`PYTORCH_ENABLE_MPS_FALLBACK=1` in one start-up function), the decided points from the v1.0 plan review (spaCy model, `HF_HUB_OFFLINE`, espeakng-loader licence, one download function for #72/#76, VA-02 Linux size) and the output contract for #69 (chunk audio = WAV, 16-bit PCM, mono, one rate per job).

## 1. What I checked in practice (scratch environment, 12 Nov)

| Fact | Result |
|---|---|
| Latest versions | kokoro 0.9.4, misaki 0.9.4, torch 2.15.0, transformers 5.22.2, spaCy 3.8.18, espeakng-loader 0.2.4 (117 packages in total) |
| Offline synthesis | **Works with every socket blocked** when the model, voices and spaCy model are local: `KModel(config=<file>, model=<file>)`, `KPipeline(model=<KModel>)`, voice given as a local `.pt` path. No `hf_hub_download` is ever called. Same on Python 3.12 and 3.13 |
| Speed (this container, CPU, 1 thread pool) | 44 characters per second (8.5 s of audio in 2.3 s); model load 13 s. A row for `docs/baseline.md`; the M4 row stays Colin's |
| Install size on Linux | default PyPI torch (CUDA): **5.6 GB** environment (3.0 GB nvidia, 1.0 GB triton, 1.1 GB torch). CPU torch index: **1.3 GB** (747 MB torch) |
| Python range | kokoro and misaki declare `Requires-Python <3.13`. uv ignores upper bounds, so `uv tool install` works on 3.13 (tested); pip/pipx on 3.13 refuse to install |
| spaCy model | `en_core_web_sm-3.8.0-py3-none-any.whl` from explosion's GitHub release `en_core_web_sm-3.8.0`: 12.8 MB, sha256 `1932429d…fb85`, MIT. Unpacked into a folder on `sys.path`, `spacy.util.is_package` finds it, so misaki never calls `spacy.cli.download` |
| Kokoro model | `hexgrad/Kokoro-82M` at revision `f3ff3571791e39611d31c381e3a41a3af07b4987`: `config.json`, `kokoro-v1_0.pth` (327 MB), voice packs 0.5 MB each; Apache-2.0; model card: trained only on "permissive/non-copyrighted audio" (public domain, Apache/MIT, CC BY data listed) |
| espeak-ng | `espeakng-loader` wheels for macOS arm64/x86, Linux x86/arm, Windows x64/arm; loader code MIT (licence file on GitHub, **no licence in the PyPI metadata**), bundles libespeak-ng (GPL-3.0-or-later). misaki's fallback loads it with no system install |
| CI licence check | fails today on `espeakng-loader` (licence "UNKNOWN" in metadata). Everything else passes; phonemizer-fork GPL-3.0+, num2words LGPL, certifi MPL-2.0 are allowed |
| pip-audit | no known vulnerabilities; it skips `torch 2.15.0+cpu` (not on PyPI) with a note |

## 2. Design

### Files (all new under `src/sci2audio/voices/`)

| File | What | Lines (rough) |
|---|---|---|
| `types.py` | **Copied** from Abogen `tts_plugin/types.py` (MIT header kept): `AudioFormat`, `Duration`, `VoiceSelection`, `ParameterValues`, `SynthesisRequest`, `TokenTiming`, `AudioSegment`, `SynthesizedAudio`, `EngineConfig`. Adapted: Abogen's `Language` enum becomes a BCP 47 tag string (`"en-US"`, `"en-GB"`), and a small `VoiceInfo` (id, name, language, gender) replaces Abogen's `VoiceManifest` (its manifest module is not copied, per D-52) | 170 |
| `engine.py` | **Copied** `Engine` / `EngineSession` protocols (create session, synthesize, dispose), plus `API_VERSION = "1.0"` (the conformance suite checks it, #6) | 100 |
| `errors.py` | **Copied** error hierarchy unchanged (`EngineError`, `ModelNotFoundError`, `NetworkError`, `InvalidInputError`, ...) | 60 |
| `kokoro.py` | **Adapted** from Abogen `plugins/kokoro/` (MIT header): the 28 English voices only (af/am/bf/bm, D-50), `create_kokoro_engine(models_dir, config)`, `KokoroEngine`, `KokoroSession`. Loads everything from local files; **never downloads**; if a file is missing it raises `ModelNotFoundError("run the voice setup")` *before* misaki can call `spacy.cli.download`. Speed checked against 0.5 to 2.0 (`InvalidInputError`). Device: `mps` if available, else `cuda` if available, else `cpu` | 250 |
| `setup.py` | The **one download function** for #72 and #76: `download_plan()` lists every file with source URL, size, sha256 and licence text to show before consent (VA-03); `download_voice_files(models_dir, progress=None)` fetches the Kokoro config, weights and all 28 English voice packs from Hugging Face at the pinned revision, plus the spaCy wheel from explosion's GitHub release (about 355 MB in total, "everything for offline use", D-47); `missing_files(models_dir)`. Each file: streamed to `name.part`, sha256 checked, then `os.replace`; files already present and verified are skipped (resume). The wheel is unpacked into `models_dir/spacy/` the same way (temp folder, then rename) | 200 |
| `runtime.py` | `prepare_environment()`, **the one start-up function** (F-15): sets `PYTORCH_ENABLE_MPS_FALLBACK=1` and `HF_HUB_OFFLINE=1` and puts the spaCy folder on `sys.path` (idempotent). `create_kokoro_engine` calls it before importing torch or kokoro, so it cannot be forgotten; #70/#71 also call it at job start | 50 |
| `wav.py` | `speak_to_wav(session, text, voice_id, speed, path) -> float` writes **16-bit PCM mono WAV at 24 kHz** with the stdlib `wave` module (float samples clipped to [-1, 1]), atomically (`.part` then rename), and returns the duration from the frame count. `preview(session, voice_id, speed, path)` speaks a fixed English sample sentence (VA-05) | 80 |
| `__init__.py` | Public names only | 40 |

`voices` imports only `core`, the stdlib, `numpy`, `requests` and (lazily, inside functions) `torch` and `kokoro`. Importing `sci2audio.voices` stays fast: no torch import at module level.

The app (#71) turns the returned path and duration into an `AudioChunk`; the voice does not build `AudioChunk`s itself, because it does not know spans.

### Decisions in this plan (each with my recommendation)

1. **spaCy model: unpack into the cache and put it on `sys.path`** (not "install into the environment"). `uv tool install` environments have no pip, and `uv tool upgrade` would wipe an installed model; a folder in the user's model cache survives both. The model cache folder is passed in by the caller (no global state); `app` picks the default folder in #70/#71.
2. **One HTTP client for both sources: `requests`** (Apache-2.0; already in the tree through spaCy, now declared). `huggingface_hub` is not used for downloading, so pinning by revision plus sha256 works the same for both sources and the fault tests mock one function. Consequence: **`HF_HUB_OFFLINE=1` is set always**, not "except during the download", because our download never goes through `huggingface_hub`. Stricter than the decided point, same intent.
3. **VA-02 Linux size: document the CPU index, keep the plain command working.** In our own lock, torch comes from the PyTorch CPU index on Linux (`[tool.uv.sources]`, so CI and contributors get 1.3 GB, D-48). Published metadata cannot express an index, so the README gets one Linux line: `uv tool install sci2audio --torch-backend cpu` (1.3 GB instead of 5.6 GB; the plain command also works and uses a GPU when there is one). The README install section belongs to #80; I add only this note there, and #80 keeps it.
4. **Python range: keep `>=3.12`**, document that pipx needs Python 3.12 (`pipx install --python python3.12 sci2audio`) because kokoro/misaki cap at <3.13, and file an issue to remove the note when they lift the cap. uv users are unaffected (tested on 3.13). Alternative not chosen: cap sci2audio at `<3.13`, which would block 3.13 for everyone because of a metadata cap that does not reflect a real break.
5. **Contract shape: Abogen's, as D-52 decided** (engine creates sessions, session synthesizes, dispose), slimmed only where Abogen depends on files we do not copy. No plugin discovery (that is v1.1, PE-07 public).
6. **Licence check in CI:** add `espeakng-loader` to `--ignore-packages` with a comment, because its metadata has no licence; the licence is checked by hand (MIT loader, bundled espeak-ng GPL-3.0-or-later) and recorded in `THIRD_PARTY_LICENSES.md`.
7. **Intel Macs are not supported** (torch has had no macOS x86_64 wheels since 2.2). Written in `THIRD_PARTY_LICENSES.md`'s neighbour, the README note, and the PR.

### Dependencies (run time) and licences

kokoro (Apache-2.0), misaki[en] (Apache-2.0), torch (BSD-3-Clause and others, listed), numpy (BSD-3-Clause), requests (Apache-2.0), plus what they pull: transformers, huggingface-hub (Apache-2.0), spaCy, thinc (MIT), espeakng-loader (MIT + bundled espeak-ng GPL-3.0-or-later), phonemizer-fork (GPL-3.0-or-later), num2words (LGPL-2.1). Models: Kokoro-82M weights and voices (Apache-2.0), en_core_web_sm 3.8.0 (MIT; its training data OntoNotes 5 is licensed to explosion, WordNet licence permissive). Copied code: Abogen (MIT, © 2025 Deniz Şafak), revision `1807822f`. All rows go into `THIRD_PARTY_LICENSES.md`.

Dev/nightly only (dependency group `asr`, not installed by the fast CI jobs): faster-whisper (MIT) with ctranslate2 (MIT), its `small` model (MIT, Systran).

## 3. Tests

**Fast (every PR, no network, no model):**
- Kokoro adapter with a fake `KPipeline` injected: voice ids map to local `.pt` paths; float audio becomes 16-bit mono 24 kHz WAV with the right frame count and duration; segments and token timings kept; speed bounds; empty text → `InvalidInputError`; errors are `EngineError`s; use after `dispose` raises; `dispose` is idempotent.
- Missing model files: `create_kokoro_engine` raises `ModelNotFoundError` naming the setup, and **neither `spacy.cli.download` nor any socket is touched** (both patched to fail the test).
- `prepare_environment` sets both variables and the `sys.path` entry, idempotent; `sci2audio.voices` imports without importing torch.
- Download, with a fake fetch function (fault injection, `.claude/rules/tests.md`): happy path; no network → `NetworkError`, no file left behind; disk full (ENOSPC on write) → clear message, no half file; checksum mismatch → error, file removed; kill mid-run then run again → verified files skipped, the rest fetched; models folder removed during the run → clear error; corrupt wheel → error, no half-unpacked folder.
- `download_plan()` lists every file with a URL on the two allowed hosts only, a sha256 and a licence.
- Hypothesis: `speak_to_wav`'s sample conversion never raises on any float array (including NaN and inf), always yields int16 in range and `frames == len(samples)`.
- Conformance suite (`sci2audio.testing.voices`, plain functions, no pytest import at module level, per Q11): run against the Kokoro adapter with the fake pipeline, and against a deliberately broken fake engine to prove it catches faults.

**Slow (nightly, 3 systems, CPU torch):** a workflow step downloads the voice files with our own download function and the whisper `small` model, both cached with `actions/cache` keyed on the pinned revisions; then with every socket blocked:
- two voices (`af_heart`, `bm_george`) turn a sentence into a WAV through the contract (VA-01 criterion);
- the conformance suite against the real Kokoro engine;
- speech-recognition round trip (#9): 5 paragraphs of *The Time Machine* from the corpus truth file (public domain, plain prose, so no text rules are needed yet); WER after normalising case and punctuation must stay below 0.10; the 3 worst sentences are printed in the report.

**Benchmark (nightly):** characters per second for a fixed paragraph on CPU; new row in `docs/baseline.md` with today's container number and the install sizes above.

## 4. Coordination

- **`sci2audio.testing`** is also created by #63. Whichever PR merges first adds the package and the layer line `sci2audio.app | sci2audio.testing` (Q11); the other rebases. My part is only `testing/voices.py`.
- Lanes: voices (main), plus infra (`pyproject.toml`, `uv.lock`, `ci.yml` ignore entry, `nightly.yml`) and docs (`THIRD_PARTY_LICENSES.md`, `docs/baseline.md`, README note), which this issue needs.
- CI cost: every job now installs torch (Linux CPU about 200 MB download, cached by setup-uv). I will report the before/after time of the fast jobs in the PR.

## 5. Out of scope (issues filed if not already covered)

Voice blending, German voices (after D-50), GPU-specific tuning, the `voices` CLI command (#72) and the consent page (#77), which both call `download_plan()` / `download_voice_files()`; pipx on Python 3.13+ (new issue, decision 4).

## 6. Size

One PR: about 300 copied lines, 650 own lines, 800 test lines, plus workflow and docs changes.
