"""Reading the voice's chunk files: WAV, 16-bit PCM, mono, one sample rate per job
(#69 plan, point B).

Output times everything from the frame counts in these files, not from the duration the
voice reported, so read-along timing is exact to the sample. Where a long sentence was cut
(`Pause.CLAUSE`, #480), the voice's own silence at the cut is trimmed while the book is
assembled (`edge_trim`); the chunk files themselves are never changed.
"""

from __future__ import annotations

import wave
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

SAMPLE_WIDTH = 2  # bytes: 16-bit PCM
_BLOCK = 1 << 16  # frames read at a time

# the voice's edge silence at a clause join (#480): measured in 10 ms steps, a step is quiet
# when its loudest sample is 45 dB under the chunk's loudest; each side keeps 30 ms of its
# quiet run and loses at most 0.8 s (Kokoro leaves about 0.25 to 0.5 s on each side)
TRIM_STEP = 0.010
TRIM_QUIET_DB = -45.0
TRIM_KEEP = 0.030
TRIM_MOST = 0.8


class ChunkAudioError(ValueError):
    """A chunk file is missing or not a 16-bit mono PCM WAV at the job's sample rate."""


@dataclass(frozen=True)
class ChunkAudio:
    """A chunk file's sample rate and its number of frames (samples, as it is mono).

    `skip_start` and `skip_end` frames are left out at its start and end when the book is
    assembled (the voice's edge silence at a clause join, #480); `kept` frames remain."""

    path: Path
    rate: int
    frames: int
    skip_start: int = 0
    skip_end: int = 0

    def __post_init__(self) -> None:
        if self.skip_start < 0 or self.skip_end < 0 or self.kept < 0:
            raise ValueError(f"cannot skip {self.skip_start} + {self.skip_end} of {self.frames}")

    @property
    def kept(self) -> int:
        return self.frames - self.skip_start - self.skip_end


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
    """The chunk's kept samples as raw 16-bit little-endian bytes, exactly `chunk.kept` of
    them, from frame `chunk.skip_start` on.

    Raises ChunkAudioError if the file changed or vanished since it was inspected.
    """
    left = chunk.kept
    try:
        with wave.open(str(chunk.path), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (
                1,
                SAMPLE_WIDTH,
                chunk.rate,
            ) or audio.getnframes() != chunk.frames:
                raise ChunkAudioError(f"audio chunk changed during the run: {chunk.path}")
            if chunk.skip_start:
                audio.setpos(chunk.skip_start)
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


def edge_trim(samples: np.ndarray, rate: int) -> tuple[int, int]:
    """How many samples of quiet to drop at the start and at the end of a chunk (#480).

    `samples` are the chunk's 16-bit samples. A chunk that is all silence keeps everything;
    otherwise every sample at or above the quiet level stays, as does `TRIM_KEEP` of the
    quiet run on each side, and no side loses more than `TRIM_MOST`. Pure.
    """
    size = len(samples)
    loudness = np.abs(np.asarray(samples, dtype=np.int32))
    peak = int(loudness.max()) if size else 0
    if peak == 0:
        return 0, 0
    level = peak * 10 ** (TRIM_QUIET_DB / 20)
    step = max(1, round(TRIM_STEP * rate))
    steps = -(-size // step)
    padded = np.zeros(steps * step, dtype=np.int32)
    padded[:size] = loudness
    loud = np.flatnonzero(padded.reshape(steps, step).max(axis=1) >= level)
    lead_quiet = int(loud[0]) * step
    tail_quiet = max(0, size - (int(loud[-1]) + 1) * step)
    keep, most = round(TRIM_KEEP * rate), round(TRIM_MOST * rate)
    return min(max(0, lead_quiet - keep), most), min(max(0, tail_quiet - keep), most)


def trimmed(chunk: ChunkAudio, *, start: bool, end: bool) -> ChunkAudio:
    """The chunk with its edge silence skipped at the start, the end or both (`edge_trim`).

    Raises ChunkAudioError if the file changed or vanished since it was inspected.
    """
    if not (start or end):
        return chunk
    data = b"".join(frames_of(replace(chunk, skip_start=0, skip_end=0)))
    lead, tail = edge_trim(np.frombuffer(data, dtype="<i2"), chunk.rate)
    return replace(chunk, skip_start=lead if start else 0, skip_end=tail if end else 0)


def silence(frames: int) -> Iterator[bytes]:
    """`frames` samples of silence, in pieces."""
    while frames > 0:
        n = min(frames, _BLOCK)
        frames -= n
        yield bytes(n * SAMPLE_WIDTH)
