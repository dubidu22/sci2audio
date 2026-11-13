"""One job per working folder, also across processes (D-161).

`work_folder_lock` holds an operating-system lock on `<work>/job.lock` while a job runs:
`fcntl.flock` on Linux and macOS, `msvcrt.locking` on Windows. The system releases it when
the process ends, even when it is killed, so a crashed job never leaves a stale lock. The
lock file itself stays; it holds nothing.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from sci2audio.app.job import JobBusyError, JobError

LOCK_NAME = "job.lock"


def _try_lock(file: IO[bytes]) -> bool:
    if sys.platform == "win32":
        import msvcrt

        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:  # BlockingIOError: someone else holds it
        return False
    return True


def _unlock(file: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(file.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def work_folder_lock(work: Path) -> Iterator[None]:
    """Hold the working folder's lock; JobBusyError if another job holds it."""
    try:
        work.mkdir(parents=True, exist_ok=True)
        file = (work / LOCK_NAME).open("a+b")
    except OSError as error:
        raise JobError(
            f"could not use the working folder {work.name}: {error.strerror or error}"
        ) from error
    try:
        if not _try_lock(file):
            raise JobBusyError(
                "another sci2audio job is working on this file's working folder; "
                "wait until it has finished"
            )
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                _unlock(file)
    finally:
        file.close()
