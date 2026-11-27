"""Writing the audiobook one chapter at a time (#723, LW-01): each chapter's files are
complete as soon as its speech is, and the result is the book `write_audiobook` writes."""

from __future__ import annotations

import errno
import hashlib
import subprocess
from dataclasses import fields, replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from output_helpers import (
    Job,
    assert_joins_trim,
    ffmetadata,
    ffmpeg_exe,
    make_job,
    quiet_edged_job,
    tags_of,
)

from sci2audio.core import AudioChunk, Span
from sci2audio.output import (
    BookWriter,
    Chapter,
    ChunkAudioError,
    Ffmpeg,
    OutputSettings,
    Pause,
    Spoken,
    audiobook_targets,
    chapter_fingerprint,
    find_ffmpeg,
    read_readalong,
    write_audiobook,
)
from sci2audio.output.timeline import plan_timeline

ALL = OutputSettings(subtitles=True)
REAL = Ffmpeg(find_ffmpeg())


def cover_file(folder: Path) -> Path:
    """A small JPEG, so the cover's way into every file is part of the byte comparison."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "cover.jpg"
    command = [ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=32x32"]
    subprocess.run(
        [*command, "-frames:v", "1", str(path)],
        check=True,
    )
    return path


def hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def written_whole(job: Job, out: Path, settings: OutputSettings = ALL) -> dict[str, str]:
    write_audiobook(job.folder, out, job.chapters, job.spoken, job.book, settings)
    return hashes(out)


def test_write_audiobook_output_is_pinned_before_the_split(tmp_path: Path) -> None:
    """Characterisation: the same input gives the same bytes in every file, so the
    chapter-by-chapter writer below can be held to byte equality with it."""
    job = make_job(tmp_path / "job")
    first = written_whole(job, tmp_path / "one")
    assert first == written_whole(job, tmp_path / "two")
    assert list(first) == sorted(
        [
            "A Study of Tones - 01 Introduction.mp3",
            "A Study of Tones - 01 Introduction.srt",
            "A Study of Tones - 01 Introduction.vtt",
            "A Study of Tones - 02 Methods; data = 1 # 2.mp3",
            "A Study of Tones - 02 Methods; data = 1 # 2.srt",
            "A Study of Tones - 02 Methods; data = 1 # 2.vtt",
            "A Study of Tones - 03 Results.mp3",
            "A Study of Tones - 03 Results.srt",
            "A Study of Tones - 03 Results.vtt",
            "A Study of Tones.m4b",
            "A Study of Tones.readalong.json",
            "A Study of Tones.srt",
            "A Study of Tones.vtt",
        ]
    )


def by_chapter(job: Job, out: Path, settings: OutputSettings = ALL, **kwargs) -> BookWriter:  # type: ignore[no-untyped-def]
    """Every chapter of `job` added to a new writer in order (not finished)."""
    writer = BookWriter(
        job.folder, out, job.book, [c.title for c in job.chapters], settings, **kwargs
    )
    for number, (first, stop) in enumerate(ranges(job), start=1):
        writer.add(number, job.spoken[first:stop])
    return writer


def ranges(job: Job) -> list[tuple[int, int]]:
    firsts = [c.first for c in job.chapters]
    return list(zip(firsts, [*firsts[1:], len(job.spoken)], strict=True))


@pytest.mark.parametrize(
    "settings",
    [
        ALL,
        OutputSettings(),
        OutputSettings(m4b=False),
        OutputSettings(m4b=False, subtitles=True),
        OutputSettings(mp3=False, subtitles=True),
    ],
    ids=["everything", "default", "mp3-only", "mp3-and-subtitles", "m4b-only"],
)
def test_chapter_by_chapter_writes_the_same_bytes_as_write_audiobook(
    tmp_path: Path, settings: OutputSettings
) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    whole = written_whole(job, tmp_path / "whole", settings)
    written = by_chapter(job, tmp_path / "parts", settings).finish()
    assert hashes(tmp_path / "parts") == whole
    assert written.readalong.name in whole
    assert [p.name for p in written.mp3s] == sorted(n for n in whole if n.endswith(".mp3"))


@pytest.mark.parametrize(
    "settings",
    [ALL, OutputSettings(m4b=False, subtitles=True)],
    ids=["everything", "mp3-and-subtitles"],
)
def test_chapter_by_chapter_with_clause_joins_writes_the_same_bytes(
    tmp_path: Path, settings: OutputSettings
) -> None:
    job = quiet_edged_job(tmp_path / "job")
    assert_joins_trim(job)
    whole = written_whole(job, tmp_path / "whole", settings)
    writer = by_chapter(job, tmp_path / "parts", settings)
    writer.finish()
    # every chunk sits at a join inside its chapter: trimmed on the joined side(s) only,
    # and a chapter's first chunk keeps its lead, its last chunk its tail
    for chapter in writer.chapters:
        assert all(a.kept < a.frames for a in chapter.audio)
        assert chapter.audio[0].skip_start == 0
        assert chapter.audio[-1].skip_end == 0
        assert all(a.skip_start for a in chapter.audio[1:])
        assert all(a.skip_end for a in chapter.audio[:-1])
    assert hashes(tmp_path / "parts") == whole


def test_a_read_along_for_the_first_chapters_lists_only_them_on_the_book_timeline(
    tmp_path: Path,
) -> None:
    job = make_job(tmp_path / "job")
    whole_out = tmp_path / "whole"
    write_audiobook(job.folder, whole_out, job.chapters, job.spoken, job.book, ALL)
    book = read_readalong(next(whole_out.glob("*.readalong.json")))
    writer = BookWriter(
        job.folder, tmp_path / "parts", job.book, [c.title for c in job.chapters], ALL
    )
    for number, (first, stop) in enumerate(ranges(job), start=1):
        writer.add(number, job.spoken[first:stop])
        so_far = read_readalong(writer.targets.readalong)
        assert so_far.m4b is None
        assert so_far.chapters == book.chapters[:number]
        assert so_far.chunks == book.chunks[:stop]
        assert so_far.duration == book.chapters[number - 1].end
        assert sorted(p.name for p in (tmp_path / "parts").glob("*.mp3")) == [
            c.mp3 for c in book.chapters[:number]
        ]


def test_every_file_is_vouched_for_before_it_is_put_in_place(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    heard: list[tuple[str, int, str]] = []

    def vouch(target: Path, size: int, sha256: str) -> None:
        assert not target.exists() or target.name.endswith(".readalong.json")
        partial = target.with_name(f".{target.name}.partial")
        assert partial.stat().st_size == size
        assert hashlib.sha256(partial.read_bytes()).hexdigest() == sha256
        heard.append((target.name, size, sha256))

    by_chapter(job, tmp_path / "out", vouch=vouch).finish()
    final = {name: (size, sha) for name, size, sha in heard}
    on_disk = hashes(tmp_path / "out")
    assert set(final) == set(on_disk)
    assert all(final[name][1] == sha for name, sha in on_disk.items())


def test_a_refused_vouch_puts_no_file_in_place(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")

    def refuse(target: Path, size: int, sha256: str) -> None:
        raise OSError("the record could not be written")

    writer = BookWriter(
        job.folder, tmp_path / "out", job.book, [c.title for c in job.chapters], vouch=refuse
    )
    with pytest.raises(OSError, match="record"):
        writer.add(1, job.spoken[:2])
    assert list((tmp_path / "out").iterdir()) == []


def test_a_failing_chapter_leaves_no_partial_and_keeps_the_chapters_before_it(
    tmp_path: Path,
) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    writer = BookWriter(job.folder, out, job.book, [c.title for c in job.chapters], ALL)
    (first, stop), (second, end), _ = ranges(job)
    writer.add(1, job.spoken[first:stop])
    kept = hashes(out)
    (job.folder / job.spoken[second].chunk.file).unlink()
    with pytest.raises(ChunkAudioError):
        writer.add(2, job.spoken[second:end])
    assert hashes(out) == kept
    assert not [p for p in out.iterdir() if p.name.endswith(".partial")]


class Failing(Ffmpeg):
    """The real ffmpeg, failing on run number `at` (counted from 0) mid-stream."""

    def __init__(self, at: int) -> None:
        super().__init__(REAL.exe)
        object.__setattr__(self, "at", at)
        object.__setattr__(self, "calls", [0])

    def run(self, args, feed=()):  # type: ignore[no-untyped-def]
        call = self.calls[0]
        self.calls[0] += 1
        if call == self.at:

            def broken():  # type: ignore[no-untyped-def]
                yield from list(feed)[:1]
                raise OSError(errno.ENOSPC, "No space left on device")

            return REAL.run(args, broken())
        return REAL.run(args, feed)


def test_ffmpeg_failing_on_a_chapter_keeps_the_whole_chapters_before_it(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    writer = BookWriter(
        job.folder, out, job.book, [c.title for c in job.chapters], ffmpeg=Failing(1)
    )
    (a, b), (c, d), _ = ranges(job)
    writer.add(1, job.spoken[a:b])
    with pytest.raises(OSError, match="No space"):
        writer.add(2, job.spoken[c:d])
    names = sorted(p.name for p in out.iterdir())
    assert names == ["A Study of Tones - 01 Introduction.mp3", "A Study of Tones.readalong.json"]
    assert len(read_readalong(out / names[1]).chapters) == 1


class Fed(Ffmpeg):
    """The real ffmpeg, counting the samples fed to each run."""

    def __init__(self) -> None:
        super().__init__(REAL.exe)
        object.__setattr__(self, "samples", [])

    def run(self, args, feed=()):  # type: ignore[no-untyped-def]
        self.samples.append(0)

        def counted():  # type: ignore[no-untyped-def]
            for piece in feed:
                self.samples[-1] += len(piece) // 2
                yield piece

        return REAL.run(args, counted())


def test_writing_a_chapter_tells_how_many_of_its_samples_are_fed(tmp_path: Path) -> None:
    """#1061: a long chapter takes a while to encode; `add` tells each piece fed, so the
    app can show the write moving. The files are the same as without it."""
    job = make_job(tmp_path / "job")
    told: list[list[tuple[int, int]]] = []
    fed = Fed()
    writer = BookWriter(
        job.folder, tmp_path / "told", job.book, [c.title for c in job.chapters], ALL, ffmpeg=fed
    )
    for number, (first, stop) in enumerate(ranges(job), start=1):
        told.append([])
        writer.add(
            number,
            job.spoken[first:stop],
            progress=lambda done, total: told[-1].append((done, total)),
        )
    writer.finish()
    mp3s = fed.samples[: len(told)]  # type: ignore[attr-defined]  (then the M4B's)
    for chapter, samples in zip(told, mp3s, strict=True):
        assert chapter[0] == (0, samples)
        assert chapter[-1] == (samples, samples)
        assert len(chapter) > 2
        done = [d for d, _ in chapter]
        assert done == sorted(done)
        assert {total for _, total in chapter} == {samples}
    assert len(told) == len(job.chapters)
    by_chapter(job, tmp_path / "quiet").finish()
    assert hashes(tmp_path / "told") == hashes(tmp_path / "quiet")


def test_a_reused_chapter_is_not_encoded_again_and_the_book_is_the_same(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    (a, b), *rest = ranges(job)
    titles = [c.title for c in job.chapters]
    BookWriter(job.folder, out, job.book, titles, ALL).add(1, job.spoken[a:b])  # then killed
    first_mp3 = next(out.glob("* - 01 *.mp3"))
    counting = Failing(at=-1)
    writer = BookWriter(
        job.folder,
        out,
        job.book,
        [c.title for c in job.chapters],
        ALL,
        ffmpeg=counting,
        keep=list(out.iterdir()),
    )
    writer.add(1, job.spoken[a:b], written=True)
    for number, (first, stop) in enumerate(rest, start=2):
        writer.add(number, job.spoken[first:stop])
    writer.finish()
    assert counting.calls == [3]  # chapters 2 and 3 and the M4B; chapter 1 was kept
    assert first_mp3.exists()
    assert hashes(out) == written_whole(job, tmp_path / "whole")


def test_existing_files_are_refused_unless_kept_or_overwritten(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    by_chapter(job, out).finish()
    titles = [c.title for c in job.chapters]
    with pytest.raises(FileExistsError, match="exist already"):
        BookWriter(job.folder, out, job.book, titles, ALL)
    assert (out / "A Study of Tones.readalong.json").exists()  # nothing changed
    BookWriter(job.folder, out, job.book, titles, ALL, keep=list(out.iterdir()))
    BookWriter(job.folder, out, job.book, titles, ALL, overwrite=True)


def test_chapters_must_come_in_document_order(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    writer = BookWriter(job.folder, tmp_path / "out", job.book, [c.title for c in job.chapters])
    (a, b), (c, d), _ = ranges(job)
    writer.add(2, job.spoken[c:d])
    with pytest.raises(ValueError, match="comes after"):
        writer.add(1, job.spoken[a:b])
    with pytest.raises(ValueError, match="no chapter 4"):
        writer.add(4, job.spoken[a:b])


def test_a_gap_in_the_chapters_keeps_every_number(tmp_path: Path) -> None:
    """A chapter whose every sentence failed is left out; the others keep their numbers
    and the count, so files already playable are never renamed."""
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    writer = BookWriter(job.folder, out, job.book, [c.title for c in job.chapters])
    (a, b), _, (e, f) = ranges(job)
    writer.add(1, job.spoken[a:b])
    writer.add(3, job.spoken[e:f])
    written = writer.finish()
    assert [p.name for p in written.mp3s] == [
        "A Study of Tones - 01 Introduction.mp3",
        "A Study of Tones - 03 Results.mp3",
    ]
    assert tags_of(ffmetadata(written.mp3s[1]))["track"] == "3/3"
    data = read_readalong(written.readalong)
    assert [c.title for c in data.chapters] == ["Introduction", "Results"]


def test_the_fingerprint_is_the_same_for_the_same_input(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    spoken = job.spoken[:2]
    assert chapter_fingerprint(job.book, "Intro", 1, 3, spoken, ALL) == chapter_fingerprint(
        job.book, "Intro", 1, 3, list(spoken), OutputSettings(subtitles=True)
    )


def _changed_chunk(job: Job, **change: object) -> list[Spoken]:
    first = job.spoken[0]
    if "file" in change or "duration" in change:
        chunk = replace(first.chunk, **change)  # type: ignore[arg-type]
        return [replace(first, chunk=chunk), *job.spoken[1:2]]
    return [replace(first, **change), *job.spoken[1:2]]  # type: ignore[arg-type]


CHANGES = {
    "chunk file": lambda job, s: (job.book, "Intro", 1, 3, _changed_chunk(job, file="x.wav"), s),
    "duration": lambda job, s: (job.book, "Intro", 1, 3, _changed_chunk(job, duration=9.0), s),
    "pause": lambda job, s: (job.book, "Intro", 1, 3, _changed_chunk(job, pause=Pause.NONE), s),
    "join": lambda job, s: (job.book, "Intro", 1, 3, _changed_chunk(job, continues=True), s),
    "text": lambda job, s: (job.book, "Intro", 1, 3, _changed_chunk(job, text="other"), s),
    "title": lambda job, s: (job.book, "Other", 1, 3, job.spoken[:2], s),
    "number": lambda job, s: (job.book, "Intro", 2, 3, job.spoken[:2], s),
    "count": lambda job, s: (job.book, "Intro", 1, 4, job.spoken[:2], s),
    "book title": lambda job, s: (replace(job.book, title="X"), "Intro", 1, 3, job.spoken[:2], s),
    "authors": lambda job, s: (replace(job.book, authors=()), "Intro", 1, 3, job.spoken[:2], s),
    "language": lambda job, s: (replace(job.book, language="de"), "Intro", 1, 3, job.spoken[:2], s),
    "cover": lambda job, s: (replace(job.book, cover=None), "Intro", 1, 3, job.spoken[:2], s),
}


@pytest.mark.parametrize("change", list(CHANGES))
def test_the_fingerprint_changes_with_each_input_that_changes_the_bytes(
    tmp_path: Path, change: str
) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    base = chapter_fingerprint(job.book, "Intro", 1, 3, job.spoken[:2], ALL)
    assert chapter_fingerprint(*CHANGES[change](job, ALL)) != base


SETTINGS = {
    "chapter_pause": 3.0,
    "heading_pause": 2.0,
    "paragraph_pause": 1.0,
    "pause_edit": 1.5,
    "clause_pause": 0.5,
    "sentence_pause": 0.4,
    "mp3": False,
    "m4b": False,
    "mp3_bitrate": "96k",
    "aac_bitrate": "96k",
    "subtitles": False,
}


def test_every_setting_is_tried_below() -> None:
    assert set(SETTINGS) == {f.name for f in fields(OutputSettings)}


@pytest.mark.parametrize(("name", "value"), list(SETTINGS.items()))
def test_the_fingerprint_changes_with_each_output_setting(
    tmp_path: Path, name: str, value: object
) -> None:
    job = make_job(tmp_path / "job")
    base = chapter_fingerprint(job.book, "Intro", 1, 3, job.spoken[:2], ALL)
    changed = replace(ALL, **{name: value})
    assert chapter_fingerprint(job.book, "Intro", 1, 3, job.spoken[:2], changed) != base


def test_the_fingerprint_changes_with_the_cover_image_bytes(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    base = chapter_fingerprint(job.book, "Intro", 1, 3, job.spoken[:2], ALL)
    assert job.book.cover is not None
    job.book.cover.write_bytes(job.book.cover.read_bytes() + b"\x00")
    assert chapter_fingerprint(job.book, "Intro", 1, 3, job.spoken[:2], ALL) != base


def test_book_writer_fingerprint_is_chapter_fingerprint(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    writer = BookWriter(job.folder, tmp_path / "out", job.book, ["A", "B", "C"], ALL)
    assert writer.fingerprint(2, job.spoken[2:3]) == chapter_fingerprint(
        job.book, "B", 2, 3, job.spoken[2:3], ALL
    )


@settings(max_examples=40, deadline=None)
@given(
    frames=st.lists(
        st.lists(st.integers(min_value=0, max_value=5000), min_size=1, max_size=4),
        min_size=1,
        max_size=5,
    ),
    pauses=st.lists(st.sampled_from(list(Pause)), min_size=1, max_size=6),
    chapter_pause=st.floats(min_value=0, max_value=3),
)
def test_chapter_times_on_their_own_add_up_to_the_book_timeline(
    frames: list[list[int]], pauses: list[Pause], chapter_pause: float
) -> None:
    """Placing the chapters so far gives every earlier chapter the samples it has on the
    whole book's timeline: adding a chapter never moves one already written."""
    chapters, spoken, lengths = [], [], []
    for c, chunk_frames in enumerate(frames):
        chapters.append(Chapter(f"C{c}", len(spoken)))
        for n in chunk_frames:
            i = len(spoken)
            spoken.append(
                Spoken(AudioChunk(Span(i, 0, 1), f"{i}.wav", n / 24000), pauses[i % len(pauses)])
            )
            lengths.append(n)
    out = OutputSettings(chapter_pause=chapter_pause)
    book = plan_timeline(chapters, spoken, lengths, 24000, out)
    for count in range(1, len(chapters) + 1):
        stop = chapters[count].first if count < len(chapters) else len(spoken)
        part = plan_timeline(chapters[:count], spoken[:stop], lengths[:stop], 24000, out)
        assert part.chunks == book.chunks[:stop]
        assert part.chapters == book.chapters[:count]


def test_write_book_writes_the_m4b_and_its_subtitles_as_write_audiobook_does(
    tmp_path: Path,
) -> None:
    """`finish` on chapters written by an earlier run: only the book's files are made."""
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    whole = written_whole(job, tmp_path / "whole")
    out = tmp_path / "out"
    by_chapter(job, out, OutputSettings(m4b=False, subtitles=True))
    counting = Failing(at=-1)
    writer = BookWriter(
        job.folder,
        out,
        job.book,
        [c.title for c in job.chapters],
        ALL,
        ffmpeg=counting,
        keep=list(out.iterdir()),
    )
    for number, (first, stop) in enumerate(ranges(job), start=1):
        writer.add(number, job.spoken[first:stop], written=True)
    written = writer.finish()
    assert counting.calls == [1]  # the M4B only
    assert written.m4b is not None
    assert [p.name for p in written.subtitles][-2:] == [
        "A Study of Tones.srt",
        "A Study of Tones.vtt",
    ]
    assert hashes(out) == whole


def test_partial_files_of_a_killed_run_are_cleared(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    out.mkdir()
    left = out / ".A Study of Tones - 02 Methods; data = 1 # 2.mp3.partial"
    left.write_bytes(b"half an mp3")
    BookWriter(job.folder, out, job.book, [c.title for c in job.chapters])
    assert not left.exists()


def test_an_old_read_along_file_is_removed_before_any_chapter_is_written(tmp_path: Path) -> None:
    """It vouches for the files it names: it must not name files this run may replace."""
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    by_chapter(job, out).finish()
    old = out / "A Study of Tones.readalong.json"
    BookWriter(job.folder, out, job.book, [c.title for c in job.chapters], overwrite=True)
    assert not old.exists()


def test_given_numbers_name_and_tag_the_chapters(tmp_path: Path) -> None:
    """Chapters are numbered by their place in the book, not among those chosen (#726,
    D-903): the second chapter written here is the book's third of thirteen."""
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    (a, b), _, (e, f) = ranges(job)
    titles = ["Introduction", "Results"]
    writer = BookWriter(job.folder, out, job.book, titles, ALL, numbers=[1, 3], count=13)
    writer.add(1, job.spoken[a:b])
    writer.add(2, job.spoken[e:f])
    written = writer.finish()
    assert [p.name for p in written.mp3s] == [
        "A Study of Tones - 01 Introduction.mp3",
        "A Study of Tones - 03 Results.mp3",
    ]
    assert [tags_of(ffmetadata(p))["track"] for p in written.mp3s] == ["1/13", "3/13"]
    assert writer.fingerprint(2, job.spoken[e:f]) == chapter_fingerprint(
        job.book, "Results", 3, 13, job.spoken[e:f], ALL
    )
    assert audiobook_targets(out, job.book.title, titles, ALL, [1, 3], 13) == writer.targets
    wide = audiobook_targets(out, job.book.title, titles, ALL, [1, 3], 100)
    assert wide.mp3s[1].name == "A Study of Tones - 003 Results.mp3"


def test_numbers_must_fit_the_chapters_and_the_count(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "out"
    for numbers, count, message in (
        ([1], 3, "one number per chapter"),
        ([2, 1], 3, "increasing"),
        ([1, 1], 3, "increasing"),
        ([0, 2], 3, "from 1 to 3"),
        ([1, 4], 3, "from 1 to 3"),
    ):
        with pytest.raises(ValueError, match=message):
            BookWriter(job.folder, out, job.book, ["A", "B"], numbers=numbers, count=count)


def test_numbers_left_out_keep_every_file_as_before(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    titles = [c.title for c in job.chapters]
    by_chapter(job, tmp_path / "default").finish()
    writer = BookWriter(job.folder, tmp_path / "given", job.book, titles, ALL, numbers=[1, 2, 3])
    for number, (first, stop) in enumerate(ranges(job), start=1):
        writer.add(number, job.spoken[first:stop])
    writer.finish()
    assert hashes(tmp_path / "given") == hashes(tmp_path / "default")
    assert audiobook_targets(tmp_path, "T", titles, ALL) == audiobook_targets(
        tmp_path, "T", titles, ALL, [1, 2, 3], 3
    )


BOOK_CHAPTERS = 3  # make_job's book


@settings(max_examples=8, deadline=None)
@given(
    first=st.sets(st.integers(min_value=1, max_value=BOOK_CHAPTERS), min_size=1),
    later=st.sets(st.integers(min_value=1, max_value=BOOK_CHAPTERS), min_size=1),
)
def test_a_chapter_added_between_two_others_leaves_their_files_unchanged(
    tmp_path_factory: pytest.TempPathFactory, first: set[int], later: set[int]
) -> None:
    """A book written for some chapters, then for those and more (any set, any chapters
    added before, between or after): every chapter written first keeps its file's name
    and bytes, and its subtitles, so a file already copied to a phone stays the same."""
    tmp = tmp_path_factory.mktemp("added")
    job = make_job(tmp / "job")
    spans = ranges(job)

    def write(numbers: list[int], out: Path) -> dict[str, str]:
        titles = [job.chapters[n - 1].title for n in numbers]
        writer = BookWriter(
            job.folder, out, job.book, titles, ALL, numbers=numbers, count=BOOK_CHAPTERS
        )
        for place, number in enumerate(numbers, start=1):
            start, stop = spans[number - 1]
            writer.add(place, job.spoken[start:stop])
        written = writer.finish()
        mine = {*written.mp3s, *written.subtitles[: 2 * len(numbers)]}
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in mine}

    before = write(sorted(first), tmp / "before")
    after = write(sorted(first | later), tmp / "after")
    assert {name: after.get(name) for name in before} == before
