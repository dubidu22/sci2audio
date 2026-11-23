"""Chapters made later (#726, LW-04): a job choosing more chapters than the project has
made adds only the new ones, keeps every file made before byte for byte, plays the book
in printed order, and never mixes settings silently."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import (
    JobSettings,
    OutputExistsError,
    SettingsChangedError,
    run_audio_job,
)
from sci2audio.app.playable import RECORD, read_record
from sci2audio.output import read_readalong

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


def test_a_version_1_record_reads_and_asks_for_a_choice(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice(), (0,))
    path = tmp_path / "work" / RECORD
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("order", "made", "built"):
        del data[key]
    for chapter in data["chapters"]:
        del chapter["spoken"]
    data["version"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
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
