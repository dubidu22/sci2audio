"""The whole book as one file, built on request from the chapters already spoken (#725,
LW-03): an M4B byte for byte the one `BookWriter.finish` writes, or one MP3 with ID3 chapter
marks (`CHAP`/`CTOC`) carrying the chapter files' tags and cover."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest
from output_helpers import (
    NEWER,
    RATE,
    Job,
    chapters_of,
    decoded_samples,
    ffmetadata,
    make_job,
    refuse_newer_names,
    streams,
    tags_of,
)
from test_output_chapters import ALL, REAL, Failing, by_chapter, cover_file, hashes, ranges

from sci2audio import __version__
from sci2audio.output import (
    BookChapter,
    BookInfo,
    BookKind,
    OutputSettings,
    book_file_name,
    book_subtitles,
    write_audiobook,
    write_book_file,
)
from sci2audio.output.write import _partial

MP3_FRAME = 576  # samples in one MPEG-2 layer III frame (24 kHz)
OUR_TAGS = ("title", "album", "artist", "genre", "comment", "track", "language")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def book_chapters(job: Job, numbers: tuple[int, ...] | None = None) -> list[BookChapter]:
    """The job's chapters (or those of the given numbers), as the app hands them over."""
    chosen = []
    for number, (chapter, (first, stop)) in enumerate(
        zip(job.chapters, ranges(job), strict=True), start=1
    ):
        if numbers is None or number in numbers:
            chosen.append(BookChapter(number, chapter.title, tuple(job.spoken[first:stop])))
    return chosen


@dataclass(frozen=True)
class Id3Chapter:
    element: str
    start_ms: int
    end_ms: int
    title: str


def id3_chapters(path: Path) -> tuple[list[Id3Chapter], list[str]]:
    """The `CHAP` frames of an ID3v2.3 tag and the children its top `CTOC` lists, read from
    the bytes (ffmpeg's reader moves chapter times by the encoder delay it skips)."""
    data = path.read_bytes()
    assert data[:3] == b"ID3"
    assert data[3] == 3, "an ID3v2.3 tag"
    size = 0
    for byte in data[6:10]:
        size = (size << 7) | byte
    tag, at = data[10 : 10 + size], 0
    chapters: list[Id3Chapter] = []
    toc: list[str] = []
    while at + 10 <= len(tag) and tag[at : at + 4].strip(b"\0"):
        frame = tag[at : at + 4].decode("ascii")
        length = struct.unpack(">I", tag[at + 4 : at + 8])[0]
        body = tag[at + 10 : at + 10 + length]
        at += 10 + length
        if frame == "CHAP":
            element, rest = body.split(b"\0", 1)
            start, end = struct.unpack(">II", rest[:8])
            chapters.append(Id3Chapter(element.decode(), start, end, _title(rest[16:])))
        elif frame == "CTOC":
            element, rest = body.split(b"\0", 1)
            flags, count = rest[0], rest[1]
            assert flags & 0b11 == 0b11, "the top-level, ordered table of contents"
            children = rest[2:].split(b"\0")[:count]
            toc = [child.decode() for child in children]
    return chapters, toc


def _title(frames: bytes) -> str:
    """The text of the `TIT2` sub-frame of a `CHAP` frame."""
    at = 0
    while at + 10 <= len(frames):
        frame = frames[at : at + 4]
        length = struct.unpack(">I", frames[at + 4 : at + 8])[0]
        body = frames[at + 10 : at + 10 + length]
        at += 10 + length
        if frame == b"TIT2":
            encoding, text = body[0], body[1:]
            codec = "utf-16" if encoding == 1 else "latin-1"
            return text.decode(codec).rstrip("\0")
    return ""


def our_tags(path: Path) -> dict[str, str]:
    tags = tags_of(ffmetadata(path))
    return {key: tags[key] for key in OUR_TAGS if key in tags}


def has_cover(path: Path) -> bool:
    return any("Video" in line and "attached pic" in line for line in streams(path))


def test_finish_writes_the_m4b_it_wrote_before_the_book_file_split(tmp_path: Path) -> None:
    """Characterisation: `finish`'s M4B and the book's subtitles are the files
    `write_audiobook` writes, so moving the M4B into `write_book_file` is held to them."""
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    write_audiobook(job.folder, tmp_path / "whole", job.chapters, job.spoken, job.book, ALL)
    whole = hashes(tmp_path / "whole")
    written = by_chapter(job, tmp_path / "parts", ALL).finish()
    assert written.m4b is not None
    for name in ("A Study of Tones.m4b", "A Study of Tones.srt", "A Study of Tones.vtt"):
        assert sha(tmp_path / "parts" / name) == whole[name]


@pytest.mark.parametrize("settings", [ALL, OutputSettings()], ids=["subtitles", "default"])
def test_the_book_m4b_is_byte_identical_to_the_one_finish_writes(
    tmp_path: Path, settings: OutputSettings
) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    written = by_chapter(job, tmp_path / "job-output", settings).finish()
    assert written.m4b is not None
    out = tmp_path / "built"
    target = book_file_name(out, job.book.title, BookKind.M4B)
    assert target.name == written.m4b.name
    made = write_book_file(job.folder, target, book_chapters(job), job.book, settings)
    assert made == target
    assert sha(target) == sha(written.m4b)
    if settings.subtitles:
        for path in book_subtitles(target):
            assert sha(path) == sha(tmp_path / "job-output" / path.name)
        assert sorted(p.name for p in out.iterdir()) == sorted(
            [target.name, *(p.name for p in book_subtitles(target))]
        )
    else:
        assert [p.name for p in out.iterdir()] == [target.name]


def test_the_book_mp3_has_a_chapter_mark_at_each_chapter_start(tmp_path: Path) -> None:
    """The bundled ffmpeg writes ID3 `CHAP` and `CTOC` frames from the chapters it is
    given, on every system CI runs (#725: settled by the `ci:full` run)."""
    job = make_job(tmp_path / "job")
    written = by_chapter(job, tmp_path / "job-output", OutputSettings()).finish()
    assert written.m4b is not None
    m4b_marks = chapters_of(ffmetadata(written.m4b))
    target = book_file_name(tmp_path / "built", job.book.title, BookKind.MP3)
    write_book_file(
        job.folder, target, book_chapters(job), job.book, OutputSettings(), BookKind.MP3
    )
    assert target.name == "A Study of Tones.mp3"
    marks, toc = id3_chapters(target)
    assert [m.title for m in marks] == [title for _, _, title in m4b_marks]
    assert toc == [m.element for m in marks]
    for mark, (start, end, _) in zip(marks, m4b_marks, strict=True):
        assert abs(mark.start_ms * RATE / 1000 - start) <= MP3_FRAME
        assert abs(mark.end_ms * RATE / 1000 - end) <= MP3_FRAME
    assert abs(decoded_samples(target) - decoded_samples(written.m4b)) <= 2 * MP3_FRAME


def test_the_book_files_carry_the_tags_and_cover_of_the_chapter_files(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    written = by_chapter(job, tmp_path / "job-output", OutputSettings()).finish()
    assert written.m4b is not None
    out = tmp_path / "built"
    mp3 = write_book_file(
        job.folder,
        book_file_name(out, job.book.title, BookKind.MP3),
        book_chapters(job),
        job.book,
        OutputSettings(),
        BookKind.MP3,
    )
    chapter_tags = our_tags(written.mp3s[0])
    chapter_tags.pop("track")
    assert our_tags(mp3) == {**chapter_tags, "title": job.book.title}
    m4b_tags = our_tags(written.m4b)
    assert {k: m4b_tags[k] for k in ("title", "album", "artist", "genre", "comment")} == {
        k: our_tags(mp3)[k] for k in ("title", "album", "artist", "genre", "comment")
    }
    assert has_cover(mp3)
    assert has_cover(written.mp3s[0])
    assert has_cover(written.m4b)


def test_the_chapter_marks_and_tags_of_the_book_files(tmp_path: Path, snapshot) -> None:  # type: ignore[no-untyped-def]
    job = make_job(tmp_path / "job")
    out = tmp_path / "built"
    files = {}
    for kind in BookKind:
        files[kind] = write_book_file(
            job.folder,
            book_file_name(out, job.book.title, kind),
            book_chapters(job),
            job.book,
            OutputSettings(),
            kind,
        )

    def tags(path: Path) -> dict[str, str]:
        return {k: v.replace(__version__, "<version>") for k, v in our_tags(path).items()}

    m4b, mp3 = files[BookKind.M4B], files[BookKind.MP3]
    marks, toc = id3_chapters(mp3)
    assert {
        "m4b": {
            "chapters": [
                (round(s * 1000 / RATE), round(e * 1000 / RATE), t)
                for s, e, t in chapters_of(ffmetadata(m4b))
            ],
            "tags": tags(m4b),
        },
        "mp3": {
            "chapters": [(m.start_ms, m.end_ms, m.title) for m in marks],
            "toc": toc,
            "tags": tags(mp3),
        },
    } == snapshot


def test_a_failing_book_build_leaves_no_partial(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "built"
    for kind in BookKind:
        target = book_file_name(out, job.book.title, kind)
        with pytest.raises(OSError, match="No space"):
            write_book_file(
                job.folder, target, book_chapters(job), job.book, ALL, kind, ffmpeg=Failing(0)
            )
        assert not target.exists()
        assert not _partial(target).exists()
    assert list(out.iterdir()) == []


def test_a_book_file_is_replaced_only_when_asked(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    target = book_file_name(tmp_path / "built", job.book.title, BookKind.MP3)
    target.parent.mkdir()
    target.write_bytes(b"not ours")
    with pytest.raises(FileExistsError):
        write_book_file(job.folder, target, book_chapters(job), job.book, kind=BookKind.MP3)
    assert target.read_bytes() == b"not ours"
    heard: list[tuple[str, int, str]] = []
    write_book_file(
        job.folder,
        target,
        book_chapters(job),
        job.book,
        kind=BookKind.MP3,
        replace=True,
        vouch=lambda path, size, digest: heard.append((path.name, size, digest)),
    )
    assert heard == [(target.name, target.stat().st_size, sha(target))]


def test_chapters_of_a_book_file_come_in_order(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    target = book_file_name(tmp_path / "built", job.book.title, BookKind.M4B)
    chapters = book_chapters(job)
    with pytest.raises(ValueError, match="comes after"):
        write_book_file(job.folder, target, [chapters[1], chapters[0]], job.book, ffmpeg=REAL)
    with pytest.raises(ValueError, match="no chapter"):
        write_book_file(job.folder, target, [], job.book, ffmpeg=REAL)
    assert not target.parent.exists() or list(target.parent.iterdir()) == []


def test_a_partial_book_is_named_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    job = make_job(tmp_path / "job")
    out = tmp_path / "built"
    out.mkdir()
    names = {
        kind: book_file_name(out, job.book.title, kind, partial=True).name for kind in BookKind
    }
    assert names == {
        BookKind.M4B: "A Study of Tones (partial).m4b",
        BookKind.MP3: "A Study of Tones (partial).mp3",
    }
    target = book_file_name(out, job.book.title, BookKind.M4B, partial=True)
    write_book_file(job.folder, target, book_chapters(job, (1, 3)), job.book, ALL)
    assert sorted(p.name for p in out.iterdir()) == [
        "A Study of Tones (partial).m4b",
        "A Study of Tones (partial).srt",
        "A Study of Tones (partial).vtt",
    ]
    assert [t for _, _, t in chapters_of(ffmetadata(target))] == ["Introduction", "Results"]
    refuse_newer_names(monkeypatch)
    book = f"Tones {NEWER} Book"
    assert book_file_name(out, book, BookKind.MP3, partial=True).name == (
        "Tones Book (partial).mp3"
    )
    assert book_file_name(out, "Tones", BookKind.MP3).name == "Tones.mp3"


def test_the_book_mp3_name_never_meets_a_chapter_file(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    written = by_chapter(job, tmp_path / "out", OutputSettings()).finish()
    book = book_file_name(tmp_path / "out", job.book.title, BookKind.MP3)
    assert book.name not in {p.name for p in written.mp3s}
    assert not book.exists()


def test_a_book_info_without_cover_or_authors_still_builds(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job")
    bare = BookInfo("Bare", (), "xx", None)
    for kind in BookKind:
        target = book_file_name(tmp_path / "built", bare.title, kind)
        write_book_file(job.folder, target, book_chapters(job), bare, OutputSettings(), kind)
        assert not has_cover(target)
        assert "artist" not in our_tags(target)
