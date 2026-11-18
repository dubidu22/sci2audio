"""Project data folders, and the move of the old working folders into them (#469).

Before #469 each document's working folder was `<user cache>/sci2audio/jobs/<id>/`; a
system clean-up could delete it with the person's markers, listening position and copy of
the file. It is now `<user data>/sci2audio/projects/<id>/`, with the same contents and the
same name (D-747). `migrate_all` moves every old folder over (the server, before it serves
anything); `migrate_one` moves one (the command line, for the file it was given).

The move never loses or replaces a file and can be cut off at any point (D-748):

- A folder that is a link or a Windows junction, or that a job holds (its `job.lock`,
  D-161), is left where it is; until it is moved, it is used where it is
  (`project_folder`), so no document is ever missing.
- The new folder does not exist yet: one rename of the whole folder, atomic, so before it
  the project is old and after it new. A rename across file systems (`EXDEV`) copies the
  folder to `projects/.moving-<id>/`, checks every copy's size and SHA-256 against its
  original, renames the copy into place, and only then removes the originals.
- The new folder exists already (a move cut off after its rename, or the same file opened
  in the new version first): file by file. A file the new folder lacks is moved in; the
  same file (size and SHA-256) is removed from the old folder; a different file is moved
  to `from-earlier-version/` in the new folder, never over a file. A file is only ever put
  in place by a hard link, which refuses a name that exists; where hard links are not
  possible, it is copied to `.<name>.moving-part`, checked, and renamed only if the name
  is still free.
- Links inside an old folder are never followed or moved; they and anything that could
  not be moved stay in the old folder and are reported.

Running it again on a finished or a cut-off move finishes it and changes nothing else.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import logging
import os
import re
import stat
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from sci2audio.app.config import default_legacy_root, default_projects_root, file_id
from sci2audio.app.job import JobBusyError, JobError
from sci2audio.app.lock import LOCK_NAME, file_lock, work_folder_lock

logger = logging.getLogger(__name__)

PROJECT_ID = re.compile(r"\A[0-9a-f]{16}\Z")
MIGRATE_LOCK = ".migrate.lock"  # in the projects root: one process moves at a time
MOVING = ".moving-"  # `projects/.moving-<id>/`: a copy being made across file systems
EARLIER = "from-earlier-version"  # an old file that differs from the new folder's
PART = ".moving-part"  # `.<name>.moving-part`: a file being copied in, renamed when checked
INCOMING = ".incoming"  # the server's upload folder (web.documents)
STALE_UPLOAD = 3600  # seconds; as web.documents.STALE_UPLOAD
LOCK_WAIT = 10.0  # seconds to wait for another process's move
_BLOCK = 1 << 20


class Moved(StrEnum):
    """What happened to one old working folder."""

    MOVED = "moved"  # renamed into the projects root
    COPIED = "copied"  # copied across file systems, checked, originals removed
    MERGED = "merged"  # file by file into a project folder that existed already
    SKIPPED = "skipped"  # left where it is (busy, a link, an error); tried again next time
    ABSENT = "absent"  # there is no old folder


@dataclass(frozen=True)
class Outcome:
    id: str
    moved: Moved
    reason: str = ""
    left: tuple[Path, ...] = ()  # what stayed in the old folder: links, files not moved


def project_folder(root: Path, legacy: Path | None, project: str) -> Path:
    """The project's data folder: the new one, unless only an old folder not moved yet
    exists (a link there is never taken as a folder)."""
    new = root / project
    if legacy is not None and not _lexists(new) and _real_folder(legacy / project):
        return legacy / project
    return new


def project_work_folder(source: Path) -> Path:
    """The default working folder of a command-line job (D-164, D-216, D-747): its old
    folder is moved over first, and used where it is if it can't be. OSError if the file
    can't be read."""
    project = file_id(source)
    root, legacy = default_projects_root(), default_legacy_root()
    outcome = migrate_one(legacy, root, project)
    if outcome.moved is Moved.SKIPPED:
        logger.warning("the old working folder %s stays where it is: %s", project, outcome.reason)
    return project_folder(root, legacy, project)


def migrate_one(legacy: Path, root: Path, project: str, *, wait: float = LOCK_WAIT) -> Outcome:
    """Move one old working folder (see the module docstring); never raises OSError."""
    if not PROJECT_ID.match(project):
        raise ValueError(f"not a project id: {project!r}")
    if not _lexists(legacy / project):
        return Outcome(project, Moved.ABSENT)
    try:
        with file_lock(root / MIGRATE_LOCK, wait=wait) as held:
            if not held:
                return Outcome(project, Moved.SKIPPED, "another sci2audio is moving folders")
            return _migrate(legacy, root, project)
    except OSError as error:
        return Outcome(project, Moved.SKIPPED, _why(error))


def migrate_all(legacy: Path, root: Path, *, wait: float = LOCK_WAIT) -> list[Outcome]:
    """Move every old working folder; then remove stale uploads of the old upload folder
    and the old root, each only if it is empty then. Never raises OSError."""
    if not _real_folder(legacy):
        return []
    try:
        with file_lock(root / MIGRATE_LOCK, wait=wait) as held:
            if not held:
                return []  # another process moves them; they are used where they are
            outcomes = [
                _migrate(legacy, root, entry.name)
                for entry in _scan(legacy)
                if PROJECT_ID.match(entry.name)
            ]
            _clear_incoming(legacy / INCOMING)
            with contextlib.suppress(OSError):
                legacy.rmdir()  # only when empty
            return outcomes
    except OSError as error:
        logger.warning("could not move the old working folders: %s", _why(error))
        return []


# ---- one folder -----------------------------------------------------------------------


def _migrate(legacy: Path, root: Path, project: str) -> Outcome:
    old = legacy / project
    if not _lexists(old):
        return Outcome(project, Moved.ABSENT)
    if not _real_folder(old):
        return Outcome(project, Moved.SKIPPED, "a link or not a folder", (old,))
    try:
        with work_folder_lock(old):
            pass  # only asked: is a job working in it? (D-161)
    except JobBusyError:
        return Outcome(project, Moved.SKIPPED, "a job is working on it")
    except JobError as error:
        return Outcome(project, Moved.SKIPPED, str(error))
    target = root / project
    try:
        if not _lexists(target):
            return _move(old, target, root, project)
        if not _real_folder(target):
            return Outcome(project, Moved.SKIPPED, f"{target} is not a folder", (old,))
        left: list[Path] = []
        _merge_folder(old, target, Path(), left)
        _prune(old)
        return Outcome(project, Moved.MERGED, left=tuple(left))
    except OSError as error:
        return Outcome(project, Moved.SKIPPED, _why(error))


def _move(old: Path, target: Path, root: Path, project: str) -> Outcome:
    root.mkdir(parents=True, exist_ok=True)
    try:
        _rename(old, target)
        return Outcome(project, Moved.MOVED)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
    staging = root / f"{MOVING}{project}"
    _discard(staging)  # a copy a cut-off move left: only ever made here
    left: list[Path] = []
    try:
        _copy_folder(old, staging, left)
    except OSError:
        with contextlib.suppress(OSError):
            _discard(staging)
        raise
    _rename(staging, target)  # the commit: until here the old folder is untouched
    _remove_copied(old, target, Path())
    _prune(old)
    return Outcome(project, Moved.COPIED, left=tuple(left))


# ---- copying across file systems --------------------------------------------------------


def _copy_folder(source: Path, target: Path, left: list[Path]) -> None:
    target.mkdir()
    for entry in _scan(source):
        path = Path(entry.path)
        kind = _kind(path)
        if kind == "folder":
            _copy_folder(path, target / entry.name, left)
        elif kind == "file":
            _copy_checked(path, target / entry.name)
        else:
            left.append(path)  # a link or something else: never followed or copied


def _copy_checked(source: Path, target: Path) -> None:
    """Copy into a new file (never over one), synced to disk, then read back: OSError
    unless the copy has the original's size and SHA-256."""
    digest = hashlib.sha256()
    with source.open("rb") as original, _create(target) as copy:
        for block in iter(lambda: original.read(_BLOCK), b""):
            digest.update(block)
            copy.write(block)
        copy.flush()
        os.fsync(copy.fileno())
    if _digest(target) != (source.stat().st_size, digest.hexdigest()):
        raise OSError(errno.EIO, f"the copy of {source} differs from it")


def _remove_copied(old: Path, new: Path, relative: Path) -> None:
    """Remove each old file whose copy is in the new folder, checked once more."""
    for entry in _scan(old / relative):
        path = Path(entry.path)
        kind = _kind(path)
        if kind == "folder":
            _remove_copied(old, new, relative / entry.name)
        elif kind == "file" and _same(path, new / relative / entry.name):
            _unlink(path)


# ---- merging into a folder that exists ------------------------------------------------


def _merge_folder(old: Path, target: Path, relative: Path, left: list[Path]) -> None:
    for entry in _scan(old / relative):
        path = Path(entry.path)
        kind = _kind(path)
        if kind == "folder":
            _merge_folder(old, target, relative / entry.name, left)
        elif kind != "file":
            left.append(path)
        elif relative == Path() and entry.name == LOCK_NAME:
            continue  # the old lock: it holds nothing and goes with its folder
        else:
            try:
                _merge_file(path, target / relative / entry.name, target / EARLIER / relative)
            except OSError as error:
                logger.warning("could not move %s: %s", path, _why(error))
                left.append(path)


def _merge_file(path: Path, new: Path, earlier: Path) -> None:
    """Put the old file `path` at `new`; if a different file is there, into `earlier`
    under its own name, then `<stem> (2)<suffix>` and so on. The same file is removed."""
    candidates = [new, earlier / path.name]
    number = 2
    while True:
        if not candidates:
            candidates.append(earlier / f"{Path(path.name).stem} ({number}){path.suffix}")
            number += 1
        place = candidates.pop(0)
        if not _lexists(place):
            _place(path, place)
            return
        if _same(path, place):
            _unlink(path)
            return


def _place(path: Path, target: Path) -> None:
    """Give `path` the new name `target` and remove the old name; never over a file. A hard
    link refuses an existing name; where hard links are not possible, an exclusive create
    and a checked copy."""
    _make_folders(target.parent)
    try:
        _link(path, target)
    except FileExistsError:
        raise
    except OSError:  # another file system, or one without hard links
        part = target.with_name(f".{target.name}{PART}")
        with contextlib.suppress(FileNotFoundError):
            _unlink(part)  # this very copy, left by a move that was cut off
        _copy_checked(path, part)
        if _lexists(target):
            _unlink(part)
            raise FileExistsError(errno.EEXIST, f"{target} appeared during the move") from None
        _rename(part, target)
    _unlink(path)


def _make_folders(folder: Path) -> None:
    """Make `folder` and its missing parents; OSError if a part is a link or a file."""
    missing: list[Path] = []
    current = folder
    while not _lexists(current):
        missing.append(current)
        current = current.parent
    if not _real_folder(current):
        raise OSError(errno.ENOTDIR, f"{current} is not a folder")
    for part in reversed(missing):
        part.mkdir()


# ---- removing what was moved ------------------------------------------------------------


def _prune(old: Path) -> None:
    """Remove the old folder's empty folders and its lock file, and the folder if it is
    then empty; anything else stays."""
    for entry in _scan(old):
        path = Path(entry.path)
        if _kind(path) == "folder":
            _prune(path)
    lock = old / LOCK_NAME
    if _kind(lock) == "file" and lock.stat().st_size == 0:
        with contextlib.suppress(OSError):
            _unlink(lock)
    with contextlib.suppress(OSError):
        old.rmdir()


def _discard(path: Path) -> None:
    """Remove a staging copy: links are removed, never followed."""
    kind = _kind(path)
    if kind is None:
        return
    if kind == "folder":
        for entry in _scan(path):
            _discard(Path(entry.path))
        path.rmdir()
    else:
        _unlink(path)


def _clear_incoming(incoming: Path) -> None:
    """Uploads a killed server left in the old upload folder (`.part`, not written to for
    an hour), then the folder if it is empty."""
    if not _real_folder(incoming):
        return
    now = time.time()
    for entry in _scan(incoming):
        path = Path(entry.path)
        with contextlib.suppress(OSError):
            if (
                path.suffix == ".part"
                and _kind(path) == "file"
                and now - path.stat().st_mtime >= STALE_UPLOAD
            ):
                _unlink(path)
    with contextlib.suppress(OSError):
        incoming.rmdir()


# ---- small helpers; the file operations are names of their own so tests can cut them off


def _rename(source: Path, target: Path) -> None:
    os.rename(source, target)


def _link(source: Path, target: Path) -> None:
    os.link(source, target)  # `source` is a regular file, checked by the caller


def _unlink(path: Path) -> None:
    os.unlink(path)


def _create(path: Path) -> BinaryIO:
    return path.open("xb")


def _scan(folder: Path) -> list[os.DirEntry[str]]:
    with os.scandir(folder) as found:
        return sorted(found, key=lambda entry: entry.name)


def _lexists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True  # there, but can't be looked at: never taken as free
    return True


def _kind(path: Path) -> str | None:
    """ "folder", "file", "other" (a link, a junction, a device…) or None if absent."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode) or _is_junction(path):
        return "other"
    if stat.S_ISDIR(mode):
        return "folder"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def _is_junction(path: Path) -> bool:
    try:
        return path.is_junction()
    except OSError:
        return False


def _real_folder(path: Path) -> bool:
    try:
        return _kind(path) == "folder"
    except OSError:
        return False


def _digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as file:
        for block in iter(lambda: file.read(_BLOCK), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _same(one: Path, other: Path) -> bool:
    """Both regular files (no links) with the same size and SHA-256 (never time and size
    alone: they collide on Windows)."""
    try:
        if _kind(one) != "file" or _kind(other) != "file":
            return False
        if one.stat().st_size != other.stat().st_size:
            return False
        return _digest(one) == _digest(other)
    except OSError:
        return False


def _why(error: OSError) -> str:
    return str(error.strerror or error)
