"""espeak-ng's data folder, checked before espeak-ng starts (#663).

Both voices start the espeak-ng that espeakng-loader ships: German pronounces through
misaki's `EspeakG2P`, and kokoro's English pipeline builds misaki's `EspeakFallback`.
espeak-ng copies its data folder into a fixed buffer (`path_home[N_PATH_HOME]` in
`speech.h`: 160 bytes on POSIX, 230 on Windows). A longer path is cut, espeak-ng falls back
to the folder baked in when the wheel was built, finds no `phontab` there and calls
`exit(1)`, which ends the whole process: the app's server mid-job, or pytest without a
summary. On Windows espeak-ng's `snprintf` is MSVC's `_snprintf`, which leaves a cut path
without its terminating zero byte, so what happens there is undefined. A missing or
unreadable `phontab` ends the process the same way. `check_espeak_data`
raises `ModelLoadError` for both before espeak-ng can.

misaki is imported only inside the functions that need it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from sci2audio.voices.errors import ModelLoadError

# the buffer less its terminating zero byte
ESPEAK_PATH_LIMIT = 229 if sys.platform == "win32" else 159


def wheel_data_path() -> str:
    """The espeak-ng data folder misaki hands to espeak-ng: espeakng-loader's own."""
    # through misaki, which imports espeakng-loader: it is not a direct dependency
    import misaki.espeak

    return str(misaki.espeak.espeakng_loader.get_data_path())


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
