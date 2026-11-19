"""Old working folders and tree digests for the move to the project folders (#469, D-748)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

# The files of one working folder before #469. v1.1: the job's records, the copied file,
# the analysis and the speech cache; v1.3 added the library's and the markers' records.
V1_1 = {
    "source/paper.pdf": b"%PDF-1.7 the paper",
    "script/paper.script.txt": b"The paper, as it is read.\n",
    "script/paper.report.json": b'{"format": "sci2audio-report"}\n',
    "chunks/ab/ab01.wav": b"RIFF one sentence",
    "chunks/cd/cd02.wav": b"RIFF another sentence",
    "job.json": b'{"format": "sci2audio-job"}\n',
    "audio.json": b'{"format": "sci2audio-audio"}\n',
    "document.json": b'{"format": "sci2audio-document"}\n',
    "audiobook.json": b'{"format": "sci2audio-web-audiobook"}\n',
    "position.json": b'{"format": "sci2audio-web-position", "seconds": 61.5}\n',
    "cover.jpg": b"\xff\xd8\xff a cover",
}
V1_3 = {
    **V1_1,
    "markers.json": b'{"format": "sci2audio-web-markers", "markers": [1, 2, 3]}\n',
    "opened.json": b'{"format": "sci2audio-web-opened"}\n',
    "about.json": b'{"format": "sci2audio-web-about"}\n',
}


def old_folder(legacy: Path, project: str, files: dict[str, bytes] | None = None) -> Path:
    """One working folder as a version before #469 left it, with its empty lock file."""
    folder = legacy / project
    for name, data in (V1_3 if files is None else files).items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data + project.encode())  # each project's files differ
    (folder / "job.lock").touch()
    return folder


def old_library(legacy: Path, count: int = 3, files: dict[str, bytes] | None = None) -> list[str]:
    """`count` old working folders; returns their ids."""
    ids = [f"{n:016x}" for n in range(0xA0, 0xA0 + count)]
    for project in ids:
        old_folder(legacy, project, files)
    return ids


def tree_digest(root: Path) -> dict[str, tuple[int, str]]:
    """Every regular file under `root` (links not followed): its path relative to `root`
    with "/" and its size and SHA-256. The lock file is left out: it holds nothing."""
    found: dict[str, tuple[int, str]] = {}
    if not root.exists():
        return found
    for folder, _folders, names in os.walk(root):
        for name in names:
            path = Path(folder) / name
            if path.is_symlink() or name == "job.lock":
                continue
            data = path.read_bytes()
            relative = path.relative_to(root).as_posix()
            found[relative] = (len(data), hashlib.sha256(data).hexdigest())
    return found


def can_link(folder: Path) -> bool:
    """True where this user may make symbolic links (Windows needs a privilege)."""
    probe = folder / "probe-link"
    try:
        os.symlink(folder, probe)
    except OSError:
        return False
    probe.unlink()
    return True
