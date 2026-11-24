"""Writing the job's files so that no half-written file is ever left (the #69 rule).

Each file is written under a temporary name of its own (`.<name>.<pid>-<random>.partial`)
next to its target and renamed when complete, so two writers of the same file never share
a temporary file and the last rename wins (#778); on any error the partial files are
removed. `write_texts` writes
all its files before it renames any, so a full disk leaves every earlier file as it was,
and without `overwrite` it puts either all of its files in place or none.
An existing file is only replaced with `overwrite=True`; without it, a file that appeared
at the target during the run is never replaced either. A run killed outright may leave a
partial file behind; the next write of that file removes it once its process is gone and
it is an hour old (`STALE_AFTER_SECONDS`).
"""

from __future__ import annotations

import contextlib
import os
import re
import secrets
import sys
import time
from collections.abc import Mapping
from pathlib import Path

STALE_AFTER_SECONDS = 3600
"""A partial file is swept only when it is older than this. A process id means something
only on its own machine and in its own PID namespace; in a folder shared with another
machine or a container, a live writer's file may name a process that looks gone here, and
a live writer finishes within seconds, so an hour old is a leftover."""


def partial_path(target: Path) -> Path:
    """A temporary name to write `target` under: new on every call, in the same folder, with
    the process id and a random part so that no two writes ever share one."""
    return target.with_name(f".{target.name}.{os.getpid():x}-{secrets.token_hex(4)}.partial")


def _process_is_gone(pid: int) -> bool:
    """True only if no process has this id; any doubt counts as "still there"."""
    try:
        if sys.platform == "win32":
            import ctypes

            access = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
            handle = ctypes.windll.kernel32.OpenProcess(access, False, pid)  # type: ignore[attr-defined,unused-ignore]
            if not handle:
                return ctypes.GetLastError() == 87  # ERROR_INVALID_PARAMETER: no such process
            code = ctypes.c_ulong()
            known = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))  # type: ignore[attr-defined,unused-ignore]
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined,unused-ignore]
            return bool(known) and code.value != 259  # STILL_ACTIVE
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (OSError, ValueError, OverflowError):
        return False
    return False


def _remove_left_behind(target: Path) -> None:
    """Remove the partial files that a run killed outright left for `target`: those named
    for a process that is gone and that are older than `STALE_AFTER_SECONDS`. Never one of
    this process (another thread may be writing), of a live process, or a young one."""
    pattern = re.compile(rf"\.{re.escape(target.name)}\.([0-9a-f]+)-[0-9a-f]{{8}}\.partial")
    with contextlib.suppress(OSError):
        for entry in os.scandir(target.parent):
            found = pattern.fullmatch(entry.name)
            if found is None:
                continue
            pid = int(found.group(1), 16)
            if pid == os.getpid():
                continue
            with contextlib.suppress(OSError):  # gone meanwhile, or not ours to remove
                old = time.time() - entry.stat().st_mtime > STALE_AFTER_SECONDS
                if old and _process_is_gone(pid):
                    os.unlink(entry.path)


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
    for target in contents:
        _remove_left_behind(target)
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
