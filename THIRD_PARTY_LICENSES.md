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

## Models and voices (downloaded on first use, never bundled)

| Model or voice | Source | Licence | Notes |
|---|---|---|---|
| *(none yet)* | | | |

## External programs (installed by the user)

| Program | Licence | Used for |
|---|---|---|
| *(none yet)* | | |
