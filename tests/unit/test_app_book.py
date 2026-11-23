"""The whole audiobook built on request (#725, LW-03): one M4B or MP3 from the chapters
made, equal to the M4B a job writes, built only from the chunk cache, reused while its
chapters are the same, and never replacing a file that is not the project's."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import (
    BookProgress,
    JobCancelledError,
    JobSettings,
    MissingChaptersError,
    OutputExistsError,
    build_book,
    run_audio_job,
)
from sci2audio.app import audio as audio_module
from sci2audio.app import book as book_module
from sci2audio.app.playable import read_record, read_spoken
from sci2audio.output import BookKind, OutputSettings

TITLES = ("Alpha", "Beta", "Gamma")
BOOK = "\n\n".join(f"# {t}\n\nThe chapter {t} starts here. It ends with {t}." for t in TITLES)


def run(folder: Path, voice: FakeVoice, chapters: tuple[int, ...] = (0, 1, 2), **kwargs):  # type: ignore[no-untyped-def]
    path = folder / "in" / "book.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(BOOK, encoding="utf-8", newline="\n")
    settings = JobSettings(chapters=chapters, output_folder=folder / "out")
    return run_audio_job(path, settings, folder / "work", voice=voice.source(), **kwargs)


def build(folder: Path, kind: BookKind = BookKind.M4B, **kwargs):  # type: ignore[no-untyped-def]
    return build_book(folder / "work", folder / "out", kind, **kwargs)


def test_the_built_m4b_equals_the_m4b_of_a_job_for_the_same_chapters(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    built = build(tmp_path)
    assert built.path == tmp_path / "out" / "book.m4b"
    assert not built.reused
    assert not built.partial
    assert built.chapters == (0, 1, 2)
    job = run(tmp_path / "job", FakeVoice(), output_settings=OutputSettings())
    assert job.written.m4b is not None
    assert built.path.read_bytes() == job.written.m4b.read_bytes()


def test_the_built_mp3_holds_every_chapter(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    built = build(tmp_path, BookKind.MP3)
    assert built.path == tmp_path / "out" / "book.mp3"
    assert built.path.stat().st_size > 0
    record = read_record(tmp_path / "work")
    assert record is not None
    (entry,) = record.built
    assert entry.kind == "mp3"
    assert entry.chapters == tuple(c.fingerprint for c in record.chapters)
    assert entry.file.matches(tmp_path / "out")


def test_a_second_build_reuses_the_file(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    first = build(tmp_path)
    stamp = first.path.stat().st_mtime_ns
    second = build(tmp_path)
    assert second.reused
    assert second.path == first.path
    assert second.path.stat().st_mtime_ns == stamp


def test_the_file_is_built_again_after_chapters_are_added(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    first = build(tmp_path)
    before = first.path.read_bytes()
    run(tmp_path, FakeVoice(), (2,))
    second = build(tmp_path)
    assert not second.reused
    assert second.path == first.path  # the project's own file is replaced
    assert second.chapters == (0, 2)
    assert second.path.read_bytes() != before
    job = run(tmp_path / "job", FakeVoice(), (0, 2), output_settings=OutputSettings())
    assert job.written.m4b is not None
    assert second.path.read_bytes() == job.written.m4b.read_bytes()


def stopped_in_gamma(folder: Path) -> None:
    def stop(text: str) -> bool:
        if "Gamma" in text:
            raise KeyboardInterrupt
        return False

    with pytest.raises(KeyboardInterrupt):
        run(folder, FakeVoice(fail_on=stop))


def test_only_generated_chapters_go_in_and_the_missing_are_named(tmp_path: Path) -> None:
    stopped_in_gamma(tmp_path)
    with pytest.raises(MissingChaptersError) as raised:
        build(tmp_path)
    assert raised.value.missing == (2,)
    assert raised.value.unavailable == ()
    assert "1 of the chosen chapters are not made yet" in str(raised.value)
    assert not list((tmp_path / "out").glob("*.m4b"))
    built = build(tmp_path, partial_ok=True)
    assert built.partial
    assert built.path.name == "book (partial).m4b"
    assert built.chapters == (0, 1)
    assert built.missing == (2,)
    job = run(tmp_path / "job", FakeVoice(), (0, 1), output_settings=OutputSettings())
    assert job.written.m4b is not None
    assert built.path.read_bytes() == job.written.m4b.read_bytes()


def test_nothing_is_spoken_to_build_the_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run(tmp_path, FakeVoice())
    cache = sorted((tmp_path / "work" / "chunks").rglob("*.wav"))

    def refused(*args: object, **kwargs: object) -> None:
        raise AssertionError("the build ran the text steps or the voice")

    monkeypatch.setattr(audio_module, "prepare_script", refused)
    monkeypatch.setattr(audio_module, "speak_to_wav", refused)
    monkeypatch.setattr(audio_module, "read_document", refused)
    built = build(tmp_path)
    assert built.path.is_file()
    assert sorted((tmp_path / "work" / "chunks").rglob("*.wav")) == cache


def test_a_chapter_whose_cache_was_cleaned_is_named_not_available(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    record = read_record(tmp_path / "work")
    assert record is not None
    beta = record.chapters[1]
    spoken = read_spoken(tmp_path / "work", beta.index, beta.spoken)
    assert spoken is not None
    (tmp_path / "work" / spoken[-1].chunk.file).unlink()
    with pytest.raises(MissingChaptersError, match="no longer in the working folder") as raised:
        build(tmp_path)
    assert raised.value.unavailable == (1,)
    assert raised.value.missing == ()
    built = build(tmp_path, partial_ok=True)
    assert built.chapters == (0, 2)
    assert built.unavailable == (1,)
    assert built.path.name == "book (partial).m4b"


def test_a_file_of_that_name_not_from_this_project_is_refused(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    theirs = tmp_path / "out" / "book.m4b"
    theirs.write_bytes(b"someone else's audiobook")
    with pytest.raises(OutputExistsError, match="not made from this project"):
        build(tmp_path)
    assert theirs.read_bytes() == b"someone else's audiobook"
    assert not list((tmp_path / "out").glob(".*.partial"))


def test_the_build_reports_progress_and_stops_on_cancel(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    events: list[BookProgress] = []
    build(tmp_path, progress=events.append)
    fractions = [e.fraction for e in events]
    assert len(fractions) > 2
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0
    assert all(0 <= f <= 1 for f in fractions)

    other = tmp_path / "cancelled"
    run(other, FakeVoice())
    cancel = threading.Event()

    def stop(event: BookProgress) -> None:
        cancel.set()

    with pytest.raises(JobCancelledError):
        build(other, progress=stop, cancel=cancel)
    assert sorted(p.name for p in (other / "out").iterdir() if "m4b" in p.name) == []
    record = read_record(other / "work")
    assert record is not None
    assert record.built == ()
    cancel.clear()
    assert build(other, cancel=cancel).path.is_file()  # and it builds again afterwards


def test_a_cancel_before_the_build_writes_nothing(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(JobCancelledError):
        build(tmp_path, cancel=cancel)
    assert not list((tmp_path / "out").glob("*.m4b"))


def test_a_project_with_no_chapter_made_says_so(tmp_path: Path) -> None:
    (tmp_path / "work").mkdir()
    with pytest.raises(book_module.JobError, match="no chapter"):
        build(tmp_path)
