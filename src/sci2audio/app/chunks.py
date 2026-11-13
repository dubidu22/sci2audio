"""The audio job's chunk cache in the working folder (WI-02, D-155, D-156, D-158).

Every chunk is the voice's audio of one utterance, cached under a key of what decides the
sound: the text, the voice, the speed and the engine version (the span is not part of it,
so the same text twice in a job is spoken once). A chunk is finished when its WAV file is
complete: the voice writes `<name>.part` and renames it (`voices.write_wav`), so a run
killed outright leaves at most a `.part` file, which the next run removes. Resuming is
running the job again on the same working folder: every finished chunk is used again.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import wave
from pathlib import Path

CHUNKS = "chunks"  # the cache's folder inside the working folder
KEY_FORMAT = 1  # bump when anything else starts to change the sound
_SAMPLE_WIDTH = 2  # 16-bit PCM (D-117)


def chunk_key(text: str, voice: str, speed: float, engine: str, engine_version: str) -> str:
    """The cache key of a chunk: SHA-256 (hex) of a canonical JSON of what decides its sound."""
    data = {
        "format": KEY_FORMAT,
        "engine": engine,
        "engine_version": engine_version,
        "voice": voice,
        "speed": float(speed),
        "text": text,
    }
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def chunk_file(key: str) -> str:
    """The chunk's file relative to the working folder (an `AudioChunk.file`)."""
    return f"{CHUNKS}/{key[:2]}/{key}.wav"


def is_finished(path: Path) -> bool:
    """True if `path` is a complete 16-bit mono PCM WAV file (a finished chunk)."""
    try:
        with wave.open(str(path), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != _SAMPLE_WIDTH:
                return False
            if audio.getframerate() <= 0:
                return False
            frames = audio.getnframes()
            if frames == 0:
                return True
            audio.setpos(frames - 1)  # a file cut short has fewer bytes than its header says
            return len(audio.readframes(1)) == _SAMPLE_WIDTH
    except (OSError, EOFError, wave.Error):
        return False


def remove_partials(work: Path) -> int:
    """Remove the `.part` files a killed run left in the cache; return how many."""
    removed = 0
    folder = work / CHUNKS
    if not folder.is_dir():
        return 0
    for part in folder.glob("*/*.part"):
        with contextlib.suppress(OSError):
            part.unlink()
            removed += 1
    return removed


def cache_size(work: Path) -> int:
    """The bytes the chunk cache takes (0 when there is none)."""
    folder = work / CHUNKS
    if not folder.is_dir():
        return 0
    total = 0
    for path in folder.rglob("*"):
        with contextlib.suppress(OSError):
            if path.is_file():
                total += path.stat().st_size
    return total


def clean_work_folder(work: Path) -> int:
    """Remove the chunk cache from a working folder; return the bytes freed.

    Only the `chunks` folder goes; the records (`audio.json`, `document.json`, `job.json`)
    stay, so a finished job can still be listed and played. The next run speaks again.
    """
    size = cache_size(work)
    shutil.rmtree(work / CHUNKS, ignore_errors=True)
    return size
