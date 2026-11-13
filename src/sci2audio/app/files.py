"""Writing the job's files so that no half-written file is ever left (the #69 rule).

Each file is written under a temporary name (`.<name>.partial`) next to its target and
renamed when complete; on any error the partial files are removed. `write_texts` writes
all its files before it renames any, so a full disk leaves every earlier file as it was,
and without `overwrite` it puts either all of its files in place or none.
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


def write_bytes_atomically(target: Path, data: bytes, *, overwrite: bool) -> None:
    """Write `data` to `target`, all of it or nothing (as `write_texts`)."""
    _write_all({target: data}, overwrite=overwrite)


def write_texts(texts: Mapping[Path, str], *, overwrite: bool) -> None:
    """Write each text to its file: all partial files first, then rename them in order.

    Raises FileExistsError if a target exists and `overwrite` is false, OSError if writing
    fails. No partial file is left, and if writing (not renaming) fails no target changed.
    Without `overwrite` the set is all or nothing: if one rename fails (a target appeared
    during the run), the targets already renamed by this call are removed again; they did
    not exist before, so nothing of the person's is deleted. With `overwrite`, a rename
    that fails after earlier ones succeeded cannot be undone (the old files are gone); on
    one file system, after every file was written in full, that is not expected to happen.
    """
    _write_all(texts, overwrite=overwrite)


def _write_all(contents: Mapping[Path, str | bytes], *, overwrite: bool) -> None:
    partials = {target: partial_path(target) for target in contents}
    committed: list[Path] = []
    try:
        for target, content in contents.items():
            _write_partial(partials[target], content)
        for target, partial in partials.items():
            _commit(partial, target, overwrite)
            committed.append(target)
    except BaseException:
        for partial in partials.values():
            with contextlib.suppress(OSError):
                partial.unlink(missing_ok=True)
        if not overwrite:
            for target in committed:
                with contextlib.suppress(OSError):
                    target.unlink(missing_ok=True)
        raise


def _write_partial(partial: Path, content: str | bytes) -> None:
    if isinstance(content, bytes):
        with partial.open("wb") as binary:
            binary.write(content)
            binary.flush()
            os.fsync(binary.fileno())
    else:
        with partial.open("w", encoding="utf-8", newline="\n") as text:
            text.write(content)
            text.flush()
            os.fsync(text.fileno())


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
