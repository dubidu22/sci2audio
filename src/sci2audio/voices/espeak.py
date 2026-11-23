"""espeak-ng's data folder, checked before espeak-ng starts (#663).

Both voices start the espeak-ng that espeakng-loader ships: German pronounces through
misaki's `EspeakG2P`, and kokoro's English pipeline builds misaki's `EspeakFallback`.
espeak-ng copies its data folder into a fixed buffer (`path_home[N_PATH_HOME]` in
`speech.h`: 160 bytes on POSIX, 230 on Windows). A longer path is cut, espeak-ng falls back
to the folder baked in when the wheel was built, finds no `phontab` there and calls
`exit(1)`, which ends the whole process: the app's server mid-job, or pytest without a
summary. On Windows espeak-ng's `snprintf` is MSVC's `_snprintf`, which leaves a cut copy
without its terminating zero byte. The first copy is the folder plus `/espeak-ng-data`, so
from 215 bytes on Windows espeak-ng reads past its buffer: undefined. A missing or
unreadable `phontab` ends the process the same way. phonemizer hands espeak-ng the folder
as UTF-8 bytes, which espeak-ng checks with the narrow C API before it sets a UTF-8 locale:
Windows reads them in the ANSI code page, so a non-ASCII folder names another, missing one
there unless that code page is UTF-8 (#744). `check_espeak_data` raises `ModelLoadError`
for all of these before espeak-ng can.
"""

from __future__ import annotations

import codecs
import locale
import os
import sys
from pathlib import Path
from typing import Any

from sci2audio.voices.errors import ModelLoadError

# espeak-ng copies the folder plus "/espeak-ng-data" first, then the folder alone, into
# path_home[N_PATH_HOME]; POSIX snprintf cuts and terminates the first copy, so only the
# second must fit there, while MSVC's _snprintf leaves a copy that does not fit unterminated
ESPEAK_PATH_LIMIT = 230 - 1 - len("/espeak-ng-data") if sys.platform == "win32" else 159


def wheel_data_path() -> str:
    """The espeak-ng data folder misaki hands to espeak-ng: espeakng-loader's own."""
    # through misaki, which imports espeakng-loader: it is not a direct dependency
    import misaki.espeak

    return str(misaki.espeak.espeakng_loader.get_data_path())


def windows_ansi_encoding() -> str | None:
    """The code page Windows reads espeak-ng's narrow paths in; `None` where bytes are kept."""
    return locale.getencoding() if sys.platform == "win32" else None


def check_espeak_data(folder: str | Path | None = None) -> None:
    """Raise `ModelLoadError` where espeak-ng could not use `folder` (default: the wheel's).

    The path is resolved as phonemizer resolves it, and measured in bytes as espeak-ng
    copies it.
    """
    path = Path(wheel_data_path() if folder is None else folder).resolve()
    size = len(os.fsencode(path))
    if size > ESPEAK_PATH_LIMIT:
        raise ModelLoadError(
            f"espeak-ng cannot use its data folder {path}: the path is {size} bytes, "
            f"espeak-ng reads at most {ESPEAK_PATH_LIMIT} and would end the program (#663); "
            "install or check out sci2audio in a folder with a shorter path"
        )
    encoding = windows_ansi_encoding()
    if encoding is not None and not str(path).isascii() and codecs.lookup(encoding).name != "utf-8":
        raise ModelLoadError(
            f"espeak-ng cannot use its data folder {path}: Windows reads its name in the "
            f"code page {encoding}, where a character outside ASCII names another folder, "
            "and espeak-ng would end the program (#744); install or check out sci2audio in "
            "a folder whose path holds only ASCII characters"
        )
    phontab = path / "phontab"
    if not (phontab.is_file() and os.access(phontab, os.R_OK)):
        raise ModelLoadError(
            f"espeak-ng cannot read {phontab}; it would end the program (#663); reinstall sci2audio"
        )


def espeak_g2p(language: str) -> Any:
    """misaki's `EspeakG2P` for `language`, after `check_espeak_data`."""
    check_espeak_data()
    from misaki.espeak import EspeakG2P

    return EspeakG2P(language=language)
