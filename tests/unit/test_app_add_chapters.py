"""Chapters made later (#726, LW-04): a job choosing more chapters than the project has
made adds only the new ones, keeps every file made before byte for byte, plays the book
in printed order, and never mixes settings silently."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from test_app_audio_faults import FailingFfmpeg

from sci2audio.app import (
    AudioProgress,
    JobError,
    JobSettings,
    OutputExistsError,
    Phase,
    SettingsChangedError,
    job,
    kept_settings,
    run_audio_job,
)
from sci2audio.app.playable import RECORD, read_record, write_record
from sci2audio.core import Content, Document
from sci2audio.layout import LayoutSettings, build_document
from sci2audio.output import find_ffmpeg, read_readalong

UNIT = Path(__file__).resolve().parent
TITLES = ("Alpha", "Beta", "Gamma")
BOOK = "\n\n".join(f"# {t}\n\nThe chapter {t} starts here. It ends with {t}." for t in TITLES)


def source(folder: Path) -> Path:
    path = folder / "in" / "book.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(BOOK, encoding="utf-8", newline="\n")
    return path


def run(folder: Path, voice: FakeVoice, chapters: tuple[int, ...], **kwargs):  # type: ignore[no-untyped-def]
    settings = JobSettings(
        chapters=chapters, output_folder=folder / "out", **kwargs.pop("settings", {})
    )
    return run_audio_job(source(folder), settings, folder / "work", voice=voice.source(), **kwargs)


def mp3s(folder: Path) -> list[str]:
    return sorted(p.name for p in (folder / "out").glob("*.mp3"))


def files(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((folder / "out").iterdir())}


def tree(folder: Path) -> dict[str, bytes]:
    """Every file under `folder`, by its path inside it."""
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def test_adding_a_chapter_speaks_only_it(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    voice = FakeVoice()
    job = run(tmp_path, voice, (2,))
    assert voice.texts
    assert all("Gamma" in text for text in voice.texts)
    # numbered by its place in the book (D-903): the third chapter, not the second made
    assert mp3s(tmp_path) == ["book - 01 Alpha.mp3", "book - 03 Gamma.mp3"]
    assert [p.name for p in job.written.mp3s] == mp3s(tmp_path)
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.complete
    assert [(c.index, c.number) for c in record.chapters] == [(0, 1), (2, 3)]


def test_generated_chapter_files_stay_byte_identical_when_others_are_added(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice(), (1,))
    (made,) = mp3s(tmp_path)
    before = (tmp_path / "out" / made).read_bytes()
    stamp = (tmp_path / "out" / made).stat().st_mtime_ns
    run(tmp_path, FakeVoice(), (0, 2))
    assert (tmp_path / "out" / made).read_bytes() == before
    assert (tmp_path / "out" / made).stat().st_mtime_ns == stamp  # not written again
    # and every file is the one a job making all three at once writes
    whole = tmp_path / "whole"
    run(whole, FakeVoice(), (0, 1, 2))
    assert files(tmp_path) == files(whole)


def test_chapters_play_in_document_order_whatever_order_they_were_made(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice(), (2,))
    run(tmp_path, FakeVoice(), (0,))
    job = run(tmp_path, FakeVoice(), (1,))
    times = read_readalong(job.written.readalong)
    assert [c.title for c in times.chapters] == list(TITLES)
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.planned == (0, 1, 2)
    assert [c.index for c in record.chapters] == [0, 1, 2]


def test_other_settings_are_refused_before_any_speech_and_name_the_choice(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice(), (0,))
    before = files(tmp_path)
    voice = FakeVoice()
    with pytest.raises(SettingsChangedError) as raised:
        run(tmp_path, voice, (1,), settings={"speed": 1.2})
    assert voice.made == 0
    assert voice.spoken == []
    assert raised.value.changes == ["settings speed: 1.0, now 1.2"]
    assert raised.value.old["settings"]["speed"] == 1.0
    assert raised.value.new["settings"]["speed"] == 1.2
    assert "keep the settings they were made with" in str(raised.value)
    assert "replace them" in str(raised.value)
    assert isinstance(raised.value, OutputExistsError)  # the CLI's exit 7
    assert files(tmp_path) == before


def test_keep_settings_makes_the_new_chapters_with_the_old_settings(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,), settings={"speed": 1.2, "voice": "bm_george"})
    voice = FakeVoice()
    run(tmp_path, voice, (1,), keep_settings=True)
    assert voice.texts
    assert all("Beta" in text for text in voice.texts)
    assert {(v, s) for _, v, s in voice.spoken} == {("bm_george", 1.2)}
    whole = tmp_path / "whole"
    run(whole, FakeVoice(), (0, 1), settings={"speed": 1.2, "voice": "bm_george"})
    assert files(tmp_path) == files(whole)


@pytest.mark.parametrize("given", ["", "en"], ids=["auto", "en"])
def test_keep_settings_lays_the_document_out_with_the_kept_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: str
) -> None:
    """The layout follows the language (#767): a job that keeps the settings reads the
    document again when the kept language is not the one it was given."""
    run(tmp_path, FakeVoice(), (0,), settings={"language": "de"})
    laid_out: list[tuple[str, str]] = []  # the language asked for, the document's own

    def record(content: Content, settings: LayoutSettings) -> Document:
        document = build_document(content, settings)
        laid_out.append((settings.language, document.language))
        return document

    monkeypatch.setattr(job, "build_document", record)
    voice = FakeVoice()
    run(tmp_path, voice, (1,), settings={"language": given}, keep_settings=True)
    assert laid_out[-1] == ("de", "de")  # the document in use was laid out as kept
    assert len(laid_out) == 2  # read as given, then again as kept
    assert voice.texts
    assert all("Beta" in text for text in voice.texts)


def test_keep_settings_reads_the_document_once_when_the_language_is_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run(tmp_path, FakeVoice(), (0,), settings={"language": "de"})
    asked: list[str] = []

    def record(content: Content, settings: LayoutSettings) -> Document:
        asked.append(settings.language)
        return build_document(content, settings)

    monkeypatch.setattr(job, "build_document", record)
    run(tmp_path, FakeVoice(), (1,), settings={"language": "de"}, keep_settings=True)
    assert asked == ["de"]


def test_keep_settings_on_a_new_project_uses_the_settings_given(tmp_path: Path) -> None:
    voice = FakeVoice()
    run(tmp_path, voice, (0,), settings={"speed": 1.2}, keep_settings=True)
    assert {s for _, _, s in voice.spoken} == {1.2}


def test_overwrite_regenerates_every_chapter(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    voice = FakeVoice()
    run(tmp_path, voice, (0, 1), settings={"speed": 1.2}, overwrite=True)
    assert {s for _, _, s in voice.spoken} == {1.2}
    assert any("Alpha" in text for text in voice.texts)
    assert any("Beta" in text for text in voice.texts)
    whole = tmp_path / "whole"
    run(whole, FakeVoice(), (0, 1), settings={"speed": 1.2})
    assert files(tmp_path) == files(whole)


def test_a_finished_audiobook_with_nothing_new_is_still_refused(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0, 1))
    voice = FakeVoice()
    for chosen in [(0, 1), (0,)]:
        with pytest.raises(OutputExistsError, match="exist already"):
            run(tmp_path, voice, chosen)
    assert voice.made == 0


def test_a_custom_order_project_is_not_extended(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (2, 0))  # another order than printed (#119)
    before = files(tmp_path)
    assert mp3s(tmp_path) == ["book - 01 Gamma.mp3", "book - 02 Alpha.mp3"]
    voice = FakeVoice()
    with pytest.raises(OutputExistsError, match="printed order"):
        run(tmp_path, voice, (1,))
    with pytest.raises(OutputExistsError, match="printed order"):
        run(tmp_path, voice, (2, 0, 1))
    assert voice.made == 0
    assert files(tmp_path) == before
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.order == "chosen"
    # a book-order project is not mixed with a custom order either
    other = tmp_path / "other"
    run(other, FakeVoice(), (0,))
    with pytest.raises(OutputExistsError, match="printed order"):
        run(other, voice, (2, 0))


def as_version_1(work: Path) -> None:
    """The working folder's chapter record as #723 (version 1) wrote it."""
    path = work / RECORD
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("order", "made", "built"):
        del data[key]
    for chapter in data["chapters"]:
        del chapter["spoken"]
    data["version"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")


def test_a_version_1_record_reads_and_asks_for_a_choice(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    as_version_1(tmp_path / "work")
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.version == 1
    assert record.made is None
    assert [c.index for c in record.chapters] == [0]
    voice = FakeVoice()
    for keep in (False, True):
        with pytest.raises(OutputExistsError, match="earlier version") as raised:
            run(tmp_path, voice, (1,), keep_settings=keep)
        assert not isinstance(raised.value, SettingsChangedError)
    assert voice.made == 0
    run(tmp_path, FakeVoice(), (0, 1), overwrite=True)
    assert mp3s(tmp_path) == ["book - 01 Alpha.mp3", "book - 02 Beta.mp3"]


KILLED_WHILE_ADDING = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    from audio_fakes import FakeVoice
    from sci2audio.app import JobSettings, run_audio_job

    folder = Path(sys.argv[2])
    voice = FakeVoice(marker=folder / "hanging", hang_on=lambda text: "Gamma" in text)
    run_audio_job(
        folder / "in" / "book.md",
        JobSettings(chapters=(1, 2), output_folder=folder / "out"),
        folder / "work",
        voice=voice.source(),
    )
    """
)


def test_a_job_killed_while_adding_a_chapter_resumes_and_keeps_the_others(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice(), (0,))
    alpha = (tmp_path / "out" / "book - 01 Alpha.mp3").read_bytes()
    child = subprocess.Popen([sys.executable, "-c", KILLED_WHILE_ADDING, str(UNIT), str(tmp_path)])
    try:
        deadline = time.monotonic() + 120
        while not (tmp_path / "hanging").exists():
            assert child.poll() is None, "the job ended before it was killed"
            assert time.monotonic() < deadline  # clock-bound: the loop's way out only
            time.sleep(0.05)
        child.kill()  # SIGKILL / TerminateProcess: no clean-up runs
        child.wait(timeout=60)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    # Beta was added before the kill; Alpha is as it was
    assert mp3s(tmp_path) == ["book - 01 Alpha.mp3", "book - 02 Beta.mp3"]
    assert (tmp_path / "out" / "book - 01 Alpha.mp3").read_bytes() == alpha
    voice = FakeVoice()
    run(tmp_path, voice, (1, 2))  # the same command again, no overwrite
    assert voice.texts
    assert all("Gamma" in text for text in voice.texts)
    whole = tmp_path / "whole"
    run(whole, FakeVoice(), (0, 1, 2))
    assert files(tmp_path) == files(whole)
    assert not list((tmp_path / "out").glob(".*.partial"))


def test_keep_settings_names_what_keeping_cannot_bring_back(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    voice = FakeVoice(version="fake-2")  # the voice was updated since
    with pytest.raises(OutputExistsError, match="cannot be matched") as raised:
        run(tmp_path, voice, (1,), keep_settings=True)
    assert not isinstance(raised.value, SettingsChangedError)  # no "--keep-settings" hint
    assert "fake-1" in str(raised.value)
    assert "fake-2" in str(raised.value)
    assert voice.made == 0


def test_another_book_in_the_same_working_folder_is_not_added_to(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    other = tmp_path / "in" / "other.md"
    other.write_text("# Delta\n\nThe chapter Delta starts here.", encoding="utf-8")
    settings = JobSettings(output_folder=tmp_path / "out")
    voice = FakeVoice()
    run_audio_job(other, settings, tmp_path / "work", voice=voice.source())
    assert voice.texts
    assert all("Delta" in text for text in voice.texts)
    assert "other - 01 Delta.mp3" in mp3s(tmp_path)


def other_book(folder: Path) -> Path:
    path = folder / "in" / "other.md"
    path.write_text("# Delta\n\nThe chapter Delta starts here.", encoding="utf-8")
    return path


@pytest.mark.parametrize("keep", [False, True], ids=["plain", "keep-settings"])
def test_another_books_version_1_record_neither_refuses_nor_lends_its_settings(
    tmp_path: Path, keep: bool
) -> None:
    run(tmp_path, FakeVoice(), (0,), settings={"speed": 1.2})
    as_version_1(tmp_path / "work")
    alpha = (tmp_path / "out" / "book - 01 Alpha.mp3").read_bytes()
    voice = FakeVoice()
    run_audio_job(
        other_book(tmp_path),
        JobSettings(output_folder=tmp_path / "out"),
        tmp_path / "work",
        voice=voice.source(),
        keep_settings=keep,
    )
    assert voice.texts
    assert all("Delta" in text for text in voice.texts)
    assert {speed for _, _, speed in voice.spoken} == {1.0}
    assert "other - 01 Delta.mp3" in mp3s(tmp_path)
    assert (tmp_path / "out" / "book - 01 Alpha.mp3").read_bytes() == alpha


def test_keep_settings_never_takes_another_books_settings(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,), settings={"speed": 1.2, "voice": "bm_george"})
    voice = FakeVoice()
    run_audio_job(
        other_book(tmp_path),
        JobSettings(output_folder=tmp_path / "out"),
        tmp_path / "work",
        voice=voice.source(),
        keep_settings=True,
    )
    assert voice.spoken
    assert {(v, s) for _, v, s in voice.spoken} == {("af_heart", 1.0)}


def test_the_kept_settings_are_public_and_are_those_the_chapters_were_made_with(
    tmp_path: Path,
) -> None:
    asked = JobSettings(chapters=(1,), output_folder=tmp_path / "elsewhere")
    assert kept_settings(tmp_path / "work", asked) == asked  # no project yet: the job's own
    run(tmp_path, FakeVoice(), (0,), settings={"speed": 1.2, "voice": "bm_george"})
    kept = kept_settings(tmp_path / "work", asked)
    assert (kept.speed, kept.voice) == (1.2, "bm_george")
    assert (kept.chapters, kept.output_folder) == (asked.chapters, asked.output_folder)


def test_kept_settings_of_a_version_1_record_name_what_cannot_be_brought_back(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice(), (0,))
    as_version_1(tmp_path / "work")
    with pytest.raises(OutputExistsError, match="earlier version"):
        kept_settings(tmp_path / "work", JobSettings(chapters=(1,)))


def test_a_record_with_no_chapters_keeps_nothing_even_when_it_holds_settings(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice(), (0,), settings={"speed": 1.2})
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.made is not None
    write_record(tmp_path / "work", replace(record, chapters=()))
    asked = JobSettings(speed=0.9, chapters=(1,), output_folder=tmp_path / "elsewhere")
    assert kept_settings(tmp_path / "work", asked) == asked


def test_adding_chapters_reports_an_unknown_chapter_as_a_fresh_run_does(tmp_path: Path) -> None:
    fresh = run(tmp_path / "fresh", FakeVoice(), (2, 9))
    assert fresh.result.ignored_chapters == (9,)
    run(tmp_path / "plain", FakeVoice(), (0,))
    run(tmp_path / "plain", FakeVoice(), (2,))
    run(tmp_path, FakeVoice(), (0,))
    added = run(tmp_path, FakeVoice(), (2, 9))
    assert added.result.ignored_chapters == (9,)
    # the unknown number changes nothing else: the same files as without it, and the same
    # work folder, the chapter record included (#830)
    assert files(tmp_path) == files(tmp_path / "plain")
    assert tree(tmp_path / "work") == tree(tmp_path / "plain" / "work")


def while_beta_is_spoken(
    folder: Path, chapters: tuple[int, ...], **kwargs: Any
) -> tuple[list[tuple[tuple[int, ...], list[str]]], list[AudioProgress]]:
    """Run the job and note, before each of Beta's chunks is spoken, the chapters the
    record on disk lists and the MP3s its read-along file names; and the job's events from
    the first of its audio stage on."""
    seen: list[tuple[tuple[int, ...], list[str]]] = []
    events: list[AudioProgress] = []

    def watch(text: str) -> bool:
        if "Beta" in text:
            record = read_record(folder / "work")
            assert record is not None
            readalong = next((folder / "out").glob("*.readalong.json"), None)
            named = [c.mp3 for c in read_readalong(readalong).chapters] if readalong else []
            seen.append((tuple(c.index for c in record.chapters), named))
        return False

    run(folder, FakeVoice(fail_on=watch), chapters, progress=events.append, **kwargs)
    start = next(n for n, e in enumerate(events) if e.phase is Phase.LOADING_VOICE)
    return seen, events[start:]


def test_chapters_made_around_an_added_one_stay_playable_while_it_is_spoken(
    tmp_path: Path,
) -> None:
    """Chapters 1 and 3 are made, chapter 2 is added (#1070): while it is spoken, the
    record on disk and the read-along file still name chapters 1 and 3 in that order (the
    Listen page needs both to agree), and so do the job's events."""
    run(tmp_path, FakeVoice(), (0, 2))
    seen, events = while_beta_is_spoken(tmp_path, (1,))
    assert seen
    assert all(
        listed == ((0, 2), ["book - 01 Alpha.mp3", "book - 03 Gamma.mp3"]) for listed in seen
    )
    beta = next(n for n, e in enumerate(events) if e.ready == 1)
    assert all(e.playable == (0, 2) for e in events[:beta])
    assert events[-1].playable == (0, 1, 2)
    # and every file is the one a job making all three at once writes
    whole = tmp_path / "whole"
    run(whole, FakeVoice(), (0, 1, 2))
    assert files(tmp_path) == files(whole)


@pytest.mark.parametrize("how", ["missing", "settings"])
def test_a_chapter_not_taken_as_it_is_is_not_listed_until_it_is_made_again(
    tmp_path: Path, how: str
) -> None:
    """Chapters 1 and 3 are made, then chapter 2 is added while chapter 3's MP3 is gone, or
    every chapter is made again under other settings (D-909): chapter 3 is neither in the
    record on disk nor in the events while chapter 2 is spoken, only from its own `ready`
    on."""
    run(tmp_path, FakeVoice(), (0, 2))
    if how == "missing":
        (tmp_path / "out" / "book - 03 Gamma.mp3").unlink()
        seen, events = while_beta_is_spoken(tmp_path, (1, 2))
    else:
        seen, events = while_beta_is_spoken(
            tmp_path, (0, 1, 2), settings={"speed": 1.2}, overwrite=True
        )
    assert seen
    assert all(listed == ((0,), ["book - 01 Alpha.mp3"]) for listed in seen)
    gamma = next(n for n, e in enumerate(events) if e.ready == 2)
    assert all(2 not in e.playable for e in events[:gamma])
    assert events[-1].playable == (0, 1, 2)


def project(folder: Path) -> dict[str, bytes]:
    """The audiobook's files and the working folder's records, byte for byte."""
    work = folder / "work"
    return {**files(folder), **{n: (work / n).read_bytes() for n in (RECORD, "audio.json")}}


@pytest.mark.parametrize("how", ["stopped", "full-disk"])
def test_the_old_records_stay_until_the_added_chapter_puts_its_first_file_in_place(
    tmp_path: Path, how: str
) -> None:
    """Stopped while the added chapter is spoken, the earlier book is left as it was; when
    its first file fails to be written, the old records were removed before it (D-119) and
    the record and the read-along file name only the chapter before it. Either way the
    rerun ends as a job making all three at once."""
    run(tmp_path, FakeVoice(), (0, 2))
    before = project(tmp_path)
    if how == "stopped":

        def stop(text: str) -> bool:
            if "Beta" in text:
                raise KeyboardInterrupt
            return False

        with pytest.raises(KeyboardInterrupt):
            run(tmp_path, FakeVoice(fail_on=stop), (1,))
        assert project(tmp_path) == before
    else:
        ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=1, calls=[])  # Beta's MP3
        with pytest.raises(JobError, match="No space left on device"):
            run(tmp_path, FakeVoice(), (1,), ffmpeg=ffmpeg)
        assert not (tmp_path / "work" / "audio.json").exists()
        record = read_record(tmp_path / "work")
        assert record is not None
        assert [c.index for c in record.chapters] == [0]
        readalong = read_readalong(tmp_path / "out" / "book.readalong.json")
        assert [c.mp3 for c in readalong.chapters] == ["book - 01 Alpha.mp3"]
    run(tmp_path, FakeVoice(), (1, 2))
    whole = tmp_path / "whole"
    run(whole, FakeVoice(), (0, 1, 2))
    assert files(tmp_path) == files(whole)
