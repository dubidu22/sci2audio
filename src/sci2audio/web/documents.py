"""Opened documents: copied into their own working folder (D-198).

A browser sends a file's bytes, never its path, so an opened file is copied to

    <work_root>/<id>/source/<name as opened>

where `<id>` is the first 16 hex digits of the file's SHA-256: the working folder the
audio job uses by default (D-164). Opening the same bytes again, even after a restart and
under another name, finds the same folder, so its pre-analysis and speech chunks are used
again. The name as opened is kept (cleaned only of characters no file system allows); a
new name replaces the old one.

Writing is safe against interruption and a full disk: the bytes stream to a `.part` file
in `<work_root>/.incoming/` while being counted and hashed, and are renamed into place
only when complete and within the size limit. A server killed mid-upload leaves its
`.part` file behind; the next server removes those not written to for an hour.

Removing a document (#120, D-353 to D-356) deletes its whole working folder and nothing
outside it, under the working folder's lock: first everything but the source, then the
source, so a removal that fails part-way leaves the document listed for another try.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import re
import secrets
import shutil
import stat
import sys
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import BinaryIO

from sci2audio.app import EXTRACTORS, JobBusyError, JobError, JobSettings, ScriptFiles, script_files
from sci2audio.app.chunks import CHUNKS
from sci2audio.app.lock import LOCK_NAME, work_folder_lock
from sci2audio.output.names import clean

ID = re.compile(r"\A[0-9a-f]{16}\Z")
INCOMING = ".incoming"
STALE_UPLOAD = 3600  # seconds since a `.part` file was last written to
SOURCE = "source"
SCRIPT = "script"  # the pre-analysis files of the server's script jobs (D-199)
AUDIO_RECORD = "audio.json"  # written by the audio job (D-165)
_BLOCK = 1024 * 1024


class StoreError(Exception):
    """The document could not be stored; `kind` names the reason for the API."""

    kind = "store-failed"


class UnsupportedFileError(StoreError):
    kind = "unsupported-file"


class TooLargeError(StoreError):
    kind = "too-large"


class DiskFullError(StoreError):
    kind = "disk-full"


class DocumentBusyError(Exception):
    """A job works on the document, in this server or in another process (D-356)."""


class RemoveError(Exception):
    """Part of the working folder could not be removed (D-355); `path` is the first left."""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path = path


@dataclass(frozen=True)
class Removed:
    """What a removal took away."""

    id: str
    name: str
    freed_bytes: int


@dataclass(frozen=True)
class StoredDocument:
    """One opened document and its working folder."""

    id: str
    folder: Path
    source: Path

    @property
    def name(self) -> str:
        return self.source.name

    @property
    def script_folder(self) -> Path:
        return self.folder / SCRIPT

    @property
    def report_file(self) -> Path:
        """The latest pre-analysis report (`sci2audio-report` v1), if one was written."""
        return self._script_files().report_json

    def analysis_files(self) -> list[Path]:
        """The latest pre-analysis' files that exist: script, report JSON, report Markdown
        (D-255), in that order."""
        return [path for path in self._script_files().outputs if path.is_file()]

    def _script_files(self) -> ScriptFiles:
        settings = JobSettings(output_folder=self.script_folder)
        return script_files(self.source, settings, self.folder)

    @property
    def speech_cache_bytes(self) -> int:
        """Bytes of kept speech chunks (D-158); 0 when there are none."""
        total = 0
        for path in (self.folder / CHUNKS).rglob("*"):
            with contextlib.suppress(OSError):
                if path.is_file():
                    total += path.stat().st_size
        return total

    @property
    def size(self) -> int:
        """Bytes of the opened file; 0 when it can't be read."""
        try:
            return self.source.stat().st_size
        except OSError:
            return 0

    @property
    def has_audio(self) -> bool:
        return (self.folder / AUDIO_RECORD).is_file()

    @property
    def folder_bytes(self) -> int:
        """Bytes of everything in the working folder: what removing it frees."""
        return _tree_size(self.folder)


def supported_suffixes() -> list[str]:
    return sorted(EXTRACTORS)


def stored_name(name: str) -> str:
    """The file name an opened file is kept under: the last part of what the browser sent
    (some send a whole Windows path), cleaned for every file system, suffix kept in lower
    case. Raises UnsupportedFileError for a type sci2audio can't read."""
    last = name.replace("\\", "/").rsplit("/", 1)[-1]
    path = PurePath(last)
    suffix = path.suffix.lower()
    if suffix not in EXTRACTORS:
        known = ", ".join(supported_suffixes())
        shown = last or "the file"
        raise UnsupportedFileError(f"{shown}: sci2audio can read {known} files only")
    return f"{clean(path.stem, 'document')}{suffix}"


class DocumentStore:
    """The documents under one work root."""

    def __init__(self, work_root: Path, *, upload_limit: int, text_limit: int) -> None:
        self.root = work_root
        self.upload_limit = upload_limit
        self.text_limit = text_limit
        # the ids being removed: gone for `get`, and a new copy of one waits (D-356)
        self._removing: set[str] = set()
        self._changes = threading.Condition()

    def clear_stale_uploads(self, older_than: float = STALE_UPLOAD) -> list[Path]:
        """Remove `.part` files of uploads a killed server left behind: those not written
        to for `older_than` seconds (a second server on the same folders may be writing a
        fresh one). Returns what was removed; a file that can't be removed is left."""
        removed: list[Path] = []
        now = time.time()
        for part in sorted((self.root / INCOMING).glob("*.part")):
            with contextlib.suppress(OSError):
                if now - part.stat().st_mtime >= older_than:
                    part.unlink()
                    removed.append(part)
        return removed

    def get(self, document_id: str) -> StoredDocument | None:
        if not ID.match(document_id) or document_id in self._removing:
            return None
        folder = self.root / document_id
        source = _newest(folder / SOURCE)
        if source is None:
            return None
        return StoredDocument(document_id, folder, source)

    def all(self) -> list[StoredDocument]:
        """Every document with a source file, most recently opened first."""
        if not self.root.is_dir():
            return []
        found = [
            document
            for folder in self.root.iterdir()
            if ID.match(folder.name) and (document := self.get(folder.name)) is not None
        ]
        return sorted(found, key=lambda d: _mtime(d.source), reverse=True)

    def store(self, name: str, data: BinaryIO, *, in_use: str | None = None) -> StoredDocument:
        """Copy an opened file in (see the module docstring). The type is checked before
        any byte is copied. `in_use` names a document a job is working on: its old source
        file is kept, so the job never loses its file."""
        kept = stored_name(name)
        return self._store(kept, _blocks(data), self.upload_limit, in_use)

    def store_text(self, text: str, name: str, *, in_use: str | None = None) -> StoredDocument:
        """Keep pasted text as `<name>.txt` (UTF-8). Readable once text files are (#74)."""
        stem = clean(name, "pasted text")
        kept = stored_name(f"{stem}.txt")
        data = text.encode("utf-8")
        return self._store(kept, [data], self.text_limit, in_use)

    def _store(
        self, name: str, blocks: Iterable[bytes], limit: int, in_use: str | None
    ) -> StoredDocument:
        incoming = self.root / INCOMING
        part = incoming / f"{secrets.token_hex(8)}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            incoming.mkdir(parents=True, exist_ok=True)
            with part.open("wb") as out:
                for block in blocks:
                    size += len(block)
                    if size > limit:
                        raise TooLargeError(
                            f"{name} is larger than {limit // (1024 * 1024)} MB; "
                            "sci2audio opens files up to that size"
                        )
                    digest.update(block)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
            document_id = digest.hexdigest()[:16]
            with self._changes:
                # the same bytes while they are being removed: wait, then a fresh folder
                self._changes.wait_for(lambda: document_id not in self._removing)
                return self._place(part, name, document_id, in_use)
        except OSError as error:
            raise _store_error(error, name) from error
        finally:
            with contextlib.suppress(OSError):
                part.unlink(missing_ok=True)

    def _place(self, part: Path, name: str, document_id: str, in_use: str | None) -> StoredDocument:
        folder = self.root / document_id
        source_folder = folder / SOURCE
        source_folder.mkdir(parents=True, exist_ok=True)
        target = source_folder / name
        os.replace(part, target)
        if document_id == in_use:
            return StoredDocument(document_id, folder, target)
        for other in source_folder.iterdir():  # a new name replaces the old one
            if other != target:
                with contextlib.suppress(OSError):
                    other.unlink()
        return StoredDocument(document_id, folder, target)

    def remove(self, document_id: str, *, busy: Callable[[], str | None]) -> Removed | None:
        """Remove the document's whole working folder (D-353, D-355); None if there is no
        such document. `busy` names a job of this server that works on it, if any; it is
        asked once the id is already gone for `get`, so no job of this server can start
        on it afterwards. DocumentBusyError when a job works on it here or in another
        process (its lock), RemoveError when part of the folder could not be removed."""
        with self._changes:
            document = self.get(document_id)
            if document is None:
                return None
            self._removing.add(document_id)
        try:
            reason = busy()
            if reason is not None:
                raise DocumentBusyError(reason)
            folder = document.folder
            if folder.is_symlink():  # never followed out of the work root
                raise RemoveError(f"{folder} is a link, not a working folder", folder)
            freed = _tree_size(folder)
            try:
                with work_folder_lock(folder):
                    _remove_folder(folder)
            except JobBusyError as error:
                raise DocumentBusyError(str(error)) from error
            except JobError as error:  # the lock file could not be opened
                raise RemoveError(str(error), folder / LOCK_NAME) from error
            # Windows can't remove the lock file while it is open; it is closed now. If
            # this fails, an empty lock file in an empty folder stays: never listed.
            with contextlib.suppress(OSError):
                (folder / LOCK_NAME).unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                folder.rmdir()
            return Removed(document_id, document.name, freed)
        finally:
            with self._changes:
                self._removing.discard(document_id)
                self._changes.notify_all()


def _remove_folder(folder: Path) -> None:
    """Everything but the source and the lock, then the source (D-355); on POSIX also the
    lock file, while it is still held (another process that opens it then makes its own)."""
    entries = sorted(folder.iterdir(), key=lambda path: path.name)
    for entry in entries:
        if entry.name not in (SOURCE, LOCK_NAME):
            _remove_entry(entry)
    _remove_entry(folder / SOURCE)
    if sys.platform != "win32":
        _remove_entry(folder / LOCK_NAME)


def _remove_entry(path: Path) -> None:
    """Remove a file, a link (never what it points to) or a folder tree. A file already
    gone counts as removed; a read-only one is made writable and tried once more."""
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, onexc=_retry_writable)
        else:
            _unlink(path)
    except OSError as error:
        left = Path(error.filename) if error.filename else path
        raise RemoveError(f"could not remove {left}: {error.strerror or error}", left) from error


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        _make_writable(path)
        path.unlink(missing_ok=True)


def _retry_writable(function: Callable[..., object], name: str, error: BaseException) -> None:
    """`shutil.rmtree`'s handler: a file gone already is fine; a read-only file or folder
    (Windows refuses to remove those) is made writable and tried once more."""
    if isinstance(error, FileNotFoundError):
        return
    if not isinstance(error, PermissionError):
        raise error
    path = Path(name)
    _make_writable(path)
    if function in (os.unlink, os.rmdir):
        with contextlib.suppress(FileNotFoundError):
            function(name)
    else:  # a folder that could not be opened or listed: once more, now that it can be
        shutil.rmtree(path, onexc=_gone_is_fine)


def _gone_is_fine(function: Callable[..., object], name: str, error: BaseException) -> None:
    if not isinstance(error, FileNotFoundError):
        raise error


def _make_writable(path: Path) -> None:
    for target in (path.parent, path):
        with contextlib.suppress(OSError):
            mode = target.lstat().st_mode
            if not stat.S_ISLNK(mode):
                target.chmod(stat.S_IMODE(mode) | stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)


def _tree_size(folder: Path) -> int:
    total = 0
    for root, _folders, names in os.walk(folder):
        for name in names:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(root, name)).st_size
    return total


def _blocks(data: BinaryIO) -> Iterable[bytes]:
    while block := data.read(_BLOCK):
        yield block


def _store_error(error: OSError, name: str) -> StoreError:
    if error.errno == errno.ENOSPC:
        return DiskFullError(f"not enough disk space to open {name}; free some space")
    return StoreError(f"could not keep {name}: {error.strerror or error}")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _newest(folder: Path) -> Path | None:
    try:
        files = [path for path in folder.iterdir() if path.is_file()]
    except OSError:
        return None
    return max(files, key=_mtime, default=None)
