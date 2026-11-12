"""Reading the voice's chunk files: WAV, 16-bit PCM, mono, one sample rate per job
(#69 plan, point B).

Output times everything from the frame counts in these files, not from the duration the
voice reported, so read-along timing is exact to the sample.
"""

from __future__ import annotations

import wave
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SAMPLE_WIDTH = 2  # bytes: 16-bit PCM
_BLOCK = 1 << 16  # frames read at a time


class ChunkAudioError(ValueError):
    """A chunk file is missing or not a 16-bit mono PCM WAV at the job's sample rate."""


@dataclass(frozen=True)
class ChunkAudio:
    """A chunk file's sample rate and its number of frames (samples, as it is mono)."""

    path: Path
    rate: int
    frames: int


def inspect(path: Path) -> ChunkAudio:
    """Read a chunk file's header; raise ChunkAudioError if it is missing or of another kind."""
    try:
        with wave.open(str(path), "rb") as audio:
            channels, width = audio.getnchannels(), audio.getsampwidth()
            rate, frames = audio.getframerate(), audio.getnframes()
    except FileNotFoundError:
        raise ChunkAudioError(f"audio chunk is missing: {path}") from None
    except (wave.Error, EOFError) as error:
        raise ChunkAudioError(f"audio chunk is not a PCM WAV file: {path} ({error})") from None
    if channels != 1 or width != SAMPLE_WIDTH or rate <= 0:
        raise ChunkAudioError(
            f"audio chunk must be 16-bit mono PCM WAV: {path} has {channels} channel(s), "
            f"{8 * width}-bit, {rate} Hz"
        )
    return ChunkAudio(path, rate, frames)


def frames_of(chunk: ChunkAudio) -> Iterator[bytes]:
    """The chunk's samples as raw 16-bit little-endian bytes, exactly `chunk.frames` of them.

    Raises ChunkAudioError if the file changed or vanished since it was inspected.
    """
    left = chunk.frames
    try:
        with wave.open(str(chunk.path), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (
                1,
                SAMPLE_WIDTH,
                chunk.rate,
            ) or audio.getnframes() != chunk.frames:
                raise ChunkAudioError(f"audio chunk changed during the run: {chunk.path}")
            while left > 0:
                data = audio.readframes(min(left, _BLOCK))
                if not data:
                    break
                left -= len(data) // SAMPLE_WIDTH
                yield data
    except FileNotFoundError:
        raise ChunkAudioError(f"audio chunk was removed during the run: {chunk.path}") from None
    except (wave.Error, EOFError) as error:
        raise ChunkAudioError(f"audio chunk became unreadable: {chunk.path} ({error})") from None
    if left != 0:
        raise ChunkAudioError(f"audio chunk is shorter than its header says: {chunk.path}")


def silence(frames: int) -> Iterator[bytes]:
    """`frames` samples of silence, in pieces."""
    while frames > 0:
        n = min(frames, _BLOCK)
        frames -= n
        yield bytes(n * SAMPLE_WIDTH)
