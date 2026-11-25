# Third-party licences

Every third-party component that sci2audio bundles, copies code from, depends on at run time or downloads must be listed here **in the same pull request that adds it** (see the licence gate in `CLAUDE.md`).

Not allowed: AGPL code, non-commercial or "research only" licences, models or voices with unclear training-data rights, and third-party texts in the repository.

## Copied code

| Component | Source | Licence | Where in this repo |
|---|---|---|---|
| Abogen voice plugin contract and Kokoro plugin (`tts_plugin/types.py`, `engine.py`, `errors.py`, `plugins/kokoro/`), revision `1807822f5871d1c92740cb470c5c6e8328b8f851` | [denizsafak/abogen](https://github.com/denizsafak/abogen) | MIT, © 2025 Deniz Şafak (notice kept at the top of each file) | `src/sci2audio/voices/types.py`, `engine.py`, `errors.py`, `kokoro_engine.py` (D-52) |
| Python's HTML parser (`Lib/html/parser.py` and `Lib/_markupbase.py`), CPython tag `v3.13.18` | [python/cpython](https://github.com/python/cpython) | PSF-2.0, © 2001-2024 Python Software Foundation (notice, licence agreement and a summary of the changes kept at the top of the file) | `src/sci2audio/extraction/htmlparser.py`: the EPUB and Markdown readers parse with this copy, so broken markup reads the same on every Python version (#175, D-777) |

## Run-time dependencies

| Package | Licence | Why |
|---|---|---|
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Apache-2.0 OR BSD-3-Clause. The wheel bundles a PDFium binary (BSD-3-Clause) built with permissive libraries whose notices ship in the wheel's `licenses/BUILD_LICENSES`: FreeType (FTL), libjpeg-turbo (IJG, BSD-3-Clause), libpng, libtiff, zlib, OpenJPEG (BSD-2-Clause), Little CMS (MIT), ICU (Unicode), Abseil (Apache-2.0), AGG 2.3, HarfBuzz (MIT), Highway, simdutf, fast_float, dragonbox (Apache-2.0, MIT or BSD) | Reads PDFs: characters with font, size, weight and position, pictures and drawings (extraction, D-65) |
| [kokoro](https://github.com/hexgrad/kokoro) | Apache-2.0 | The Kokoro speech model's inference code (voices, D-48, D-52) |
| [misaki](https://github.com/hexgrad/misaki) (with its `en` extra, through kokoro) | Apache-2.0 | English letters-to-sounds for Kokoro (D-54) |
| [torch](https://pytorch.org) | BSD-3-Clause, with bundled parts under Apache-2.0, Apache-2.0 WITH LLVM-exception, BSD-2-Clause, BSL-1.0, ISC, MIT, Zlib (wheel metadata); the Linux wheels also bundle libgomp (GPL-3.0-or-later WITH GCC-exception-3.1) | Runs the speech model (D-48). CI and our lock use the CPU-only build on Linux |
| [numpy](https://numpy.org) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Audio samples; drawing and comparing glyph shapes (#618) |
| [requests](https://github.com/psf/requests) | Apache-2.0 | The user-started voice download (D-47) |
| [spaCy](https://spacy.io) | MIT | Loads the English model misaki uses for word classes (D-53) |
| [transformers](https://github.com/huggingface/transformers), [huggingface_hub](https://github.com/huggingface/huggingface_hub), tokenizers, safetensors, hf-xet | Apache-2.0 | Pulled in by kokoro. huggingface_hub is never used to download: `HF_HUB_OFFLINE=1` is always set (VA-04) |
| [espeakng-loader](https://github.com/thewh1teagle/espeakng-loader) (through misaki) | MIT for the loader (licence file in its repository; **its package metadata states no licence**, so CI lists it as checked by hand); it bundles the [espeak-ng](https://github.com/espeak-ng/espeak-ng) library and data, GPL-3.0-or-later | Pronounces words misaki does not know (fallback), and all German text for the German voice (#211); no system install needed |
| [phonemizer-fork](https://github.com/bootphon/phonemizer) (through misaki) | GPL-3.0-or-later | Calls espeak-ng for the fallback and for German |
| [num2words](https://github.com/savoirfairelinux/num2words) (through misaki) | LGPL-2.1 | Numbers as words inside misaki |
| [certifi](https://github.com/certifi/python-certifi), [tqdm](https://tqdm.github.io) (through requests and transformers) | MPL-2.0 (tqdm: MPL-2.0 AND MIT) | Certificates for the download; progress bars |
| All other packages these pull in (thinc, blis, srsly, pydantic, typer, regex, sympy, networkx, jinja2, ...) | MIT, BSD, Apache-2.0, ISC, PSF-2.0 or CNRI-Python | Checked on every PR by the `licences` CI job (`pip-licenses`) |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) 0.8.1 | BSD-2-Clause (the Python wrapper). The wheel bundles an FFmpeg program; its licence per platform is listed under "Bundled programs" below | Finds the ffmpeg program that output uses to write MP3 and M4B files (Q5, #69) |
| [markdown-it-py](https://github.com/executablebooks/markdown-it-py) 4.2 and [mdurl](https://github.com/executablebooks/mdurl) (through it) | MIT | Parses Markdown files (CommonMark, GFM tables, strikethrough) into HTML that extraction reads like an EPUB chapter (#74, D-338, D-340). Already pulled in through spaCy, typer and rich; now a direct dependency |
| [mdit-py-plugins](https://github.com/executablebooks/mdit-py-plugins) 0.6 | MIT | Footnotes, dollar maths and front matter for markdown-it-py (#74, D-338, D-339) |
| [platformdirs](https://github.com/tox-dev/platformdirs) 4.14.5 | MIT (no dependencies) | Finds the user's configuration folder on Windows, macOS and Linux for the settings file (app, #70) |
| [FastAPI](https://github.com/fastapi/fastapi) 0.162.5 | MIT | The local server and its JSON API (web, #76, D-101). Since 0.143 it depends on `opentelemetry-api` and instruments requests itself; sci2audio switches all of that off in code (D-195) |
| [Starlette](https://github.com/encode/starlette) 1.10.0 (through FastAPI, also imported) | BSD-3-Clause | The server's request handling, static files and templates (web) |
| [uvicorn](https://github.com/encode/uvicorn) 0.54.0, without the `standard` extra | BSD-3-Clause; pulls in [h11](https://github.com/python-hyper/h11) (MIT) and [click](https://github.com/pallets/click) (BSD-3-Clause) | Serves the app on 127.0.0.1 (web, D-192) |
| [Jinja2](https://github.com/pallets/jinja) 3.1.6 with [MarkupSafe](https://github.com/pallets/markupsafe) | BSD-3-Clause | The server-rendered pages (web, D-101) |
| [python-multipart](https://github.com/Kludex/python-multipart) 0.0.33 | Apache-2.0 | Reads opened files sent by the browser (web, D-101) |
| [pydantic](https://github.com/pydantic/pydantic) 2.14.3 with pydantic-core, annotated-types, typing-inspection | MIT | The API's request and response bodies (web); it was already pulled in by spaCy |
| [opentelemetry-api](https://github.com/open-telemetry/opentelemetry-python) 1.45.2 (through FastAPI) | Apache-2.0 | Not used: FastAPI's telemetry is switched off (D-195). Without an SDK and exporter, which sci2audio never installs, it records and sends nothing |
| [annotated-doc](https://github.com/fastapi/annotated-doc) 0.0.6, [anyio](https://github.com/agronholm/anyio) (through FastAPI) | MIT | Documentation markers; the server's async runtime |
| [pywebview](https://github.com/r0x0r/pywebview) 6.2.1, optional extra `window` | BSD-3-Clause (repository LICENSE; PyPI metadata "BSD 3-Clause License") | The app's own window (#215, D-797): the system's web engine, WKWebView on macOS and WebView2 on Windows. Only `sci2audio-app` loads it; the PyPI install leaves it out unless asked for |
| [bottle](https://github.com/bottlepy/bottle) 0.13.4, [proxy-tools](https://github.com/jtushman/proxy_tools) 0.1.0, typing-extensions (through pywebview) | MIT; typing-extensions PSF-2.0 | Imported by pywebview; its own web server (bottle) is never started, since the window opens sci2audio's server |
| [pythonnet](https://github.com/pythonnet/pythonnet) 3.2.1 and [clr-loader](https://github.com/pythonnet/clr-loader) 0.3.1 with [cffi](https://github.com/python-cffi/cffi) 2.1.1 and [pycparser](https://github.com/eliben/pycparser) 3.12 (through pywebview, Windows only) | pythonnet MIT; clr-loader MIT (repository LICENSE; **its package metadata states no licence**); cffi MIT-0 (as its metadata says); pycparser BSD-3-Clause | Lets pywebview drive WebView2 through .NET on Windows |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc) 13.0: pyobjc-core and the Cocoa, Quartz, Security, UniformTypeIdentifiers and WebKit frameworks (through pywebview, macOS only) | MIT | Lets pywebview drive WKWebView on macOS |
| [QtPy](https://github.com/spyder-ide/qtpy) 2.4.3 (in the lock for OpenBSD only; never installed on Linux, macOS or Windows) | MIT | pywebview's Qt layer, unused |

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

The installers (next section) never carry these binaries: they leave imageio-ffmpeg's program out and bring an audio-only FFmpeg of their own (D-798).

## The installers (#215, #13, D-797, D-798)

The macOS, Windows and Linux installers bundle sci2audio with the run-time dependencies above (the `window` extra included) and the parts below. Each installer carries a `licenses/` folder: sci2audio's `LICENSE`, this file, the licence texts of every Python package (`python-packages.txt`, made by `pip-licenses`; the build stops on a refused licence, as the `licences` CI job does), Python's licence, FFmpeg's and LAME's licences and build configuration, and `SOURCE.txt`, which names where the complete source is: the sdist and `sci2audio-<version>-sources.tar` on the release page (FFmpeg, LAME and espeak-ng source archives pinned by SHA-256, with the build script).

| Component | Licence | Why |
|---|---|---|
| [FFmpeg](https://ffmpeg.org) 9.0.2, built from the pinned source archive by `packaging/ffmpeg/build.sh` without `--enable-gpl` or `--enable-nonfree`: audio and the few formats sci2audio and its tests use (PCM, MP3, AAC in M4B, ffmetadata, JPEG/PNG covers, SRT/WebVTT read back), files and pipes only, no network protocol | LGPL-2.1-or-later | Writes the MP3 and M4B files (output); the installers point `IMAGEIO_FFMPEG_EXE` at it |
| [LAME](https://lame.sourceforge.io) 3.100, linked into that FFmpeg | LGPL-2.0-or-later | The MP3 encoder |
| zlib (linked into FFmpeg for PNG covers; on Windows statically, with the MinGW-w64 GCC runtime and winpthreads) | Zlib; GCC runtime: GPL-3.0-or-later WITH GCC-exception-3.1; winpthreads: MIT and BSD-3-Clause | Built in, nothing to install |
| [CPython](https://www.python.org) 3.12 (python-build-standalone, as uv installs it), frozen with the program | PSF-2.0 (with the licences of its bundled libraries, in Python's LICENSE.txt) | Runs sci2audio |
| [PyInstaller](https://pyinstaller.org) 6.22.3 and pyinstaller-hooks-contrib 2026.10 (dependency group `installer`; with altgraph, macholib, pefile, pywin32-ctypes as its own dependencies, build time only) | GPL-2.0-or-later with the PyInstaller bootloader exception (hooks-contrib: GPL-2.0-or-later or Apache-2.0); altgraph, macholib MIT; pefile MIT; pywin32-ctypes BSD-3-Clause | Freezes Python and sci2audio into one folder. Its bootloader starts the programs; the exception allows any licence for the bundled program, and sci2audio is GPL anyway |
| [Inno Setup](https://jrsoftware.org/isinfo.php) 6.7.4 (Windows; download pinned by the SHA-256 in the publisher's signed `.issig` file) | Inno Setup License (permissive, zlib-style; commercial use and redistribution allowed with the copyright notice kept) | Makes `setup.exe`; its installer and uninstaller stub becomes part of that file |
| [appimagetool](https://github.com/AppImage/appimagetool) 1.9.1 and the [type-2 runtime](https://github.com/AppImage/type2-runtime) `20251108` (Linux; both pinned by SHA-256) | MIT (the static runtime links [libfuse](https://github.com/libfuse/libfuse) 3.15.0, LGPL-2.1, patched by the runtime, and [squashfuse](https://github.com/vasi/squashfuse) 0.5.2, BSD-2-Clause; the source of all three is in `sci2audio-<version>-sources.tar` on the release page) | Makes the AppImage; the runtime is the AppImage's first part and mounts it |
| The app icon (`packaging/icons`, drawn by `make_icons.py` in this repository) | GPL-3.0-or-later, as sci2audio | The app's icon |

## Bundled fonts (shipped in the wheel, served only by the local server)

The interface's two typefaces (design "The Working Reader", D-663; #385, D-670). Both are under the **SIL Open Font License 1.1** (`OFL-1.1`); neither notice names a Reserved Font Name. The files are used unmodified, exactly as the named npm release ships them, and the licence text of each family ships beside them in `src/sci2audio/web/static/fonts/` (`OFL-atkinson.txt`: © 2020 Braille Institute of America, Inc.; `OFL-literata.txt`: © 2017 The Literata Project Authors). Each subset is loaded only when a page uses its characters (`unicode-range`). A test checks every file below against its SHA-256 and that the wheel carries each font and both licences.

The design prototype in `docs/design/prototype/fonts/` (moved from `dubidu22/sci2audio-design` on 20 Nov 2026) carries the same two families, Atkinson Hyperlegible (400, 400 italic, 700) and Literata (regular, italic), unmodified, with the same two OFL texts beside them. It is a design record, not part of the wheel.

| File in `src/sci2audio/web/static/fonts/` | Subset | Upstream release | SHA-256 |
|---|---|---|---|
| `atkinson-hyperlegible-latin-400-normal.woff2` | Latin, 400 | [@fontsource/atkinson-hyperlegible](https://www.npmjs.com/package/@fontsource/atkinson-hyperlegible/v/5.3.0) 5.3.0 (npm tarball `atkinson-hyperlegible-5.3.0.tgz`, `files/atkinson-hyperlegible-latin-400-normal.woff2`), built from Atkinson Hyperlegible 1.006 | `d64ba838ef5472bba248620ec4fd8b5aa7cf0db2908e0bb230600caf279ba7bc` |
| `atkinson-hyperlegible-latin-400-italic.woff2` | Latin, 400 italic | [@fontsource/atkinson-hyperlegible](https://www.npmjs.com/package/@fontsource/atkinson-hyperlegible/v/5.3.0) 5.3.0 (npm tarball `atkinson-hyperlegible-5.3.0.tgz`, `files/atkinson-hyperlegible-latin-400-italic.woff2`), built from Atkinson Hyperlegible 1.006 | `bc8825fd435d4aa8e31449937826d583a7daaae15a83832c91b38375131ebf08` |
| `atkinson-hyperlegible-latin-700-normal.woff2` | Latin, 700 | [@fontsource/atkinson-hyperlegible](https://www.npmjs.com/package/@fontsource/atkinson-hyperlegible/v/5.3.0) 5.3.0 (npm tarball `atkinson-hyperlegible-5.3.0.tgz`, `files/atkinson-hyperlegible-latin-700-normal.woff2`), built from Atkinson Hyperlegible 1.006 | `140e2bd25a7315c8a062508391426b0d8c3297400c947b8d847be28f73a199f0` |
| `atkinson-hyperlegible-latin-ext-400-normal.woff2` | Latin Extended, 400 | [@fontsource/atkinson-hyperlegible](https://www.npmjs.com/package/@fontsource/atkinson-hyperlegible/v/5.3.0) 5.3.0 (npm tarball `atkinson-hyperlegible-5.3.0.tgz`, `files/atkinson-hyperlegible-latin-ext-400-normal.woff2`), built from Atkinson Hyperlegible 1.006 | `61eeb0eb8b881a84d069e67be1723f5b353b0b9b866ad8e7ad9dba66cdc4dabd` |
| `atkinson-hyperlegible-latin-ext-400-italic.woff2` | Latin Extended, 400 italic | [@fontsource/atkinson-hyperlegible](https://www.npmjs.com/package/@fontsource/atkinson-hyperlegible/v/5.3.0) 5.3.0 (npm tarball `atkinson-hyperlegible-5.3.0.tgz`, `files/atkinson-hyperlegible-latin-ext-400-italic.woff2`), built from Atkinson Hyperlegible 1.006 | `90d887d541fe6e912d15f826aae6ca1190efcf172b65401704472475ed771049` |
| `atkinson-hyperlegible-latin-ext-700-normal.woff2` | Latin Extended, 700 | [@fontsource/atkinson-hyperlegible](https://www.npmjs.com/package/@fontsource/atkinson-hyperlegible/v/5.3.0) 5.3.0 (npm tarball `atkinson-hyperlegible-5.3.0.tgz`, `files/atkinson-hyperlegible-latin-ext-700-normal.woff2`), built from Atkinson Hyperlegible 1.006 | `840ced16f975d8abc2594b436d0206649e0c2a7327e36750ff849d3d37c3c02e` |
| `literata-latin-wght-normal.woff2` | Latin, roman | [@fontsource-variable/literata](https://www.npmjs.com/package/@fontsource-variable/literata/v/5.3.0) 5.3.0 (npm tarball `literata-5.3.0.tgz`, `files/literata-latin-wght-normal.woff2`), built from Literata 3.103 (variable, weights 200 to 900) | `9adbeac5b167fe5ad6c49d9e29aa0c76e2f1bb3b46bf4ebf12a9eca7d3525384` |
| `literata-latin-wght-italic.woff2` | Latin, italic | [@fontsource-variable/literata](https://www.npmjs.com/package/@fontsource-variable/literata/v/5.3.0) 5.3.0 (npm tarball `literata-5.3.0.tgz`, `files/literata-latin-wght-italic.woff2`), built from Literata 3.103 (variable, weights 200 to 900) | `ab198d6616c7cc966f26a4a5b28a3977dc47439640f09d9b3361226bd465c404` |
| `literata-latin-ext-wght-normal.woff2` | Latin Extended, roman | [@fontsource-variable/literata](https://www.npmjs.com/package/@fontsource-variable/literata/v/5.3.0) 5.3.0 (npm tarball `literata-5.3.0.tgz`, `files/literata-latin-ext-wght-normal.woff2`), built from Literata 3.103 (variable, weights 200 to 900) | `46792f7cd10b28fb512161caeaaa11b049feb2221ccaa72bb4d4ccc286199155` |
| `literata-latin-ext-wght-italic.woff2` | Latin Extended, italic | [@fontsource-variable/literata](https://www.npmjs.com/package/@fontsource-variable/literata/v/5.3.0) 5.3.0 (npm tarball `literata-5.3.0.tgz`, `files/literata-latin-ext-wght-italic.woff2`), built from Literata 3.103 (variable, weights 200 to 900) | `ba0e6a12e2f0a1f5d455c23c47068b71f9898c571dcb92dab385294ebdae3e74` |
| `literata-greek-wght-normal.woff2` | Greek, roman | [@fontsource-variable/literata](https://www.npmjs.com/package/@fontsource-variable/literata/v/5.3.0) 5.3.0 (npm tarball `literata-5.3.0.tgz`, `files/literata-greek-wght-normal.woff2`), built from Literata 3.103 (variable, weights 200 to 900) | `393643556e420af45f8f0854c30f00e17ac52e85f1df4fd4ae2f2a29e0d279f1` |
| `literata-greek-wght-italic.woff2` | Greek, italic | [@fontsource-variable/literata](https://www.npmjs.com/package/@fontsource-variable/literata/v/5.3.0) 5.3.0 (npm tarball `literata-5.3.0.tgz`, `files/literata-greek-wght-italic.woff2`), built from Literata 3.103 (variable, weights 200 to 900) | `e43ead3dd6acf3c07005a1f724d99522065b9363ae9fc6689f544c6782995730` |

Release checksums as published on npm: `@fontsource/atkinson-hyperlegible@5.3.0` integrity `sha512-Sp8Ve8+rQmENY2Lv02VH7sLpntzTTvnncnJMTbRE7DX6TLxGraN4ykZfzaUWIoCFmaomwkvNiqmlPkrKBuDoSA==`; `@fontsource-variable/literata@5.3.0` integrity `sha512-1Jw7xvOcoGyB83lxB2nG4bfNbqtX2/TTbdh9sHAOmU064SvmSdulDtA5RBu5JYWf64fdaKX7xU+z3GO1T2bCHA==`. Fontsource packages the Google Fonts builds of [Atkinson Hyperlegible](https://fonts.google.com/specimen/Atkinson+Hyperlegible) (Braille Institute) and [Literata](https://github.com/googlefonts/literata); the font version is the one in each file's name table. The icons of the interface are drawn in this repository (`templates/_icons.html`, from the design repository's prototype) and are not third-party.

## Drawings of letters (generated from fonts; no font file ships, #618, D-789)

`src/sci2audio/extraction/data/letter-shapes.json.gz` holds, for each style below, the advance widths of 216 letters and their drawings on a 24 × 30 grid, made by `scripts/letter_shapes.py shapes` with sci2audio's own glyph reader. Letter recognition compares the glyphs of PDF fonts that carry no letters (#442) with them. The file holds drawings and widths, not the fonts: no outline, hinting or font program is copied, and no font file is part of sci2audio. Each release is downloaded only when a person runs the script, and checked against the SHA-256 below before it is opened. Each licence was confirmed in the release itself: the `name` table of every font file (name IDs 0, 13 and 14) and, for Carlito, the `LICENSE` file it ships.

| Family (twin of) | Styles | Release | Licence | Copyright |
|---|---|---|---|---|
| Tinos 1.31 (Times New Roman) | Regular, Bold, Italic, BoldItalic | ChromeOS `croscorefonts-1.31.0.tar.bz2`, SHA-256 `672c3487883ec1ef83d9254240d4327b014212abc823d06d15816095867315e1`, from the [ChromeOS mirror](https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/croscorefonts-1.31.0.tar.bz2) | Apache-2.0 | © 2010-2014 Google Inc. |
| Arimo 1.31 (Arial) | Regular, Bold, Italic, BoldItalic | the same `croscorefonts-1.31.0.tar.bz2` | Apache-2.0 | © 2010-2014 Google Inc. |
| Cousine 1.21 (Courier New) | Regular, Bold, Italic, BoldItalic | the same `croscorefonts-1.31.0.tar.bz2` | Apache-2.0 | © 2010 Google Inc. |
| Caladea 1.002 (Cambria) | Regular, Bold, Italic, BoldItalic | ChromeOS `crosextrafonts-20130214.tar.gz`, SHA-256 `c48d1c2fd613c9c06c959c34da7b8388059e2408d2bb19845dc3ed35f76e4d09`, from the [ChromeOS mirror](https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/crosextrafonts-20130214.tar.gz) | Apache-2.0 | © 2012 Huerta Tipográfica |
| Carlito 1.103 (Calibri) | Regular, Bold, Italic, BoldItalic | ChromeOS `crosextrafonts-carlito-20130920.tar.gz`, SHA-256 `4bd12b6cbc321c1cf16da76e2c585c925ce956a08067ae6f6c64eff6ccfdaf5a`, from the [ChromeOS mirror](https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/crosextrafonts-carlito-20130920.tar.gz) | OFL-1.1 (Reserved Font Name "Carlito") | © 2010-2013 tyPoland Łukasz Dziedzic |

Carlito is under the SIL Open Font License 1.1: its drawings are output made from the font, not the font or a modified version of it, so the OFL's conditions for the font itself (shipping the licence beside it, the Reserved Font Name) do not apply to the data file (D-789); the row above names the font and its licence all the same.

## Models and voices (downloaded on first use, never bundled)

Fetched only when the user starts the voice download (`sci2audio.voices.download_voice_files`), pinned by revision and sha256; the licences are shown before the download (VA-03).

| Model or voice | Source | Licence | Notes |
|---|---|---|---|
| Kokoro-82M model (`config.json`, `kokoro-v1_0.pth`) and its 28 English voice packs (`voices/af_*`, `am_*`, `bf_*`, `bm_*`), revision `f3ff3571791e39611d31c381e3a41a3af07b4987` | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache-2.0 | 327 MB plus 0.5 MB per voice. The model card states it was trained only on permissive or non-copyrighted audio (public domain, Apache/MIT-licensed audio, CC BY data it lists) |
| Kokoro German model by Thorsten-Voice (`config.json`, `model.pth` = epoch 5) and its voice pack `voices/thorsten.pt` (voice `dm_thorsten`), revision `734e593d320a3d876bede7020f773dfd481a0cc7` | [Thorsten-Voice/Kokoro](https://huggingface.co/Thorsten-Voice/Kokoro) | Apache-2.0 (model card) | 327 MB plus 0.5 MB (#211, D-467). A fine-tune of Kokoro-82M (above, Apache-2.0) on the [Thorsten-Voice](https://www.thorsten-voice.de/) dataset, which its speaker Thorsten Müller released as CC0-1.0 (public domain); the model card names that dataset as the only training data. `config.json` is byte-identical to Kokoro-82M's |
| spaCy English model `en_core_web_sm` 3.8.0 (wheel, unpacked into the model folder) | [explosion/spacy-models release](https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0) | MIT | 12.8 MB. Not on PyPI, so not a package dependency. Its `LICENSES_SOURCES` names OntoNotes 5 (licensed to Explosion), ClearNLP and WordNet 3.0 (permissive) as training sources |

## Test-only components (never installed with sci2audio)

| Component | Licence | Used for |
|---|---|---|
| [Schemathesis](https://github.com/schemathesis/schemathesis) 4.33.4 (dev group) with harfile, hypothesis-graphql, graphql-core, jsonschema-rs, pyrate-limiter (MIT) and Werkzeug (BSD-3-Clause) | MIT | Tests the server against its OpenAPI document (#7) |
| [httpx](https://github.com/encode/httpx) 0.28.1 with httpcore (dev group) | BSD-3-Clause | FastAPI's `TestClient` (#7) |
| [Playwright for Python](https://github.com/microsoft/playwright-python) 1.65.1 (dev group) with [greenlet](https://github.com/python-greenlet/greenlet) 3.5.6 (MIT AND PSF-2.0) | Apache-2.0 | Drives a real browser through the interface (#77, #8, D-259). The browsers themselves (Chromium, Firefox, WebKit) are downloaded by CI with `playwright install`, never by sci2audio or its tests |
| [pytest-playwright](https://github.com/microsoft/playwright-pytest) 0.10.0 (dev group) with [python-slugify](https://github.com/un33k/python-slugify) 9.1.3 (MIT) and [text-unidecode](https://github.com/kmike/text-unidecode) 1.3 (Artistic-1.0 **or** GPL-2.0-or-later; sci2audio uses it under GPL-2.0-or-later) | Apache-2.0 | The `page` and browser fixtures for the browser tests |
| [axe-playwright-python](https://github.com/pamelafox/axe-playwright-python) 0.1.8 (dev group) | MIT; it bundles [axe-core](https://github.com/dequelabs/axe-core) 4.12.1 (`axe.min.js`, MPL-2.0, © Deque Systems, notice kept in the file) | The accessibility checks on every page state (AQ-01, D-257) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with ctranslate2, onnxruntime, PyAV (dependency group `asr`) | MIT (PyAV: BSD-3-Clause; its bundled FFmpeg includes x264 and x265, so GPL-2.0-or-later) | Nightly speech-recognition round trip (#9) |
| Whisper `small` for CTranslate2, revision `536b0662742c02347bc0e980a01041f333bce120` | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small), MIT | Same; downloaded by the nightly workflow only |
| [OWASP ZAP](https://github.com/zaproxy/zaproxy) 2.17.0, Docker image `ghcr.io/zaproxy/zaproxy` pinned by digest in `scripts/zap_scan.py` | Apache-2.0 (the image also holds a Java runtime and other programs under their own licences; it is pulled and run, never redistributed) | The baseline scan of the local server (#12, AQ-03, D-364 to D-372). Pulled by the ZAP workflow, or by a developer who runs the script; never by sci2audio or its tests |
| [hatchling](https://github.com/pypa/hatch) with pathspec, tomlkit, trove-classifiers (dependency group `dev`; also the build backend) | MIT (pathspec: MPL-2.0; tomlkit: MIT; trove-classifiers: Apache-2.0) | Test that the wheel ships the package data files (#68) |
| Subsets of [Tinos](https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/croscorefonts-1.31.0.tar.bz2) 1.31, Arimo 1.31 and Cousine 1.21 Regular (`tests/fixtures/fonts/tinos-regular-subset.ttf`, `arimo-regular-subset.ttf`, `cousine-regular-subset.ttf`, printable ASCII and German's letters and marks, made by `scripts/letter_shapes.py fixtures`; the copyright and licence name records kept in each file) | Apache-2.0, © 2010-2014 Google Inc. (Cousine © 2010) | The PDFs whose fonts have no Unicode source that letter recognition is tested on (#618) |
| [fontTools](https://github.com/fonttools/fonttools) 4.55.3, run by hand with `uv run --with fonttools==4.55.3` (not a dependency) | MIT | Makes those subsets (`scripts/letter_shapes.py fixtures`) |

## External programs (installed by the user)

| Program | Licence | Used for |
|---|---|---|
| *(none yet)* | | |
