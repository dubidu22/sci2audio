"""A project's audiobook folders and the record of every audiobook file sci2audio wrote
there (#469, D-749, D-750).

Each document's audiobook goes into a folder of its own inside the output folder,
`<output folder>/<project name>/` (`~/Documents/sci2audio/<project name>/` by default),
named after the opened file and kept for the project once made (D-749). The web keeps its
own record of these folders and files, `project.json` in the project data folder (D-750):

    {"format": "sci2audio-web-project", "version": 1, "document": "<id>",
     "name": "<project name>",
     "audiobooks": [{"folder": "<absolute path>",
                     "files": [{"name": "<bare name>", "bytes": 123, "sha256": "…"}]}]}

- A folder is only ever recorded when this code made it (`mkdir` without `exist_ok`): a
  folder that exists already, whatever its name or case, is never taken over; the next
  free name `<name> (2)`, `(3)`… is made instead. So every recorded folder is sci2audio's.
- A file is recorded with its size and SHA-256 after a finished audio job, replacing the
  entry of the same name; entries of earlier runs stay while their file is there.
- Whether a file is still the one sci2audio wrote is decided by size and SHA-256 only,
  never by its time (time and size collide on Windows).
- The record is read as strictly as the web's other records: missing, too large, a link,
  not ours, another version or document, or broken reads as no record, and such a file is
  never rewritten (as `markers.json`). Removing a project (#470) deletes only files listed
  here whose size and hash still match.

The audio job, the command line and the app never read or write this file.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from sci2audio.app.files import write_texts
from sci2audio.output.names import clean, cut

PROJECT = "project.json"
PROJECT_FORMAT = "sci2audio-web-project"
PROJECT_VERSION = 1
PROJECT_LIMIT = 256 * 1024  # bytes: a few hundred file entries
NAME_CHARS = 60  # a project folder's name: room for the files' names inside 260 (Windows)
NAME_BYTES = 80
MAX_TRIES = 1000  # `<name> (2)` to `<name> (1000)`
_BLOCK = 1 << 20


class ProjectError(Exception):
    """The project's audiobook folder can't be made; the message is for people."""


@dataclass(frozen=True)
class AudiobookFile:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class AudiobookFolder:
    folder: Path
    files: tuple[AudiobookFile, ...] = ()


@dataclass(frozen=True)
class Project:
    document: str
    name: str
    audiobooks: tuple[AudiobookFolder, ...] = ()

    def folders(self) -> list[Path]:
        """The recorded audiobook folders, the most recently made last."""
        return [audiobook.folder for audiobook in self.audiobooks]


def folder_name(document_name: str) -> str:
    """The project folder's name from the opened file's name: without its suffix, cleaned
    for every file system (forbidden, unassigned and surrogate code points, Windows names,
    #491, #493) and cut to NAME_CHARS characters and NAME_BYTES bytes."""
    stem = PurePosixPath(document_name).stem  # the same on every system: "a:" is no drive
    return clean(cut(clean(stem, "audiobook"), NAME_CHARS, NAME_BYTES), "audiobook")


def _numbered(name: str, number: int) -> str:
    if number == 1:
        return name
    suffix = f" ({number})"
    short = cut(name, NAME_CHARS - len(suffix), NAME_BYTES - len(suffix))
    return clean(short, "audiobook") + suffix


# ---- the record -------------------------------------------------------------------------


def read_project(work: Path, document_id: str) -> Project | None:
    """The project's record, or None if there is none this version can trust."""
    path = work / PROJECT
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > PROJECT_LIMIT:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    try:
        return _project(data, document_id)
    except (KeyError, TypeError, ValueError):
        return None


def _project(data: Any, document_id: str) -> Project:
    if (
        not isinstance(data, dict)
        or data.get("format") != PROJECT_FORMAT
        or type(data.get("version")) is not int
        or data["version"] != PROJECT_VERSION
        or data.get("document") != document_id
        or not isinstance(data.get("name"), str)
        or not isinstance(data.get("audiobooks"), list)
    ):
        raise ValueError("not a project record of this document")
    audiobooks = []
    for entry in data["audiobooks"]:
        folder = entry["folder"]
        if not isinstance(folder, str) or "\x00" in folder or not Path(folder).is_absolute():
            raise ValueError("an audiobook folder must be a full path")
        files = tuple(
            AudiobookFile(_text(f["name"]), _count(f["bytes"]), _sha(f["sha256"]))
            for f in entry["files"]
        )
        audiobooks.append(AudiobookFolder(Path(folder), files))
    return Project(document_id, data["name"], tuple(audiobooks))


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected a name")
    return value


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("expected a size")
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or set(value) - set("0123456789abcdef"):
        raise ValueError("expected a SHA-256")
    return value


def write_project(work: Path, project: Project) -> None:
    """Write the record, all of it or nothing (OSError if it can't be written)."""
    data = {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "document": project.document,
        "name": project.name,
        "audiobooks": [
            {
                "folder": str(audiobook.folder),
                "files": [
                    {"name": f.name, "bytes": f.bytes, "sha256": f.sha256} for f in audiobook.files
                ],
            }
            for audiobook in project.audiobooks
        ],
    }
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    write_texts({work / PROJECT: text}, overwrite=True)


# ---- the folder ---------------------------------------------------------------------------


def audiobook_folder(work: Path, document_id: str, document_name: str, output: Path) -> Path:
    """The project's audiobook folder in `output` (D-749): the one recorded for it there if
    it is still a real folder, else a new one made now and recorded before anything is
    written into it. ProjectError if it can't be made or recorded."""
    output = output.absolute()
    path = work / PROJECT
    project = read_project(work, document_id)
    if project is None:
        if os.path.lexists(path):  # a record this version can't read: never written over
            raise ProjectError(f"the project record {path} can't be read; move it away")
        project = Project(document_id, folder_name(document_name))
    for folder in reversed(project.folders()):
        if folder.parent == output and _real_folder(folder):
            return folder
    try:
        output.mkdir(parents=True, exist_ok=True)
        folder = _make_folder(output, project.name)
        made = (*project.audiobooks, AudiobookFolder(folder))
        write_project(work, replace(project, audiobooks=made))
    except OSError as error:
        raise ProjectError(
            f"could not make the audiobook folder in {output}: {error.strerror or error}"
        ) from error
    return folder


def _make_folder(output: Path, name: str) -> Path:
    for number in range(1, MAX_TRIES + 1):
        folder = output / _numbered(name, number)
        try:
            folder.mkdir()  # the OS decides "exists", in its own case and normalisation rules
        except FileExistsError:
            continue
        return folder
    raise FileExistsError(f"{output} has {MAX_TRIES} folders named {name}")


def _real_folder(folder: Path) -> bool:
    try:
        return folder.is_dir() and not folder.is_symlink() and not folder.is_junction()
    except OSError:
        return False


# ---- the files ----------------------------------------------------------------------------


def record_files(work: Path, document_id: str, folder: Path, written: list[Path]) -> None:
    """Record the files a finished audio job wrote into `folder` (each must be directly in
    it), with size and SHA-256; entries of files no longer there are dropped. Leaves a
    record this version can't read as it is. OSError if the record can't be written."""
    project = read_project(work, document_id)
    if project is None:
        return
    found = {path.name: _file(path) for path in written if path.parent == folder}
    audiobooks = []
    for audiobook in project.audiobooks:
        if audiobook.folder != folder:
            audiobooks.append(audiobook)
            continue
        kept = {
            f.name: f
            for f in audiobook.files
            if f.name not in found and os.path.lexists(folder / f.name)
        }
        files = sorted([*kept.values(), *found.values()], key=lambda f: f.name)
        audiobooks.append(AudiobookFolder(folder, tuple(files)))
    write_project(work, replace(project, audiobooks=tuple(audiobooks)))


def _file(path: Path) -> AudiobookFile:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as file:
        for block in iter(lambda: file.read(_BLOCK), b""):
            size += len(block)
            digest.update(block)
    return AudiobookFile(path.name, size, digest.hexdigest())
