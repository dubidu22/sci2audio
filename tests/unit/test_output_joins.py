"""The pieces of a cut sentence sound joined (#480, D-730): the clause pause, the voice's edge
silence trimmed at a clause join, and the read-along `joins` key that a version-1 reader of
sci2audio v1.0.0 ignores."""

from __future__ import annotations

import json
import wave
from collections.abc import Iterable, Sequence
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
import readalong_v1_0
from hypothesis import given
from hypothesis import strategies as st
from output_helpers import RATE, decoded_samples

from sci2audio.core import AudioChunk, Span
from sci2audio.output import (
    BookInfo,
    Chapter,
    OutputSettings,
    Pause,
    ReadAlongError,
    Spoken,
    readalong,
    write_audiobook,
)
from sci2audio.output.ffmpeg import Ffmpeg, find_ffmpeg
from sci2audio.output.timeline import plan_timeline
from sci2audio.output.wav import (
    TRIM_KEEP,
    TRIM_MOST,
    TRIM_QUIET_DB,
    TRIM_STEP,
    ChunkAudio,
    edge_trim,
    frames_of,
    inspect,
    trimmed,
)

STEP = round(TRIM_STEP * RATE)  # 240 samples
KEEP = round(TRIM_KEEP * RATE)  # 720 samples
MOST = round(TRIM_MOST * RATE)  # 19200 samples
LOUD = 8000


def tone(frames: int, amplitude: int = LOUD) -> np.ndarray:
    return (amplitude * np.sin(np.arange(frames) / 5.0)).astype(np.int16)


def speech(lead: int, body: int, tail: int, *, floor: int = 0) -> np.ndarray:
    """`lead` samples of quiet, a tone of `body` samples, `tail` samples of quiet; the quiet
    holds noise of at most `floor`."""
    rng = np.random.default_rng(lead * 7 + tail)
    quiet = [rng.integers(-floor, floor + 1, n).astype(np.int16) for n in (lead, tail)]
    return np.concatenate([quiet[0], tone(body), quiet[1]])


def write_samples(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(samples.astype("<i2").tobytes())


# --- the clause pause -------------------------------------------------------------------------


def test_the_clause_pause_is_short_and_between_none_and_sentence() -> None:
    settings = OutputSettings()
    assert settings.clause_pause == 0.25
    assert settings.seconds(Pause.CLAUSE) == 0.25
    assert settings.seconds(Pause.NONE) == 0.0
    assert list(Pause).index(Pause.NONE) < list(Pause).index(Pause.CLAUSE)
    assert list(Pause).index(Pause.CLAUSE) < list(Pause).index(Pause.SENTENCE)
    assert Pause.strongest(Pause.CLAUSE, Pause.NONE) is Pause.CLAUSE
    assert Pause.strongest(Pause.CLAUSE, Pause.SENTENCE) is Pause.SENTENCE
    assert Pause.strongest(Pause.CLAUSE, Pause.PAUSE_EDIT) is Pause.PAUSE_EDIT
    assert OutputSettings(clause_pause=0.1).seconds(Pause.CLAUSE) == 0.1


@pytest.mark.parametrize("bad", [-0.01, 60.5, float("nan"), float("inf")])
def test_the_clause_pause_is_checked_like_the_others(bad: float) -> None:
    with pytest.raises(ValueError, match="clause_pause"):
        OutputSettings(clause_pause=bad)


# --- edge_trim (pure) ---------------------------------------------------------------------------


def test_silence_and_nothing_are_never_trimmed() -> None:
    assert edge_trim(np.zeros(48000, dtype=np.int16), RATE) == (0, 0)
    assert edge_trim(np.zeros(0, dtype=np.int16), RATE) == (0, 0)


def test_a_tone_keeps_30_ms_of_its_quiet_run_on_each_side() -> None:
    samples = speech(lead=10_000, body=24_000, tail=12_000)
    lead, tail = edge_trim(samples, RATE)
    # the quiet run counts in whole 10 ms steps from the chunk's start; a step holding a loud
    # sample stays whole
    assert lead == (10_000 // STEP) * STEP - KEEP
    assert tail == len(samples) - -(-34_000 // STEP) * STEP - KEEP
    aligned = speech(lead=50 * STEP, body=100 * STEP, tail=40 * STEP)
    assert edge_trim(aligned, RATE) == (50 * STEP - KEEP, 40 * STEP - KEEP)


def test_a_quiet_run_shorter_than_the_floor_is_kept_whole() -> None:
    assert edge_trim(speech(lead=KEEP, body=4800, tail=KEEP - 1), RATE) == (0, 0)
    assert edge_trim(speech(lead=KEEP + STEP, body=4800, tail=0), RATE) == (STEP, 0)
    assert edge_trim(tone(4800), RATE) == (0, 0)


def test_no_side_loses_more_than_the_cap() -> None:
    lead, tail = edge_trim(speech(lead=3 * RATE, body=4800, tail=2 * RATE), RATE)
    assert (lead, tail) == (MOST, MOST)


def test_quiet_is_measured_against_the_chunks_own_peak() -> None:
    # noise at -40 dB of the peak is not quiet; at -50 dB it is
    assert TRIM_QUIET_DB == -45.0  # the decided level (plan D-730), written out below
    level = LOUD * 10 ** (-45 / 20)
    noisy = speech(lead=12_000, body=24_000, tail=12_000, floor=int(level * 1.8))
    assert edge_trim(noisy, RATE) == (0, 0)
    hushed = speech(lead=12_000, body=24_000, tail=12_000, floor=int(level * 0.5))
    assert edge_trim(hushed, RATE) == (12_000 - KEEP, 12_000 - KEEP)
    # a quiet voice is trimmed like a loud one
    soft = (speech(lead=12_000, body=24_000, tail=12_000) // 40).astype(np.int16)
    assert edge_trim(soft, RATE) == (12_000 - KEEP, 12_000 - KEEP)


def test_the_full_scale_negative_sample_counts_as_loud() -> None:
    samples = np.zeros(10_000, dtype=np.int16)
    samples[5000] = -32768
    lead, tail = edge_trim(samples, RATE)
    assert lead <= 5000 < 10_000 - tail


@given(
    st.lists(st.integers(-32768, 32767), min_size=1, max_size=4000),
    st.integers(0, 3000),
    st.integers(0, 3000),
    st.sampled_from([8000, 16000, 22050, 24000, 48000]),
)
def test_the_kept_range_holds_every_sample_that_is_not_quiet(
    body: list[int], lead: int, tail: int, rate: int
) -> None:
    samples = np.concatenate(
        [np.zeros(lead, np.int16), np.array(body, np.int16), np.zeros(tail, np.int16)]
    )
    cut_lead, cut_tail = edge_trim(samples, rate)
    assert 0 <= cut_lead <= round(TRIM_MOST * rate)
    assert 0 <= cut_tail <= round(TRIM_MOST * rate)
    loudness = np.abs(samples.astype(np.int32))
    peak = int(loudness.max())
    if peak == 0:
        assert (cut_lead, cut_tail) == (0, 0)
        return
    assert cut_lead + cut_tail < len(samples)
    loud = np.flatnonzero(loudness >= peak * 10 ** (TRIM_QUIET_DB / 20))
    assert cut_lead <= loud[0] - min(loud[0], round(TRIM_KEEP * rate))
    assert len(samples) - cut_tail >= loud[-1] + 1 + min(
        len(samples) - loud[-1] - 1, round(TRIM_KEEP * rate)
    )


# --- trimmed chunks ---------------------------------------------------------------------------


def test_a_trimmed_chunk_streams_only_its_kept_samples(tmp_path: Path) -> None:
    samples = speech(lead=50 * STEP, body=100 * STEP, tail=40 * STEP)
    write_samples(tmp_path / "a.wav", samples)
    chunk = inspect(tmp_path / "a.wav")
    both = trimmed(chunk, start=True, end=True)
    assert (both.skip_start, both.skip_end) == (50 * STEP - KEEP, 40 * STEP - KEEP)
    assert both.kept == len(samples) - both.skip_start - both.skip_end
    data = np.frombuffer(b"".join(frames_of(both)), dtype="<i2")
    assert np.array_equal(data, samples[both.skip_start : len(samples) - both.skip_end])
    start_only = trimmed(chunk, start=True, end=False)
    assert (start_only.skip_start, start_only.skip_end) == (50 * STEP - KEEP, 0)
    end_only = trimmed(chunk, start=False, end=True)
    assert (end_only.skip_start, end_only.skip_end) == (0, 40 * STEP - KEEP)
    assert trimmed(chunk, start=False, end=False) is chunk
    # the file itself is never changed
    with wave.open(str(tmp_path / "a.wav"), "rb") as audio:
        assert audio.getnframes() == len(samples)


def test_a_chunk_cannot_skip_more_than_it_has(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot skip"):
        ChunkAudio(tmp_path / "a.wav", RATE, 100, 60, 41)
    with pytest.raises(ValueError, match="cannot skip"):
        ChunkAudio(tmp_path / "a.wav", RATE, 100, -1, 0)


# --- a book with a cut sentence -------------------------------------------------------------


class Capturing(Ffmpeg):
    """The real ffmpeg, keeping the samples fed to each run (the last run is the M4B)."""

    def __init__(self) -> None:
        super().__init__(find_ffmpeg())
        object.__setattr__(self, "fed", [])

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        data = bytearray()

        def tee() -> Iterable[bytes]:
            for piece in feed:
                data.extend(piece)
                yield piece

        out = super().run(args, tee())
        self.fed.append(np.frombuffer(bytes(data), dtype="<i2"))  # type: ignore[attr-defined]
        return out


QUIET = (50 * STEP, 40 * STEP)  # the voice's silence before and after its speech: 0.5 s, 0.4 s


def cut_sentence_book(folder: Path, pauses: Sequence[Pause]) -> tuple[list[Chapter], list[Spoken]]:
    """One chapter: a sentence, a long sentence cut into three pieces, a last sentence."""
    spoken = []
    for index, pause in enumerate(pauses):
        name = f"chunks/{index}.wav"
        write_samples(folder / name, speech(QUIET[0], 120 * STEP, QUIET[1]))
        chunk = AudioChunk(Span(0, 10 * index, 10 * index + 9), name, 1.0)
        spoken.append(Spoken(chunk, pause, f"piece {index}", pause is Pause.CLAUSE))
    return [Chapter("One", 0)], spoken


PIECES = (Pause.PARAGRAPH, Pause.SENTENCE, Pause.CLAUSE, Pause.CLAUSE, Pause.SENTENCE)


def loud_runs(samples: np.ndarray) -> list[tuple[int, int]]:
    """Start and end of each stretch of tone in the fed samples (the quiet is exact zeros)."""
    loud = np.abs(samples.astype(np.int32)) > 0
    edges = np.flatnonzero(np.diff(np.concatenate([[0], loud.astype(np.int8), [0]])))
    runs = list(zip(edges[::2], edges[1::2], strict=True))
    merged: list[tuple[int, int]] = []
    for start, end in runs:  # a sine crosses zero: join runs closer than a step
        if merged and start - merged[-1][1] < STEP:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def test_the_gap_at_a_cut_is_the_clause_pause_and_the_times_stay_exact(tmp_path: Path) -> None:
    chapters, spoken = cut_sentence_book(tmp_path / "job", PIECES)
    book = BookInfo("Cut", (), "en")
    settings = OutputSettings()
    ffmpeg = Capturing()
    written = write_audiobook(
        tmp_path / "job", tmp_path / "out", chapters, spoken, book, settings, ffmpeg=ffmpeg
    )
    fed = ffmpeg.fed[-1]  # type: ignore[attr-defined]
    runs = loud_runs(fed)
    assert len(runs) == len(PIECES)
    gaps = [(b[0] - a[1]) / RATE for a, b in pairwise(runs)]
    clause = settings.clause_pause + 2 * TRIM_KEEP  # the pause and 30 ms kept on each side
    sentence = settings.sentence_pause + (QUIET[0] + QUIET[1]) / RATE  # untrimmed
    assert gaps == pytest.approx([sentence, clause, clause, sentence], abs=2 / RATE)

    # the read-along times are those of the kept samples, and the M4B is as long as the feed
    data = readalong.read_readalong(written.readalong)
    assert written.m4b is not None
    assert decoded_samples(written.m4b) == len(fed) == round(data.duration * RATE)
    for chunk, (start, end) in zip(data.chunks, runs, strict=True):
        assert chunk.start * RATE <= start + 1
        assert end - 1 <= chunk.end * RATE
    starts = [c.start for c in data.chunks]
    ends = [c.end for c in data.chunks]
    assert starts[2] - ends[1] == pytest.approx(settings.clause_pause, abs=0.0015)
    assert starts[3] - ends[2] == pytest.approx(settings.clause_pause, abs=0.0015)
    assert [c.joins for c in data.chunks] == [False, False, True, True, False]
    # only the edges at the two joins were trimmed: pieces 1 and 3 lost their tail,
    # 2 and 3 their lead (three pieces of one sentence); the rest kept every sample
    length = QUIET[0] + 120 * STEP + QUIET[1]
    cut = (QUIET[0] - KEEP, QUIET[1] - KEEP)
    kept = [length, length - cut[1], length - cut[0] - cut[1], length - cut[0], length]
    assert [round((e - s) * RATE) for s, e in zip(starts, ends, strict=True)] == kept


def test_a_chapter_start_is_never_trimmed_whatever_its_pause(tmp_path: Path) -> None:
    pauses = (Pause.PARAGRAPH, Pause.CLAUSE)
    _, spoken = cut_sentence_book(tmp_path / "job", pauses)
    chapters = [Chapter("One", 0), Chapter("Two", 1)]
    written = write_audiobook(
        tmp_path / "job", tmp_path / "out", chapters, spoken, BookInfo("Cut", (), "en")
    )
    data = readalong.read_readalong(written.readalong)
    length = QUIET[0] + 120 * STEP + QUIET[1]
    assert [round((c.end - c.start) * RATE) for c in data.chunks] == [length, length]


def test_none_still_means_no_pause_and_no_trim(tmp_path: Path) -> None:
    """Plans made before #480 gave a cut Pause.NONE: it keeps its meaning."""
    chapters, spoken = cut_sentence_book(tmp_path / "job", (Pause.PARAGRAPH, Pause.NONE))
    written = write_audiobook(
        tmp_path / "job", tmp_path / "out", chapters, spoken, BookInfo("Cut", (), "en")
    )
    data = readalong.read_readalong(written.readalong)
    length = QUIET[0] + 120 * STEP + QUIET[1]
    assert [round((c.end - c.start) * RATE) for c in data.chunks] == [length, length]
    assert data.chunks[1].start == data.chunks[0].end


# --- the read-along key and version 1 ---------------------------------------------------------


def _with_joins() -> readalong.ReadAlong:
    pieces = [
        Spoken(AudioChunk(Span(0, 0, 9), "c/0.wav", 0.1), Pause.PARAGRAPH),
        Spoken(AudioChunk(Span(0, 10, 20), "c/1.wav", 0.1), Pause.CLAUSE, "", True),
        Spoken(AudioChunk(Span(1, 0, 7), "c/2.wav", 0.1), Pause.PARAGRAPH),
    ]
    chapters = [Chapter("One", 0)]
    t = plan_timeline(chapters, pieces, [2400, 1200, 4800], RATE, OutputSettings())
    return readalong.build(t, pieces, "Book.m4b", ["Book - 01 One.mp3"])


def test_joins_is_written_only_where_true_and_survives_the_file() -> None:
    data = _with_joins()
    assert [c.joins for c in data.chunks] == [False, True, False]
    raw = json.loads(readalong.to_json(data))
    assert raw["version"] == 1
    assert [c.get("joins") for c in raw["chunks"]] == [None, True, None]
    assert list(raw["chunks"][1]) == [
        "chapter",
        "start",
        "end",
        "block",
        "start_char",
        "end_char",
        "joins",
    ]
    assert readalong.from_json(readalong.to_json(data)) == data


@pytest.mark.parametrize("value", [1, "true", None, [True]])
def test_joins_must_be_true_or_false(value: object) -> None:
    raw = json.loads(readalong.to_json(_with_joins()))
    raw["chunks"][1]["joins"] = value
    with pytest.raises(ReadAlongError, match="joins"):
        readalong.from_json(json.dumps(raw))
    raw["chunks"][1]["joins"] = False
    assert not readalong.from_json(json.dumps(raw)).chunks[1].joins


def test_the_released_version_1_reader_reads_a_file_with_joins() -> None:
    """D-730: sci2audio v1.0.0's reader takes a new file and ignores the key."""
    data = _with_joins()
    old = readalong_v1_0.from_json(readalong.to_json(data))
    assert (old.sample_rate, old.duration, old.m4b) == (data.sample_rate, data.duration, data.m4b)
    assert [(c.title, c.mp3, c.start, c.end, c.first_chunk) for c in old.chapters] == [
        (c.title, c.mp3, c.start, c.end, c.first_chunk) for c in data.chapters
    ]
    assert [(c.chapter, c.start, c.end, c.span) for c in old.chunks] == [
        (c.chapter, c.start, c.end, c.span) for c in data.chunks
    ]


def test_this_reader_takes_a_file_the_released_version_wrote() -> None:
    """D-730: a file sci2audio v1.0.0 wrote (no key) reads with no chunk joined."""
    pieces = [
        Spoken(AudioChunk(Span(0, 0, 9), "c/0.wav", 0.1), Pause.PARAGRAPH),
        Spoken(AudioChunk(Span(0, 10, 20), "c/1.wav", 0.1), Pause.NONE),
    ]
    t = plan_timeline([Chapter("One", 0)], pieces, [2400, 1200], RATE, OutputSettings())
    text = readalong_v1_0.to_json(readalong_v1_0.build(t, pieces, "Book.m4b", None))
    assert "joins" not in text
    data = readalong.from_json(text)
    assert [c.joins for c in data.chunks] == [False, False]
    assert [(c.chapter, c.start, c.end, c.span) for c in data.chunks] == [
        (c.chapter, c.start, c.end, c.span) for c in readalong_v1_0.from_json(text).chunks
    ]
