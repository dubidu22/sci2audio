"""The one download of the voice files, started only by the user (D-47, VA-03, VA-04).

Everything Kokoro English needs to run offline comes from two places, each pinned by
revision and sha256: the model and its English voice packs from the official Hugging Face
repository, and the spaCy English model misaki uses from explosion's GitHub release (it is
not on PyPI). `download_plan()` lists every file with its size and licence for the consent
screen; `download_voice_files()` fetches what is missing. The CLI (#72) and the interface
(#76, #77) call these two and nothing else.

Writing is safe against interruption: each file is streamed to `<name>.part`, checked
against its sha256 and only then renamed into place, and the spaCy wheel is unpacked into
a temporary folder that is renamed when complete. Running the download again skips every
file that is already in place and correct, so an interrupted download resumes.

Layout of the models folder (the caller picks the folder; nothing here has a default):

    kokoro-82m/<revision>/config.json, kokoro-v1_0.pth, voices/<voice>.pt
    spacy/en_core_web_sm-3.8.0/   (put on sys.path; holds the package and its metadata)
"""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import requests

from sci2audio.voices.errors import EngineError, NetworkError

KOKORO_REPO = "hexgrad/Kokoro-82M"
KOKORO_REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
KOKORO_WEIGHTS = "kokoro-v1_0.pth"
SPACY_MODEL = "en_core_web_sm"
SPACY_MODEL_VERSION = "3.8.0"

_KOKORO_DIR = PurePosixPath("kokoro-82m") / KOKORO_REVISION
_SPACY_DIR = PurePosixPath("spacy") / f"{SPACY_MODEL}-{SPACY_MODEL_VERSION}"
_HF_BASE = f"https://huggingface.co/{KOKORO_REPO}/resolve/{KOKORO_REVISION}"
_SPACY_WHEEL = f"{SPACY_MODEL}-{SPACY_MODEL_VERSION}-py3-none-any.whl"
_SPACY_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    f"{SPACY_MODEL}-{SPACY_MODEL_VERSION}/{_SPACY_WHEEL}"
)

KOKORO_LICENCE = (
    "Kokoro-82M model and voices by hexgrad: Apache License 2.0. The model card states it "
    "was trained only on permissive or non-copyrighted audio. "
    f"https://huggingface.co/{KOKORO_REPO}"
)
SPACY_LICENCE = (
    "spaCy English model en_core_web_sm 3.8.0 by Explosion: MIT License. "
    "https://github.com/explosion/spacy-models"
)

# (voice id, size in bytes, sha256) of every English voice pack at KOKORO_REVISION.
_ENGLISH_VOICE_FILES: tuple[tuple[str, int, str], ...] = (
    ("af_alloy", 523_425, "6d877149dd8b348fbad12e5845b7e43d975390e9f3b68a811d1d86168bef5aa3"),
    ("af_aoede", 523_425, "c03bd1a4c3716c2d8eaa3d50022f62d5c31cfbd6e15933a00b17fefe13841cc4"),
    ("af_bella", 523_425, "8cb64e02fcc8de0327a8e13817e49c76c945ecf0052ceac97d3081480e8e48d6"),
    ("af_heart", 523_425, "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff"),
    ("af_jessica", 523_435, "cdfdccb8cc975aa34ee6b89642963b0064237675de0e41a30ae64cc958dd4e87"),
    ("af_kore", 523_420, "8bfbc512321c3db49dff984ac675fa5ac7eaed5a96cc31104d3a9080e179d69d"),
    ("af_nicole", 523_430, "c5561808bcf5250fe8c5f5de32caf2d94f27e57e95befdb098c5c85991d4c5da"),
    ("af_nova", 523_420, "e0233676ddc21908c37a1f102f6b88a59e4e5c1bd764983616eb9eda629dbcd2"),
    ("af_river", 523_425, "e149459bd9c084416b74756b9bd3418256a8b839088abb07d463730c369dab8f"),
    ("af_sarah", 523_425, "49bd364ea3be9eb3e9685e8f9a15448c4883112a7c0ff7ab139fa4088b08cef9"),
    ("af_sky", 523_351, "c799548aed06e0cb0d655a85a01b48e7f10484d71663f9a3045a5b9362e8512c"),
    ("am_adam", 523_420, "ced7e284aba12472891be1da3ab34db84cc05cc02b5889535796dbf2d8b0cb34"),
    ("am_echo", 523_420, "8bcfdc852bc985fb45c396c561e571ffb9183930071f962f1b50df5c97b161e8"),
    ("am_eric", 523_420, "ada66f0eefff34ec921b1d7474d7ac8bec00cd863c170f1c534916e9b8212aae"),
    ("am_fenrir", 523_430, "98e507eca1db08230ae3b6232d59c10aec9630022d19accac4f5d12fcec3c37a"),
    ("am_liam", 523_420, "c82550757ddb31308b97f30040dda8c2d609a9e2de6135848d0a948368138518"),
    ("am_michael", 523_435, "9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37"),
    ("am_onyx", 523_420, "e8452be16cd0f6da7b4579eaf7b1e4506e92524882053d86d72b96b9a7fed584"),
    ("am_puck", 523_420, "dd1d8973f4ce4b7d8ae407c77a435f485dabc052081b80ea75c4f30b84f36223"),
    ("am_santa", 523_425, "7f2f7582fa2b1f160e90aafe6d0b442a685e773608b6667e545d743b073e97a7"),
    ("bf_alice", 523_425, "d292651b6af6c0d81705c2580dcb4463fccc0ff7b8d618a471dbb4e45655b3f3"),
    ("bf_emma", 523_420, "d0a423deabf4a52b4f49318c51742c54e21bb89bbbe9a12141e7758ddb5da701"),
    ("bf_isabella", 523_440, "cdd4c37003805104d1d08fb1e05855c8fb2c68de24ca6e71f264a30aaa59eefd"),
    ("bf_lily", 523_420, "6e09c2e481e2d53004d7e5ae7d3a325369e130a6f45c35a6002de75084be9285"),
    ("bm_daniel", 523_430, "fc3fce4e9c12ed4dbc8fa9680cfe51ee190a96444ce7c3ad647549a30823fc5d"),
    ("bm_fable", 523_425, "d44935f3135257a9064df99f007fc1342ff1aa767552b4a4fa4c3b2e6e59079c"),
    ("bm_george", 523_430, "f1bc812213dc59774769e5c80004b13eeb79bd78130b11b2d7f934542dab811b"),
    ("bm_lewis", 523_425, "b5204750dcba01029d2ac9cec17aec3b20a6d64073c579d694a23cb40effbd0e"),
)

_CHUNK = 1024 * 1024
_TIMEOUT = (15, 60)  # seconds: connect, and between two received chunks


@dataclass(frozen=True)
class RemoteFile:
    """One file of the voice download.

    `target` is the path inside the models folder, with forward slashes. A file with
    `unpack` set is a wheel: it is unpacked into `target` (a folder) and not kept.
    """

    url: str
    target: str
    size: int
    sha256: str
    licence: str
    unpack: bool = False


@dataclass(frozen=True)
class DownloadPlan:
    """What the voice download fetches, for the consent screen (VA-03)."""

    files: tuple[RemoteFile, ...]
    total_bytes: int
    licences: tuple[str, ...]


# Progress: bytes done, bytes in total, target of the file being fetched.
Progress = Callable[[int, int, str], None]
# Fetch: stream the body of `url` into `out`, calling `on_bytes(n)` for every n bytes.
# Raises NetworkError when the network fails. Replaceable in tests (no network in tests).
Fetch = Callable[[str, BinaryIO, Callable[[int], None]], None]


class DownloadError(EngineError):
    """The voice download could not finish (disk full, wrong checksum, folder removed)."""


def _kokoro_files() -> list[RemoteFile]:
    files = [
        RemoteFile(
            url=f"{_HF_BASE}/config.json",
            target=str(_KOKORO_DIR / "config.json"),
            size=2_351,
            sha256="5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
            licence=KOKORO_LICENCE,
        ),
        RemoteFile(
            url=f"{_HF_BASE}/{KOKORO_WEIGHTS}",
            target=str(_KOKORO_DIR / KOKORO_WEIGHTS),
            size=327_212_226,
            sha256="496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4",
            licence=KOKORO_LICENCE,
        ),
    ]
    files += [
        RemoteFile(
            url=f"{_HF_BASE}/voices/{voice}.pt",
            target=str(_KOKORO_DIR / "voices" / f"{voice}.pt"),
            size=size,
            sha256=sha256,
            licence=KOKORO_LICENCE,
        )
        for voice, size, sha256 in _ENGLISH_VOICE_FILES
    ]
    return files


def download_plan() -> DownloadPlan:
    """Every file the voice download fetches, with sizes and licences, before consent."""
    files = (
        *_kokoro_files(),
        RemoteFile(
            url=_SPACY_URL,
            target=str(_SPACY_DIR),
            size=12_806_118,
            sha256="1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85",
            licence=SPACY_LICENCE,
            unpack=True,
        ),
    )
    return DownloadPlan(
        files=files,
        total_bytes=sum(f.size for f in files),
        licences=(KOKORO_LICENCE, SPACY_LICENCE),
    )


def kokoro_dir(models_dir: Path) -> Path:
    """Folder with the Kokoro config, weights and `voices/`."""
    return models_dir / _KOKORO_DIR


def spacy_dir(models_dir: Path) -> Path:
    """Folder that goes on `sys.path` so spaCy finds the English model."""
    return models_dir / _SPACY_DIR


def _in_place(models_dir: Path, file: RemoteFile) -> bool:
    """Cheap check that a file is present: right size, or an unpacked wheel with metadata."""
    path = models_dir / file.target
    if file.unpack:
        record = path / f"{SPACY_MODEL}-{SPACY_MODEL_VERSION}.dist-info" / "RECORD"
        return record.is_file()
    return path.is_file() and path.stat().st_size == file.size


def missing_files(models_dir: Path) -> list[RemoteFile]:
    """Files of the voice download that are not in `models_dir` (size check, no hashing)."""
    return [f for f in download_plan().files if not _in_place(models_dir, f)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(_CHUNK):
            digest.update(block)
    return digest.hexdigest()


def _fetch_with_requests(url: str, out: BinaryIO, on_bytes: Callable[[int], None]) -> None:
    try:
        with requests.get(url, stream=True, timeout=_TIMEOUT) as response:
            response.raise_for_status()
            for block in response.iter_content(chunk_size=_CHUNK):
                out.write(block)
                on_bytes(len(block))
    except requests.RequestException as error:
        raise NetworkError(f"could not download {url}: {error}") from error


def _disk_error(error: OSError, models_dir: Path, plan: Iterable[RemoteFile]) -> DownloadError:
    if error.errno == errno.ENOSPC:
        need = sum(f.size for f in plan) // 1_000_000
        return DownloadError(
            f"not enough disk space in {models_dir} for the voice files "
            f"(about {need} MB are needed); free some space and start the download again"
        )
    if error.errno == errno.ENOENT:
        return DownloadError(
            f"the folder {models_dir} disappeared during the voice download; "
            "start the download again"
        )
    return DownloadError(f"could not write the voice files to {models_dir}: {error}")


def _unpack_wheel(wheel: Path, target: Path) -> None:
    """Unpack the wheel into a temporary folder beside `target`, then rename it."""
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or "\\" in name:
                raise DownloadError(f"unsafe path {name!r} in {wheel.name}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
        try:
            archive.extractall(temporary)
            if target.exists():
                shutil.rmtree(target)
            temporary.rename(target)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise


def _download_one(
    models_dir: Path, file: RemoteFile, fetch: Fetch, on_bytes: Callable[[int], None]
) -> None:
    target = models_dir / file.target
    if file.unpack:
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.parent / f"{_SPACY_WHEEL}.part"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
    try:
        with part.open("wb") as out:
            fetch(file.url, out, on_bytes)
        actual = _sha256(part)
        if actual != file.sha256:
            raise DownloadError(
                f"{file.url} does not match its expected checksum "
                f"(sha256 {actual}, expected {file.sha256}); nothing was kept"
            )
        if file.unpack:
            _unpack_wheel(part, target)
        else:
            os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)


def download_voice_files(
    models_dir: Path, *, progress: Progress | None = None, fetch: Fetch | None = None
) -> None:
    """Fetch every missing voice file into `models_dir`. Only call this on user action.

    Files already in place are checked (sha256 for files, metadata for the unpacked
    wheel) and skipped; a file in place but wrong is fetched again.

    Raises:
        NetworkError: The network failed; files finished so far are kept.
        DownloadError: Disk full, wrong checksum, or the folder was removed mid-run.
    """
    fetch = fetch or _fetch_with_requests
    plan = download_plan()
    todo = [
        f
        for f in plan.files
        if not (
            _in_place(models_dir, f) and (f.unpack or _sha256(models_dir / f.target) == f.sha256)
        )
    ]
    total = sum(f.size for f in todo)
    done = 0

    for file in todo:

        def on_bytes(n: int, target: str = file.target) -> None:
            nonlocal done
            done += n
            if progress is not None:
                progress(done, total, target)

        try:
            _download_one(models_dir, file, fetch, on_bytes)
        except OSError as error:
            raise _disk_error(error, models_dir, todo) from error
