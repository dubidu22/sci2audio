# Third-party licences

Every third-party component that sci2audio bundles, copies code from, depends on at run time or downloads must be listed here **in the same pull request that adds it** (see the licence gate in `CLAUDE.md`).

Not allowed: AGPL code, non-commercial or "research only" licences, models or voices with unclear training-data rights, and third-party texts in the repository.

## Copied code

| Component | Source | Licence | Where in this repo |
|---|---|---|---|
| *(none yet)* | | | |

## Run-time dependencies

| Package | Licence | Why |
|---|---|---|
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Apache-2.0 OR BSD-3-Clause. The wheel bundles a PDFium binary (BSD-3-Clause) built with permissive libraries whose notices ship in the wheel's `licenses/BUILD_LICENSES`: FreeType (FTL), libjpeg-turbo (IJG, BSD-3-Clause), libpng, libtiff, zlib, OpenJPEG (BSD-2-Clause), Little CMS (MIT), ICU (Unicode), Abseil (Apache-2.0), AGG 2.3, HarfBuzz (MIT), Highway, simdutf, fast_float, dragonbox (Apache-2.0, MIT or BSD) | Reads PDFs: characters with font, size, weight and position, pictures and drawings (extraction, D-65) |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) 0.8.1 | BSD-2-Clause (the Python wrapper). The wheel bundles an FFmpeg program; its licence per platform is listed under "Bundled programs" below | Finds the ffmpeg program that output uses to write MP3 and M4B files (Q5, #69) |

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

| Model or voice | Source | Licence | Notes |
|---|---|---|---|
| *(none yet)* | | | |

## External programs (installed by the user)

| Program | Licence | Used for |
|---|---|---|
| *(none yet)* | | |
