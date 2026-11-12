"""The output stage's parts without ffmpeg: input types, pauses, the timeline, file names,
the ffmetadata text and the read-along format (#69)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import AudioChunk, Span
from sci2audio.output import (
    BookInfo,
    Chapter,
    OutputSettings,
    Pause,
    ReadAlongError,
    Spoken,
    names,
    readalong,
)
from sci2audio.output.timeline import plan_timeline, samples
from sci2audio.output.write import _escape, _ffmetadata, _language

RATE = 24000


def spoken(n: int, pause: Pause = Pause.SENTENCE) -> list[Spoken]:
    return [Spoken(AudioChunk(Span(i, 0, 1), f"c/{i}.wav", 0.1), pause) for i in range(n)]


# --- input types -------------------------------------------------------------------------


def test_settings_defaults_are_the_decided_pause_lengths() -> None:
    """Q8 plus the sentence pause of the #69 plan (point A)."""
    s = OutputSettings()
    assert (s.chapter_pause, s.heading_pause, s.paragraph_pause, s.pause_edit) == (
        2.0,
        1.0,
        0.6,
        0.5,
    )
    assert s.sentence_pause == 0.3
    assert s.seconds(Pause.NONE) == 0.0
    assert s.seconds(Pause.HEADING) == 1.0
    assert s.seconds(Pause.PAUSE_EDIT) == 0.5


@pytest.mark.parametrize(
    "bad",
    [
        {"sentence_pause": -0.1},
        {"chapter_pause": float("nan")},
        {"heading_pause": 61},
        {"mp3_bitrate": "64"},
        {"aac_bitrate": "1000k"},
        {"mp3": False, "m4b": False},
    ],
)
def test_settings_refuse_bad_values(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 (each case has its own message)
        OutputSettings(**bad)  # type: ignore[arg-type]


def test_pause_strongest() -> None:
    assert Pause.strongest(Pause.SENTENCE, Pause.PARAGRAPH, Pause.PAUSE_EDIT) is Pause.PARAGRAPH
    assert Pause.strongest(Pause.PAUSE_EDIT, Pause.HEADING) is Pause.HEADING
    assert Pause.strongest() is Pause.NONE


def test_chapter_and_book_need_titles() -> None:
    with pytest.raises(ValueError, match="title"):
        Chapter(" ", 0)
    with pytest.raises(ValueError, match=">= 0"):
        Chapter("A", -1)
    with pytest.raises(ValueError, match="title"):
        BookInfo("")
    with pytest.raises(ValueError, match="language"):
        BookInfo("T", language="")


@pytest.mark.parametrize(
    ("firsts", "count", "message"),
    [
        ([], 3, "at least one chapter"),
        ([1], 3, "start at chunk 0"),
        ([0, 2, 2], 3, "increasing"),
        ([0, 3], 3, "only 3"),
        ([0], 0, "nothing to write"),
    ],
)
def test_chapters_must_fit_the_chunks(firsts: list[int], count: int, message: str) -> None:
    chapters = [Chapter(f"C{i}", f) for i, f in enumerate(firsts)]
    with pytest.raises(ValueError, match=message):
        plan_timeline(chapters, spoken(count), [10] * count, RATE, OutputSettings())


# --- timeline ----------------------------------------------------------------------------


def test_timeline_places_pauses_before_chunks_and_chapter_pause_at_every_chapter() -> None:
    pieces = [
        *spoken(1),
        Spoken(AudioChunk(Span(1, 0, 1), "c/1.wav", 0.1), Pause.HEADING),
        Spoken(AudioChunk(Span(2, 0, 1), "c/2.wav", 0.1), Pause.NONE),
        # a chapter start gets the chapter pause, whatever kind the app gave it
        Spoken(AudioChunk(Span(3, 0, 1), "c/3.wav", 0.1), Pause.PARAGRAPH),
    ]
    chapters = [Chapter("One", 0), Chapter("Two", 3)]
    t = plan_timeline(chapters, pieces, [100, 200, 300, 400], RATE, OutputSettings())
    two, one, none = 48000, 24000, 0  # chapter, heading and no pause, in samples
    assert [(p.pause_start, p.start, p.end) for p in t.chunks] == [
        (0, two, two + 100),
        (two + 100, two + 100 + one, two + 300 + one),
        (two + 300 + one, two + 300 + one + none, two + 600 + one),
        (two + 600 + one, 2 * two + 600 + one, 2 * two + 1000 + one),
    ]
    assert [(c.start, c.end, c.first, c.stop) for c in t.chapters] == [
        (0, two + 600 + one, 0, 3),
        (two + 600 + one, 2 * two + 1000 + one, 3, 4),
    ]


@st.composite
def books(draw: st.DrawFn) -> tuple[list[Chapter], list[Spoken], list[int], int, OutputSettings]:
    count = draw(st.integers(1, 30))
    firsts = sorted({0, *draw(st.sets(st.integers(1, max(1, count - 1)), max_size=5))})
    firsts = [f for f in firsts if f < count]
    chapters = [Chapter(f"Chapter {i}", f) for i, f in enumerate(firsts)]
    kinds = draw(st.lists(st.sampled_from(list(Pause)), min_size=count, max_size=count))
    pieces = [
        Spoken(AudioChunk(Span(i, 0, 1), f"c/{i}.wav", 0.1), kind) for i, kind in enumerate(kinds)
    ]
    frames = draw(st.lists(st.integers(0, 50_000), min_size=count, max_size=count))
    rate = draw(st.sampled_from([8000, 16000, 22050, 24000, 44100, 48000]))
    lengths = st.floats(0, 5, allow_nan=False)
    settings = OutputSettings(
        chapter_pause=draw(lengths),
        heading_pause=draw(lengths),
        paragraph_pause=draw(lengths),
        pause_edit=draw(lengths),
        sentence_pause=draw(lengths),
    )
    return chapters, pieces, frames, rate, settings


@given(books())
def test_timeline_properties(
    book: tuple[list[Chapter], list[Spoken], list[int], int, OutputSettings],
) -> None:
    chapters, pieces, frames, rate, settings = book
    t = plan_timeline(chapters, pieces, frames, rate, settings)
    # chunks follow one another without gaps or overlaps, each as long as its file
    position = 0
    for placed, length in zip(t.chunks, frames, strict=True):
        assert placed.pause_start == position <= placed.start
        assert placed.end - placed.start == length
        position = placed.end
    assert t.total == position
    # every pause is the setting's length; a chapter's first chunk gets the chapter pause
    starts = {c.first for c in chapters}
    for index, (placed, piece) in enumerate(zip(t.chunks, pieces, strict=True)):
        wanted = settings.chapter_pause if index in starts else settings.seconds(piece.pause)
        assert placed.start - placed.pause_start == samples(wanted, rate)
    # the chapters tile the book, in order, each starting where its first chunk's pause does
    assert t.chapters[0].start == 0
    assert t.chapters[-1].end == t.total
    for a, b in zip(t.chapters, t.chapters[1:], strict=False):
        assert a.end == b.start
        assert a.stop == b.first
    for c in t.chapters:
        assert c.start == t.chunks[c.first].pause_start
        assert all(t.chunks[i].chapter == c.index for i in range(c.first, c.stop))


# --- file names ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("A Study of Tones", "A Study of Tones"),
        ('What? A "test": a/b\\c|d*e<f>', "What A test a b c d e f"),
        ("  ...Dots...  ", "Dots"),
        ("Tab\tand\nnewline", "Tab and newline"),
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("???", "audiobook"),
        ("", "audiobook"),
        ("Ünïcödé café", "Ünïcödé café"),
    ],
)
def test_book_names(title: str, expected: str) -> None:
    assert names.book_name(title) == expected


def test_chapter_file_names_keep_their_number() -> None:
    assert names.chapter_file("Book", 3, 9, "Results") == "Book - 03 Results.mp3"
    assert names.chapter_file("Book", 7, 120, "?") == "Book - 007 chapter.mp3"
    long = names.chapter_file("B" * 120, 12, 20, "C" * 200)
    assert long.startswith("B" * 80 + " - 12 ")
    assert len(long) == names.MAX_LENGTH + len(".mp3")


FORBIDDEN = set('<>:"/\\|?*') | {chr(c) for c in range(32)} | {"\x7f"}


@given(st.text())
def test_names_are_safe_everywhere(title: str) -> None:
    name = names.book_name(title)
    assert name
    assert 1 <= len(name) <= names.MAX_LENGTH
    assert not FORBIDDEN & set(name)
    assert name == name.strip(" .")
    assert name.split(".")[0].upper() not in {"CON", "PRN", "AUX", "NUL"}
    assert names.book_name(name) == name  # idempotent
    name.encode("utf-8")  # no lone surrogates


# --- ffmetadata text ---------------------------------------------------------------------


def test_ffmetadata_escapes_special_characters_and_counts_in_samples() -> None:
    assert _escape("a=b;c#d\\e\nf") == "a\\=b\\;c\\#d\\\\e f"
    chapters = [Chapter("One = 1", 0), Chapter("Two", 1)]
    t = plan_timeline(chapters, spoken(2), [100, 100], RATE, OutputSettings())
    text = _ffmetadata(t, BookInfo("T; x", ("A", "B")))
    assert text.startswith(";FFMETADATA1\ntitle=T\\; x\n")
    assert "artist=A\\; B\n" in text
    assert "comment=AI-generated audio" in text
    assert f"[CHAPTER]\nTIMEBASE=1/{RATE}\nSTART=0\nEND=48100\ntitle=One \\= 1\n" in text


def test_language_codes() -> None:
    assert _language(BookInfo("T", language="en-GB")) == "eng"
    assert _language(BookInfo("T", language="DE")) == "deu"
    assert _language(BookInfo("T", language="tlh")) == "und"


# --- read-along format -------------------------------------------------------------------


def _data() -> readalong.ReadAlong:
    chapters = [Chapter("One", 0), Chapter("Två", 2)]
    t = plan_timeline(chapters, spoken(3), [2400, 1200, 4800], RATE, OutputSettings())
    return readalong.build(t, spoken(3), "Book.m4b", ["Book - 01 One.mp3", "Book - 02 Två.mp3"])


def test_readalong_round_trip(tmp_path: Path) -> None:
    data = _data()
    path = tmp_path / "x.json"
    path.write_text(readalong.to_json(data), encoding="utf-8")
    assert readalong.read_readalong(path) == data
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert (raw["format"], raw["version"]) == ("sci2audio-readalong", 1)
    assert raw["chunks"][0] == {
        "chapter": 0,
        "start": 2.0,
        "end": 2.1,
        "block": 0,
        "start_char": 0,
        "end_char": 1,
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"version": 2}, "version 2 is not supported"),
        ({"format": "other"}, "not a sci2audio read-along"),
        ({"chunks": [{"chapter": 0}]}, "broken"),
        (
            {
                "chunks": [
                    {"chapter": 0, "start": 1, "end": 2, "block": 0, "start_char": 5, "end_char": 1}
                ]
            },
            "broken",
        ),
    ],
)
def test_readalong_refuses_unknown_or_broken_files(change: dict[str, object], message: str) -> None:
    raw = json.loads(readalong.to_json(_data()))
    raw.update(change)
    with pytest.raises(ReadAlongError, match=message):
        readalong.from_json(json.dumps(raw))


def test_readalong_refuses_text_that_is_not_json() -> None:
    with pytest.raises(ReadAlongError, match="broken"):
        readalong.from_json("not json")
    with pytest.raises(ReadAlongError, match="broken"):
        readalong.from_json("[]")
