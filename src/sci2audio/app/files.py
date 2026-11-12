"""Writing the job's files so that no half-written file is ever left (the #69 rule).

Each file is written under a temporary name (`.<name>.partial`) next to its target and
renamed when complete; on any error the partial files are removed. `write_texts` writes
all its files before it renames any, so a full disk leaves every earlier file as it was.
An existing file is only replaced with `overwrite=True`; without it, a file that appeared
at the target during the run is never replaced either. A run killed outright may leave a
partial file behind; the next run writes over it.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Mapping
from pathlib import Path


def partial_path(target: Path) -> Path:
    """The temporary name a file is written under."""
    return target.with_name(f".{target.name}.partial")


def write_text_atomically(target: Path, text: str, *, overwrite: bool) -> None:
    """Write `text` (UTF-8, "\\n" line ends) to `target`, all of it or nothing."""
    write_texts({target: text}, overwrite=overwrite)


def write_texts(texts: Mapping[Path, str], *, overwrite: bool) -> None:
    """Write each text to its file: all partial files first, then rename them in order.

    Raises FileExistsError if a target exists and `overwrite` is false, OSError if writing
    fails; no partial file is left, and if writing (not renaming) fails no target changed.
    """
    partials = {target: partial_path(target) for target in texts}
    try:
        for target, text in texts.items():
            with partials[target].open("w", encoding="utf-8", newline="\n") as file:
                file.write(text)
                file.flush()
                os.fsync(file.fileno())
        for target, partial in partials.items():
            _commit(partial, target, overwrite)
    except BaseException:
        for partial in partials.values():
            with contextlib.suppress(OSError):
                partial.unlink(missing_ok=True)
        raise


def _commit(partial: Path, target: Path, overwrite: bool) -> None:
    if overwrite:
        os.replace(partial, target)
    elif sys.platform == "win32":
        os.rename(partial, target)  # refuses an existing target on Windows
    else:
        try:
            os.link(partial, target)  # refuses an existing target
        except FileExistsError:
            raise
        except OSError:  # no hard links here (FAT, some network drives): check, then rename
            if target.exists():
                raise FileExistsError(f"file appeared during the run: {target}") from None
            os.rename(partial, target)
        else:
            partial.unlink()
