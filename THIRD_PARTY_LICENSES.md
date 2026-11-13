# Third-party licences

Every third-party component that sci2audio bundles, copies code from, depends on at run time or downloads must be listed here **in the same pull request that adds it** (see the licence gate in `CLAUDE.md`).

Not allowed: AGPL code, non-commercial or "research only" licences, models or voices with unclear training-data rights, and third-party texts in the repository.

## Copied code

| Component | Source | Licence | Where in this repo |
|---|---|---|---|
| Abogen voice plugin contract and Kokoro plugin (`tts_plugin/types.py`, `engine.py`, `errors.py`, `plugins/kokoro/`), revision `1807822f5871d1c92740cb470c5c6e8328b8f851` | [denizsafak/abogen](https://github.com/denizsafak/abogen) | MIT, © 2025 Deniz Şafak (notice kept at the top of each file) | `src/sci2audio/voices/types.py`, `engine.py`, `errors.py`, `kokoro_engine.py` (D-52) |

## Run-time dependencies

| Package | Licence | Why |
|---|---|---|
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Apache-2.0 OR BSD-3-Clause. The wheel bundles a PDFium binary (BSD-3-Clause) built with permissive libraries whose notices ship in the wheel's `licenses/BUILD_LICENSES`: FreeType (FTL), libjpeg-turbo (IJG, BSD-3-Clause), libpng, libtiff, zlib, OpenJPEG (BSD-2-Clause), Little CMS (MIT), ICU (Unicode), Abseil (Apache-2.0), AGG 2.3, HarfBuzz (MIT), Highway, simdutf, fast_float, dragonbox (Apache-2.0, MIT or BSD) | Reads PDFs: characters with font, size, weight and position, pictures and drawings (extraction, D-65) |
| [kokoro](https://github.com/hexgrad/kokoro) | Apache-2.0 | The Kokoro speech model's inference code (voices, D-48, D-52) |
| [misaki](https://github.com/hexgrad/misaki) (with its `en` extra, through kokoro) | Apache-2.0 | English letters-to-sounds for Kokoro (D-54) |
| [torch](https://pytorch.org) | BSD-3-Clause, with bundled parts under Apache-2.0, Apache-2.0 WITH LLVM-exception, BSD-2-Clause, BSL-1.0, ISC, MIT, Zlib (wheel metadata); the Linux wheels also bundle libgomp (GPL-3.0-or-later WITH GCC-exception-3.1) | Runs the speech model (D-48). CI and our lock use the CPU-only build on Linux |
| [numpy](https://numpy.org) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Audio samples |
| [requests](https://github.com/psf/requests) | Apache-2.0 | The user-started voice download (D-47) |
| [spaCy](https://spacy.io) | MIT | Loads the English model misaki uses for word classes (D-53) |
| [transformers](https://github.com/huggingface/transformers), [huggingface_hub](https://github.com/huggingface/huggingface_hub), tokenizers, safetensors, hf-xet | Apache-2.0 | Pulled in by kokoro. huggingface_hub is never used to download: `HF_HUB_OFFLINE=1` is always set (VA-04) |
| [espeakng-loader](https://github.com/thewh1teagle/espeakng-loader) (through misaki) | MIT for the loader (licence file in its repository; **its package metadata states no licence**, so CI lists it as checked by hand); it bundles the [espeak-ng](https://github.com/espeak-ng/espeak-ng) library and data, GPL-3.0-or-later | Pronounces words misaki does not know (fallback); no system install needed |
| [phonemizer-fork](https://github.com/bootphon/phonemizer) (through misaki) | GPL-3.0-or-later | Calls espeak-ng for the fallback |
| [num2words](https://github.com/savoirfairelinux/num2words) (through misaki) | LGPL-2.1 | Numbers as words inside misaki |
| [certifi](https://github.com/certifi/python-certifi), [tqdm](https://tqdm.github.io) (through requests and transformers) | MPL-2.0 (tqdm: MPL-2.0 AND MIT) | Certificates for the download; progress bars |
| All other packages these pull in (thinc, blis, srsly, pydantic, typer, regex, sympy, networkx, jinja2, ...) | MIT, BSD, Apache-2.0, ISC, PSF-2.0 or CNRI-Python | Checked on every PR by the `licences` CI job (`pip-licenses`) |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) 0.8.1 | BSD-2-Clause (the Python wrapper). The wheel bundles an FFmpeg program; its licence per platform is listed under "Bundled programs" below | Finds the ffmpeg program that output uses to write MP3 and M4B files (Q5, #69) |
| [platformdirs](https://github.com/tox-dev/platformdirs) 4.14.5 | MIT (no dependencies) | Finds the user's configuration folder on Windows, macOS and Linux for the settings file (app, #70) |
| [FastAPI](https://github.com/fastapi/fastapi) 0.162.5 | MIT | The local server and its JSON API (web, #76, D-101). Since 0.143 it depends on `opentelemetry-api` and instruments requests itself; sci2audio switches all of that off in code (D-195) |
| [Starlette](https://github.com/encode/starlette) 1.10.0 (through FastAPI, also imported) | BSD-3-Clause | The server's request handling, static files and templates (web) |
| [uvicorn](https://github.com/encode/uvicorn) 0.54.0, without the `standard` extra | BSD-3-Clause; pulls in [h11](https://github.com/python-hyper/h11) (MIT) and [click](https://github.com/pallets/click) (BSD-3-Clause) | Serves the app on 127.0.0.1 (web, D-192) |
| [Jinja2](https://github.com/pallets/jinja) 3.1.6 with [MarkupSafe](https://github.com/pallets/markupsafe) | BSD-3-Clause | The server-rendered pages (web, D-101) |
| [python-multipart](https://github.com/Kludex/python-multipart) 0.0.33 | Apache-2.0 | Reads opened files sent by the browser (web, D-101) |
| [pydantic](https://github.com/pydantic/pydantic) 2.14.3 with pydantic-core, annotated-types, typing-inspection | MIT | The API's request and response bodies (web); it was already pulled in by spaCy |
| [opentelemetry-api](https://github.com/open-telemetry/opentelemetry-python) 1.45.2 (through FastAPI) | Apache-2.0 | Not used: FastAPI's telemetry is switched off (D-195). Without an SDK and exporter, which sci2audio never installs, it records and sends nothing |
| [annotated-doc](https://github.com/fastapi/annotated-doc) 0.0.6, [anyio](https://github.com/agronholm/anyio) (through FastAPI) | MIT | Documentation markers; the server's async runtime |

## Bundled programs (come with a run-time dependency)

FFmpeg arrives inside the `imageio-ffmpeg` wheel from PyPI, one build per platform. sci2audio does not redistribute these binaries itself. A future native installer that bundles them must also ship or offer the FFmpeg source (GPL). Checked on 2026-11-12 by reading each binary's build configuration. None is built with `--enable-nonfree`, and none includes ffprobe. All of them include the LAME MP3 encoder (`libmp3lame`, LGPL-2.0-or-later), FFmpeg's own AAC encoder, and the `ipod` (M4B) and `ffmetadata` formats.

| Wheel platform | FFmpeg version | Build flags | Licence of the binary |
|---|---|---|---|
| Linux x86_64 (manylinux_2_28) | n9.0.2 | `--enable-gpl --enable-version3` | GPL-3.0-or-later |
| Linux aarch64 (manylinux_2_28) | n9.0.2 | `--enable-gpl --enable-version3` | GPL-3.0-or-later |
| macOS x86_64 (10.13+) | 9.0.2 | `--enable-gpl --enable-version3` | GPL-3.0-or-later |
| macOS arm64 (12.0+) | 9.0 | `--enable-gpl` | GPL-2.0-or-later |
| Windows x86_64 | 9.0.2 | `--enable-gpl --enable-version3` | GPL-3.0-or-later |
| Windows arm64 | 9.0.1 | `--enable-gpl --enable-version3` | GPL-3.0-or-later |
| Windows 32-bit | 4.2.2 | `--enable-gpl --enable-version3` | GPL-3.0-or-later |

Both licences can be combined with sci2audio's GPL-3.0-or-later. If no bundled binary is present, sci2audio uses an `ffmpeg` found on PATH (the user's own install, under its own licence).

## Models and voices (downloaded on first use, never bundled)

Fetched only when the user starts the voice download (`sci2audio.voices.download_voice_files`), pinned by revision and sha256; the licences are shown before the download (VA-03).

| Model or voice | Source | Licence | Notes |
|---|---|---|---|
| Kokoro-82M model (`config.json`, `kokoro-v1_0.pth`) and its 28 English voice packs (`voices/af_*`, `am_*`, `bf_*`, `bm_*`), revision `f3ff3571791e39611d31c381e3a41a3af07b4987` | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache-2.0 | 327 MB plus 0.5 MB per voice. The model card states it was trained only on permissive or non-copyrighted audio (public domain, Apache/MIT-licensed audio, CC BY data it lists) |
| spaCy English model `en_core_web_sm` 3.8.0 (wheel, unpacked into the model folder) | [explosion/spacy-models release](https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0) | MIT | 12.8 MB. Not on PyPI, so not a package dependency. Its `LICENSES_SOURCES` names OntoNotes 5 (licensed to Explosion), ClearNLP and WordNet 3.0 (permissive) as training sources |

## Test-only components (never installed with sci2audio)

| Component | Licence | Used for |
|---|---|---|
| [Schemathesis](https://github.com/schemathesis/schemathesis) 4.33.4 (dev group) with harfile, hypothesis-graphql, graphql-core, jsonschema-rs, pyrate-limiter (MIT) and Werkzeug (BSD-3-Clause) | MIT | Tests the server against its OpenAPI document (#7) |
| [httpx](https://github.com/encode/httpx) 0.28.1 with httpcore (dev group) | BSD-3-Clause | FastAPI's `TestClient` (#7) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with ctranslate2, onnxruntime, PyAV (dependency group `asr`) | MIT (PyAV: BSD-3-Clause; its bundled FFmpeg includes x264 and x265, so GPL-2.0-or-later) | Nightly speech-recognition round trip (#9) |
| Whisper `small` for CTranslate2, revision `536b0662742c02347bc0e980a01041f333bce120` | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small), MIT | Same; downloaded by the nightly workflow only |
| [hatchling](https://github.com/pypa/hatch) with pathspec, tomlkit, trove-classifiers (dependency group `dev`; also the build backend) | MIT (pathspec: MPL-2.0; tomlkit: MIT; trove-classifiers: Apache-2.0) | Test that the wheel ships the package data files (#68) |

## External programs (installed by the user)

| Program | Licence | Used for |
|---|---|---|
| *(none yet)* | | |
