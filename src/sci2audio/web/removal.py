"""Deleting a project's audiobook files when the project is removed (#470, D-751, D-754).

Only files `project.json` lists (D-750), in a project audiobook folder sci2audio made, are
ever deleted, and each only while its size and SHA-256 still match the record. Everything
else stays and is named with its reason:

- `changed`: its size or hash differ (the person edited or replaced it), or it is not a
  regular file any more;
- `not-recorded`: a file in a project folder that sci2audio did not write;
- `link`: a symbolic link or a Windows junction, never followed;
- `outside`: the recorded folder or the file's real place is not where the record says,
  or the folder is or holds a folder sci2audio never deletes in (home, Documents, the
  output folder itself, sci2audio's own folders, a drive's root);
- `shared`: another project's record lists the same file;
- `unreadable`: it can't be read to be checked (an iCloud file not downloaded, offline).

Audiobooks made before #469 sit flat in the output folder; no project folder holds them,
so they are never deleted (D-751). A project folder is removed with `rmdir` only, never
recursively, once nothing is left in it but system clutter (`.DS_Store`, `Thumbs.db`,
`desktop.ini`, small regular files), so a file the person put there keeps it.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import stat
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sci2audio.web.player import bare_name
from sci2audio.web.project import AudiobookFile, Project

CLUTTER = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
CLUTTER_LIMIT = 64 * 1024  # bytes: larger is not the system's note about a folder
KEPT_LIMIT = 50  # kept paths named in the answer; the rest are counted
_BLOCK = 1 << 20


class AudiobookRemoveError(Exception):
    """An audiobook file could not be deleted; `path` is the first one left."""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path = path


@dataclass(frozen=True)
class Kept:
    """A path that stayed and why; `folder` is the project folder it is in, or the path
    itself when a whole folder stayed (#569 round 1, R3)."""

    path: Path
    reason: str
    folder: Path

    @property
    def whole(self) -> bool:
        return self.path == self.folder


@dataclass(frozen=True)
class Planned:
    path: Path
    file: AudiobookFile
    folder_real: Path


@dataclass(frozen=True)
class PlannedFolder:
    """A project folder to remove once empty, with its real path when it was checked."""

    path: Path
    real: Path


@dataclass(frozen=True)
class AudiobookPlan:
    """What removing the project's audiobook files will do."""

    delete: tuple[Planned, ...] = ()
    folders: tuple[PlannedFolder, ...] = ()
    kept: tuple[Kept, ...] = ()


@dataclass(frozen=True)
class AudiobookRemoved:
    files: int = 0
    bytes: int = 0
    kept: tuple[Kept, ...] = ()


def plan(
    project: Project | None, protected: Sequence[Path], others: Iterable[Project]
) -> AudiobookPlan:
    """Check every recorded file now (R3, R4); nothing is deleted here."""
    if project is None:
        return AudiobookPlan()
    guarded = _reals(protected)
    claimed = {
        _real_or_none(audiobook.folder / f.name)
        for other in others
        for audiobook in other.audiobooks
        for f in audiobook.files
    } - {None}
    delete: list[Planned] = []
    folders: list[PlannedFolder] = []
    kept: list[Kept] = []
    for audiobook in project.audiobooks:
        folder = audiobook.folder
        reason = _folder_refused(folder, guarded)
        if reason == "absent":
            continue
        if reason is not None:
            kept.append(Kept(folder, reason, folder))
            continue
        real = folder.resolve(strict=True)
        listed = set()
        for file in audiobook.files:
            if not bare_name(file.name):
                kept.append(Kept(folder / str(file.name), "outside", folder))
                continue
            listed.add(file.name)
            path = folder / file.name
            why = _file_refused(path, real, file, claimed)
            if why == "absent":
                continue
            if why is None:
                delete.append(Planned(path, file, real))
            else:
                kept.append(Kept(path, why, folder))
        for entry in _entries(folder):
            if entry.name not in listed and not _clutter(entry):
                kept.append(Kept(entry, "not-recorded", folder))
        folders.append(PlannedFolder(folder, real))
    return AudiobookPlan(tuple(delete), tuple(folders), tuple(kept))


def carry_out(planned: AudiobookPlan) -> AudiobookRemoved:
    """Delete the planned files, then each project folder left empty (but for clutter).
    Each file, and each folder before its entries are listed, is looked at once more just
    before it goes: still a regular file or folder, no link, at the same real place
    (#569 round 1, R1). AudiobookRemoveError names the first file that could not go."""
    files = size = 0
    kept = list(planned.kept)
    for item in planned.delete:
        try:
            mode = item.path.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as error:
            raise AudiobookRemoveError(_message(item.path, error), item.path) from error
        if not stat.S_ISREG(mode) or _real_or_none(item.path.parent) != item.folder_real:
            kept.append(Kept(item.path, "changed", item.path.parent))
            continue
        _unlink(item.path)
        files += 1
        size += item.file.bytes
    for folder in planned.folders:
        why = _folder_moved(folder)
        if why == "absent":
            continue
        if why is not None:
            kept.append(Kept(folder.path, why, folder.path))
            continue
        _remove_if_empty(folder.path)
    return AudiobookRemoved(files, size, tuple(kept))


# ---- checks ---------------------------------------------------------------------------------


def _folder_refused(folder: Path, guarded: set[Path]) -> str | None:
    if not folder.is_absolute() or ".." in folder.parts or "\x00" in str(folder):
        return "outside"
    try:
        mode = folder.lstat().st_mode
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    if stat.S_ISLNK(mode) or _is_junction(folder):
        return "link"
    if not stat.S_ISDIR(mode):
        return "outside"
    try:
        real = folder.resolve(strict=True)
    except OSError:
        return "unreadable"
    if any(real == guard or real in guard.parents for guard in guarded):
        return "outside"  # it is, or holds, a folder sci2audio never deletes in
    return None


def _folder_moved(folder: PlannedFolder) -> str | None:
    """`changed` when the folder is no longer the one that was checked: a link or junction
    now, not a folder, or at another real place."""
    try:
        mode = folder.path.lstat().st_mode
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    if stat.S_ISLNK(mode) or _is_junction(folder.path) or not stat.S_ISDIR(mode):
        return "changed"
    if _real_or_none(folder.path) != folder.real:
        return "changed"
    return None


def _file_refused(
    path: Path, folder_real: Path, file: AudiobookFile, claimed: set[Path | None]
) -> str | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    if stat.S_ISLNK(mode) or _is_junction(path):
        return "link"
    if not stat.S_ISREG(mode):
        return "changed"
    real = _real_or_none(path)
    if real is None or real.parent != folder_real:
        return "outside"
    if real in claimed:
        return "shared"
    try:
        if path.stat().st_size != file.bytes or _sha256(path) != file.sha256:
            return "changed"
    except OSError:
        return "unreadable"
    return None


def _reals(paths: Iterable[Path]) -> set[Path]:
    found: set[Path] = set()
    for path in paths:
        found.add(Path(path.absolute().anchor))  # the drive or file-system root
        with contextlib.suppress(OSError, RuntimeError):
            found.add(path.resolve())
    return found


def _real_or_none(path: Path) -> Path | None:
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _is_junction(path: Path) -> bool:
    try:
        return path.is_junction()
    except OSError:
        return False


def _entries(folder: Path) -> list[Path]:
    try:
        with os.scandir(folder) as found:
            return sorted((Path(entry.path) for entry in found), key=lambda p: p.name)
    except OSError:
        return []


def _clutter(path: Path) -> bool:
    """A note the system leaves in folders it shows: a small regular file of a known name."""
    if path.name not in CLUTTER:
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_size <= CLUTTER_LIMIT


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


# ---- deleting ---------------------------------------------------------------------------------


def _unlink(path: Path) -> None:
    """Delete one file; a read-only one (Windows refuses those) is made writable once."""
    for attempt in (1, 2):
        try:
            os.unlink(path)
            return
        except FileNotFoundError:
            return
        except PermissionError as error:
            if attempt == 2:
                raise AudiobookRemoveError(_message(path, error), path) from error
            with contextlib.suppress(OSError):
                path.chmod(stat.S_IMODE(path.lstat().st_mode) | stat.S_IWUSR | stat.S_IRUSR)
        except OSError as error:
            raise AudiobookRemoveError(_message(path, error), path) from error


def _remove_if_empty(folder: Path) -> None:
    entries = _entries(folder)
    if not all(_clutter(entry) for entry in entries):
        return
    for entry in entries:
        with contextlib.suppress(OSError):
            os.unlink(entry)
    with contextlib.suppress(OSError):
        folder.rmdir()  # never recursive: a file that appeared meanwhile keeps the folder


def _message(path: Path, error: OSError) -> str:
    return f"could not delete {path}: {error.strerror or error}"
