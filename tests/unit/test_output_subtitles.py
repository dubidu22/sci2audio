"""Subtitles (#214, OU-04, D-606): SRT and WebVTT cues of the spoken text on the read-along's
times. Pure tests of the cues and formats, Hypothesis properties, and files written with
the real ffmpeg (a few seconds of tones), which also parses them back."""

from __future__ import annotations

import errno
import itertools
import json
import re
import subprocess
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from output_helpers import RATE, Job, ffmpeg_exe, make_job

from sci2audio.core import AudioChunk, Span
from sci2audio.output import Chapter, OutputSettings, Pause, Spoken, read_readalong, write_audiobook
from sci2audio.output import readalong as readalong_module
from sci2audio.output.subtitles import (
    LINE,
    LINES,
    Cue,
    cues,
    milliseconds,
    split,
    to_srt,
    to_vtt,
    wrap,
)
from sci2audio.output.timeline import plan_timeline

TEXTS = (
    "Introduction to tones.",
    "Figure 2 is not read here; it shows the spectrum.",
    "Tones are sounds of one frequency.",
    "We measured forty tones, each for two seconds, at three volumes; the louder ones, as "
    "expected, were heard first, and the quiet ones were missed by two of the ten listeners.",
    "Short.",
    "See https://example.org/a/very/long/path/that/goes/on/and/on/for/a/while for more.",
)


def job_with_text(folder: Path) -> Job:
    job = make_job(folder, frames=((4800, 2400), (3600,), (2400, 1200, 6000)))
    spoken = [Spoken(s.chunk, s.pause, TEXTS[n]) for n, s in enumerate(job.spoken)]
    return Job(job.folder, job.chapters, spoken, job.book)


def timeline_of(chapters: list[Chapter], spoken: list[Spoken], frames: list[int]):  # type: ignore[no-untyped-def]
    return plan_timeline(chapters, spoken, frames, RATE, OutputSettings())


def spoken_texts(*texts: str) -> list[Spoken]:
    return [
        Spoken(AudioChunk(Span(n, 0, 1), f"c/{n}.wav", 1.0), Pause.SENTENCE, text)
        for n, text in enumerate(texts)
    ]


# --- lines and cues -----------------------------------------------------------------------


def test_a_short_text_is_one_line() -> None:
    assert wrap(["A", "short", "line."]) == ("A short line.",)
    assert split("A  short\n line.") == [("A short line.",)]


def test_two_lines_are_as_even_as_they_can_be() -> None:
    words = [
        "The",
        "quick",
        "brown",
        "fox",
        "jumps",
        "over",
        "the",
        "lazy",
        "dog",
        "and",
        "runs",
        "away",
    ]
    lines = wrap(words)
    assert lines == ("The quick brown fox jumps over", "the lazy dog and runs away")
    assert all(len(line) <= LINE for line in lines)


def test_a_word_longer_than_a_line_has_a_line_of_its_own() -> None:
    url = "https://example.org/" + "x" * 60
    assert split(f"See {url} now.") == [("See", url), ("now.",)]
    assert split(url) == [(url,)]


def test_a_long_chunk_is_cut_after_a_clause_mark() -> None:
    pieces = split(TEXTS[3])
    assert len(pieces) > 1
    assert all(len(lines) <= LINES and all(len(x) <= LINE for x in lines) for lines in pieces)
    assert " ".join(pieces[0]).endswith(";"), pieces  # ";" before "," (D-606)
    assert " ".join(" ".join(p) for p in pieces) == TEXTS[3]


def test_a_comma_is_used_when_there_is_no_semicolon() -> None:
    text = (
        "Tones were played in a quiet room with the door shut, and every listener wrote down "
        "what they heard in their own words"
    )
    first = " ".join(split(text)[0])
    assert first.endswith("shut,"), first


def test_no_stub_cue_before_an_early_clause_mark() -> None:
    text = "Yes, " + " ".join(["tones"] * 30)
    assert " ".join(split(text)[0]) != "Yes,"


def test_an_empty_text_has_no_cue() -> None:
    assert split("") == split("  \n") == []


def test_each_chunk_has_its_own_cues_on_the_read_along_times() -> None:
    spoken = spoken_texts("One.", TEXTS[3], "Two.")
    chapters = [Chapter("A", 0), Chapter("B", 2)]
    timeline = timeline_of(chapters, spoken, [2400, 24000, 1200])
    book = cues(timeline, spoken)
    data = readalong_module.build(timeline, spoken, "b.m4b", None)
    assert next(c.chunk for c in book) == 0
    assert book[-1].chunk == 2
    for index, times in enumerate(data.chunks):
        own = [c for c in book if c.chunk == index]
        assert own[0].start == round(times.start * 1000)
        assert own[-1].end == round(times.end * 1000)
        assert all(a.end == b.start for a, b in itertools.pairwise(own))
    # a chapter's cues count from the chapter's start, the read-along's rule for MP3s
    second = cues(timeline, spoken, 1)
    origin = round(data.chapters[1].start * 1000)
    assert [(c.start, c.end) for c in second] == [
        (c.start - origin, c.end - origin) for c in book if c.chunk == 2
    ]


def test_milliseconds_round_as_the_read_along_does() -> None:
    for samples in (0, 1, 11, 12, 13, 23999, 24000, 36012, 10**9 + 7):
        assert milliseconds(samples, RATE) == round(readalong_module._seconds(samples, RATE) * 1000)


# --- formats --------------------------------------------------------------------------


def test_srt_numbers_cues_from_one_with_comma_milliseconds() -> None:
    text = to_srt([Cue(0, 0, 1500, ("One.",)), Cue(1, 3_723_004, 360_000_000, ("Two", "lines."))])
    assert text == (
        "1\n00:00:00,000 --> 00:00:01,500\nOne.\n\n2\n01:02:03,004 --> 100:00:00,000\nTwo\nlines.\n"
    )


def test_srt_shows_an_arrow_in_the_text_so_it_is_not_a_time_line() -> None:
    assert "x -> y" in to_srt([Cue(0, 0, 10, ("x --> y",))])


def test_vtt_has_its_header_dot_milliseconds_and_escapes() -> None:
    text = to_vtt([Cue(0, 0, 1500, ("a < b & c > d",)), Cue(1, 1500, 2000, ("x --> y",))])
    assert text == (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.500\na &lt; b &amp; c &gt; d\n\n"
        "00:00:01.500 --> 00:00:02.000\nx --&gt; y\n"
    )


SRT_BLOCK = re.compile(
    r"\A(\d+)\n(\d{2,}:\d{2}:\d{2},\d{3}) --> (\d{2,}:\d{2}:\d{2},\d{3})\n(.+)\Z", re.S
)
VTT_BLOCK = re.compile(
    r"\A(\d{2,}:\d{2}:\d{2}\.\d{3}) --> (\d{2,}:\d{2}:\d{2}\.\d{3})\n(.+)\Z", re.S
)


def ms_of(stamp: str) -> int:
    hours, minutes, rest = stamp.replace(",", ".").split(":")
    return (int(hours) * 3600 + int(minutes) * 60) * 1000 + round(float(rest) * 1000)


def parse_srt(text: str) -> list[tuple[int, int, str]]:
    """A strict reading: numbered from 1 without gaps, one blank line between cues."""
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    out = []
    for number, block in enumerate(text[:-1].split("\n\n"), start=1):
        match = SRT_BLOCK.match(block)
        assert match, block
        assert int(match[1]) == number
        assert all(line.strip() for line in match[4].split("\n"))
        out.append((ms_of(match[2]), ms_of(match[3]), match[4]))
    return out


def parse_vtt(text: str) -> list[tuple[int, int, str]]:
    """A strict reading of what we write: the WEBVTT line, then timed cues, no `-->` in a
    cue's text, no raw `<` or `&` that is not an escape."""
    if text == "WEBVTT\n":
        return []
    assert text.startswith("WEBVTT\n\n")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    out = []
    for block in text[len("WEBVTT\n\n") : -1].split("\n\n"):
        match = VTT_BLOCK.match(block)
        assert match, block
        body = match[3]
        assert "-->" not in body
        assert "<" not in body
        assert not re.search(r"&(?!amp;|lt;|gt;)", body)
        out.append((ms_of(match[1]), ms_of(match[2]), body))
    return out


# --- properties -----------------------------------------------------------------------

WORD = st.text(alphabet="abcdefghijkXYZ0123456789-<>&./", min_size=1, max_size=12)
LONG_WORD = st.text(alphabet="abcxyz/:.", min_size=LINE + 1, max_size=70)
MARKED = st.tuples(WORD, st.sampled_from([",", ";", ":", ".", ""])).map("".join)
SPACE = st.sampled_from([" ", "  ", "\n", "\t", " \n "])
CHUNK_TEXT = st.lists(st.one_of(MARKED, MARKED, MARKED, LONG_WORD), max_size=60).flatmap(
    lambda words: st.lists(SPACE, min_size=len(words), max_size=len(words)).map(
        lambda gaps: "".join(gap + word for gap, word in zip(gaps, words, strict=True))
    )
)


@given(text=CHUNK_TEXT)
def test_split_keeps_every_word_in_lines_that_fit(text: str) -> None:
    pieces = split(text)
    assert " ".join(" ".join(lines) for lines in pieces) == " ".join(text.split())
    for lines in pieces:
        assert 1 <= len(lines) <= LINES
        assert all(line and (len(line) <= LINE or " " not in line) for line in lines)


@given(
    data=st.lists(st.tuples(CHUNK_TEXT, st.integers(0, 20 * RATE)), min_size=1, max_size=8),
    cut=st.integers(0, 7),
)
def test_cues_are_contiguous_per_chunk_and_sit_on_its_read_along_times(
    data: list[tuple[str, int]], cut: int
) -> None:
    spoken = spoken_texts(*(text for text, _ in data))
    chapters = [Chapter("A", 0), *([Chapter("B", cut)] if 0 < cut < len(data) else [])]
    timeline = timeline_of(chapters, spoken, [frames for _, frames in data])
    book = cues(timeline, spoken)
    times = readalong_module.build(timeline, spoken, "b.m4b", None)
    for a, b in itertools.pairwise(book):
        assert a.start <= a.end <= b.start  # in order, never overlapping
    for index, (text, _) in enumerate(data):
        own = [c for c in book if c.chunk == index]
        if not text.split():
            assert own == []
            continue
        assert own[0].start == round(times.chunks[index].start * 1000)
        assert own[-1].end == round(times.chunks[index].end * 1000)
        assert all(a.end == b.start for a, b in itertools.pairwise(own))  # contiguous
        assert " ".join(" ".join(c.lines) for c in own) == " ".join(text.split())
    for number, chapter in enumerate(times.chapters):
        origin = round(chapter.start * 1000)
        part = cues(timeline, spoken, number)
        assert all(c.start >= 0 for c in part)
        assert [(c.chunk, c.start + origin, c.end + origin, c.lines) for c in part] == [
            (c.chunk, c.start, c.end, c.lines)
            for c in book
            if timeline.chapters[number].first <= c.chunk < timeline.chapters[number].stop
        ]
    assert parse_vtt(to_vtt(book)) == [
        (
            c.start,
            c.end,
            "\n".join(c.lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        )
        for c in book
    ]
    if book:
        assert [(a, b) for a, b, _ in parse_srt(to_srt(book))] == [(c.start, c.end) for c in book]


# --- files ----------------------------------------------------------------------------

SUBS = [
    "A Study of Tones - 01 Introduction.srt",
    "A Study of Tones - 01 Introduction.vtt",
    "A Study of Tones - 02 Methods; data = 1 # 2.srt",
    "A Study of Tones - 02 Methods; data = 1 # 2.vtt",
    "A Study of Tones - 03 Results.srt",
    "A Study of Tones - 03 Results.vtt",
    "A Study of Tones.srt",
    "A Study of Tones.vtt",
]


@pytest.fixture
def job(tmp_path: Path) -> Job:
    return job_with_text(tmp_path / "job")


def write(job: Job, out: Path, **settings: object):  # type: ignore[no-untyped-def]
    return write_audiobook(
        job.folder,
        out,
        job.chapters,
        job.spoken,
        job.book,
        OutputSettings(**{"subtitles": True, **settings}),  # type: ignore[arg-type]
    )


def ffmpeg_reads(path: Path) -> list[tuple[int, int, str]]:
    """The cues as the bundled ffmpeg's SRT or WebVTT demuxer reads them, written as SRT."""
    result = subprocess.run(
        [ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "srt", "-"],
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return parse_srt(result.stdout.replace("\r\n", "\n").rstrip("\n") + "\n")


def test_subtitles_are_off_by_default(job: Job, tmp_path: Path) -> None:
    written = write_audiobook(job.folder, tmp_path / "out", job.chapters, job.spoken, job.book)
    assert written.subtitles == ()
    assert not [p for p in (tmp_path / "out").iterdir() if p.suffix in (".srt", ".vtt")]


def test_subtitle_files_match_the_read_along_and_ffmpeg_reads_them(
    job: Job, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    written = write(job, out)
    assert [p.name for p in written.subtitles] == SUBS
    assert all(p.parent == out.absolute() for p in written.subtitles)
    times = read_readalong(written.readalong)
    for number, chapter in enumerate([*times.chapters, None]):
        srt, vtt = written.subtitles[2 * number : 2 * number + 2]
        ours = parse_srt(srt.read_text(encoding="utf-8"))
        assert [(a, b) for a, b, _ in parse_vtt(vtt.read_text(encoding="utf-8"))] == [
            (a, b) for a, b, _ in ours
        ]
        chunks = [
            (n, c) for n, c in enumerate(times.chunks) if chapter is None or c.chapter == number
        ]
        origin = 0.0 if chapter is None else chapter.start
        starts = {round((c.start - origin) * 1000) for _, c in chunks}
        ends = {round((c.end - origin) * 1000) for _, c in chunks}
        # every chunk starts and ends a cue, on the read-along's own times
        assert starts <= {a for a, _, _ in ours}
        assert ends <= {b for _, b, _ in ours}
        assert ours[0][0] == min(starts)
        assert ours[-1][1] == max(ends)
        assert ffmpeg_reads(srt) == ours
        assert [(a, b) for a, b, _ in ffmpeg_reads(vtt)] == [(a, b) for a, b, _ in ours]
    whole = " ".join(t for _, _, t in parse_srt(written.subtitles[-2].read_text(encoding="utf-8")))
    assert " ".join(whole.split()) == " ".join(TEXTS)


def test_mp3s_only_write_chapter_subtitles_m4b_only_the_books(job: Job, tmp_path: Path) -> None:
    assert [p.name for p in write(job, tmp_path / "a", m4b=False).subtitles] == SUBS[:-2]
    assert [p.name for p in write(job, tmp_path / "b", mp3=False).subtitles] == SUBS[-2:]


def test_existing_subtitles_are_refused_without_overwrite(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / SUBS[-1]).write_text("mine", encoding="utf-8")
    with pytest.raises(FileExistsError, match=re.escape(SUBS[-1])):
        write(job, out)
    assert [p.name for p in out.iterdir()] == [SUBS[-1]]  # nothing else was written
    written = write_audiobook(
        job.folder,
        out,
        job.chapters,
        job.spoken,
        job.book,
        OutputSettings(subtitles=True),
        overwrite=True,
    )
    assert written.subtitles[-1].read_text(encoding="utf-8").startswith("WEBVTT\n")


@pytest.mark.parametrize("failing", ["Results.vtt.partial", ".readalong.json.partial"])
def test_disk_full_after_some_subtitles_takes_the_new_ones_back(
    job: Job, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    """No half file; the subtitle files this run put in place are removed again, so a rerun
    is not refused over them. A subtitle file that was there before stays (it was only
    replaced with `overwrite`, and that cannot be undone)."""
    out = tmp_path / "out"
    out.mkdir()
    (out / SUBS[0]).write_text("mine", encoding="utf-8")
    original = Path.write_text

    def half_then_full(self: Path, text: str, *args, **kwargs) -> int:  # type: ignore[no-untyped-def]
        if self.name.endswith(failing):
            original(self, text[: len(text) // 2], *args, **kwargs)
            raise OSError(errno.ENOSPC, "No space left on device")
        return original(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", half_then_full)
    with pytest.raises(OSError, match="No space left"):
        write_audiobook(
            job.folder,
            out,
            job.chapters,
            job.spoken,
            job.book,
            OutputSettings(subtitles=True),
            overwrite=True,
        )
    left = sorted(p.name for p in out.iterdir())
    assert not [n for n in left if n.endswith((".partial", ".readalong.json"))], left
    assert [n for n in left if n.endswith((".srt", ".vtt"))] == [SUBS[0]]
    assert (out / SUBS[0]).read_text(encoding="utf-8").startswith("1\n00:00:")  # replaced
    assert "A Study of Tones.m4b" in left  # the app removes new audio files (it knows them)


def test_the_readalong_file_is_unchanged_by_subtitles(job: Job, tmp_path: Path) -> None:
    plain = write_audiobook(job.folder, tmp_path / "a", job.chapters, job.spoken, job.book)
    with_subs = write(job, tmp_path / "b")
    assert json.loads(plain.readalong.read_text()) == json.loads(with_subs.readalong.read_text())
