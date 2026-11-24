"""Each chapter becomes playable as soon as it is spoken (#723, LW-01): the job writes a
chapter's files before the next chapter is spoken, records them in `chapters.json`, tells
the listener, and a rerun or resume takes its own whole chapters as they are."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from audio_fakes import FakeVoice
from syrupy.assertion import SnapshotAssertion

from sci2audio.app import (
    AudioProgress,
    JobSettings,
    OutputExistsError,
    Phase,
    run_audio_job,
)
from sci2audio.app.audio import JOB_OUTPUT
from sci2audio.app.playable import (
    RECORD,
    RecordedFile,
    playable_chapters,
    read_record,
)
from sci2audio.output import Ffmpeg, OutputSettings, find_ffmpeg, read_readalong

TITLES = ("Alpha", "Beta", "Gamma")


def book(folder: Path, parts: tuple[str, ...] = TITLES) -> Path:
    """A Markdown book with one chapter per title, two sentences each."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "book.md"
    text = [f"# {t}\n\nThe chapter {t} starts here. It ends with {t}." for t in parts]
    path.write_text("\n\n".join(text), encoding="utf-8", newline="\n")
    return path


def run(folder: Path, voice: FakeVoice, **kwargs):  # type: ignore[no-untyped-def]
    settings = kwargs.pop("settings", JobSettings())
    settings = JobSettings(**{**settings.__dict__, "output_folder": folder / "out"})
    source = kwargs.pop("source", None) or book(folder / "in")
    return run_audio_job(source, settings, folder / "work", voice=voice.source(), **kwargs)


def outputs(folder: Path) -> list[str]:
    out = folder / "out"
    return sorted(p.name for p in out.iterdir()) if out.exists() else []


class Counting(Ffmpeg):
    """The real ffmpeg, noting the file each run writes."""

    def __init__(self) -> None:
        super().__init__(find_ffmpeg())
        object.__setattr__(self, "written", [])

    def run(self, args, feed=()):  # type: ignore[no-untyped-def]
        self.written.append(Path(args[-1]).name)  # type: ignore[attr-defined]
        return super().run(args, feed)


def test_each_chapter_is_playable_before_the_next_is_spoken(tmp_path: Path) -> None:
    seen: list[tuple[str, list[str]]] = []

    def watch(text: str) -> bool:  # called before each chunk is spoken
        seen.append((text, outputs(tmp_path)))
        return False

    run(tmp_path, FakeVoice(fail_on=watch))
    firsts = {text: names for text, names in seen if text.startswith("The chapter")}
    mp3s = lambda names: [n for n in names if n.endswith(".mp3")]  # noqa: E731
    assert mp3s(firsts["The chapter Alpha starts here."]) == []
    assert len(mp3s(firsts["The chapter Beta starts here."])) == 1
    assert len(mp3s(firsts["The chapter Gamma starts here."])) == 2
    # and the read-along file lists exactly those chapters at that moment
    assert any(n.endswith(".readalong.json") for n in firsts["The chapter Gamma starts here."])


def test_a_ready_event_names_each_chapter_in_document_order(tmp_path: Path) -> None:
    events: list[AudioProgress] = []
    run(tmp_path, FakeVoice(), progress=events.append, settings=JobSettings(chapters=(2, 0, 1)))
    ready = [e for e in events if e.ready is not None]
    assert [e.ready for e in ready] == [2, 0, 1]  # the job's order: the order chosen (#119)
    assert [e.playable for e in ready] == [(2,), (2, 0), (2, 0, 1)]
    assert all(e.phase is Phase.SPEAKING and e.chapter_done for e in ready)
    # every later event carries the playable chapters, the last one too
    after = events[events.index(ready[0]) + 1 :]
    assert all(2 in e.playable for e in after)
    assert events[-1].phase is Phase.DONE
    assert events[-1].playable == (2, 0, 1)


def test_the_record_lists_the_playable_chapters_while_the_job_runs(tmp_path: Path) -> None:
    seen: list[list[int]] = []

    def progress(event: AudioProgress) -> None:
        if event.ready is not None:
            seen.append([c.index for c in playable_chapters(tmp_path / "work", tmp_path / "out")])
            record = read_record(tmp_path / "work")
            assert record is not None
            assert not record.complete
            assert record.planned == (0, 1, 2)

    run(tmp_path, FakeVoice(), progress=progress)
    assert seen == [[0], [0, 1], [0, 1, 2]]
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.complete
    assert record.owned(tmp_path / "out") == set(outputs(tmp_path))


def test_the_laid_out_document_is_written_before_the_first_chapter_is_playable(
    tmp_path: Path,
) -> None:
    """The Listen page reads along in a book that is still growing (#724): it needs the
    laid-out document from the moment the first chapter is playable, not only at the end."""
    seen: list[tuple[bool, bool]] = []
    work = tmp_path / "work"

    def progress(event: AudioProgress) -> None:
        if event.ready is not None:
            seen.append(((work / "document.json").is_file(), (work / "audio.json").exists()))

    job = run(tmp_path, FakeVoice(), progress=progress)
    assert seen == [(True, False)] * 3
    whole = run(tmp_path / "again", FakeVoice())
    assert job.document_file.read_bytes() == whole.document_file.read_bytes()


def test_audio_json_is_still_written_only_at_the_end(tmp_path: Path) -> None:
    """`audio.json` alone vouches for a finished audiobook (D-119): a rerun removes the old
    one before its first file is put in place and writes its own only once it is done."""
    first = run(tmp_path, FakeVoice())
    old = first.document_file.read_bytes()
    seen: list[bool] = []

    def watch(text: str) -> bool:  # before each chunk is spoken
        seen.append(first.record.exists())
        return False

    other = JobSettings(speed=1.1)
    job = run(tmp_path, FakeVoice(fail_on=watch), overwrite=True, settings=other)
    # the old record stays while the first chapter is spoken (nothing of it replaced yet)
    # and goes before the first chapter's files are put in place
    assert seen[:3] == [True, True, True]
    assert seen[3:] == [False] * (len(seen) - 3)
    assert job.record.exists()
    assert job.document_file.read_bytes() == old  # same text, so the same document


def test_the_job_writes_no_m4b_by_default(tmp_path: Path) -> None:
    job = run(tmp_path, FakeVoice())
    assert OutputSettings(m4b=False) == JOB_OUTPUT
    assert job.written.m4b is None
    assert [n for n in outputs(tmp_path) if n.endswith(".mp3")] == [
        p.name for p in job.written.mp3s
    ]
    assert len(job.written.mp3s) == 3
    assert not any(n.endswith(".m4b") for n in outputs(tmp_path))
    assert read_readalong(job.written.readalong).m4b is None


def test_a_resume_reuses_finished_chapter_files_without_speaking_or_encoding_them(
    tmp_path: Path,
) -> None:
    def stop_in_gamma(text: str) -> bool:
        if "Gamma" in text:
            raise KeyboardInterrupt
        return False

    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, FakeVoice(fail_on=stop_in_gamma))
    done = [n for n in outputs(tmp_path) if n.endswith(".mp3")]
    assert len(done) == 2
    stamps = {n: (tmp_path / "out" / n).stat().st_mtime_ns for n in done}
    voice, ffmpeg = FakeVoice(), Counting()
    job = run(tmp_path, voice, ffmpeg=ffmpeg)  # no overwrite: they are the job's own
    assert all("Gamma" in text for text in voice.texts)  # nothing spoken twice
    assert [n for n in ffmpeg.written if n.endswith(".mp3.partial")] == [
        f".{job.written.mp3s[2].name}.partial"
    ]
    assert {n: (tmp_path / "out" / n).stat().st_mtime_ns for n in done} == stamps
    whole = run(tmp_path / "whole", FakeVoice())
    assert [p.read_bytes() for p in job.written.mp3s] == [
        p.read_bytes() for p in whole.written.mp3s
    ]
    assert job.written.readalong.read_bytes() == whole.written.readalong.read_bytes()


def stopped_after_two(tmp_path: Path) -> None:
    def stop_in_gamma(text: str) -> bool:
        if "Gamma" in text:
            raise KeyboardInterrupt
        return False

    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, FakeVoice(fail_on=stop_in_gamma))


def test_a_resume_after_the_settings_changed_is_refused_without_overwrite(
    tmp_path: Path,
) -> None:
    """Nothing is mixed silently: the files of a run under other settings are not the
    job's to replace or to reuse unless the person says replace (D-163)."""
    stopped_after_two(tmp_path)
    before = {n: (tmp_path / "out" / n).read_bytes() for n in outputs(tmp_path)}
    voice = FakeVoice()
    with pytest.raises(OutputExistsError, match="choose to replace them"):
        run(tmp_path, voice, settings=JobSettings(speed=1.2))
    assert voice.spoken == []
    assert {n: (tmp_path / "out" / n).read_bytes() for n in outputs(tmp_path)} == before
    job = run(tmp_path, FakeVoice(), settings=JobSettings(speed=1.2), overwrite=True)
    assert len(job.written.mp3s) == 3


def test_a_chapter_file_changed_since_is_not_reused(tmp_path: Path) -> None:
    stopped_after_two(tmp_path)
    first = sorted(n for n in outputs(tmp_path) if n.endswith(".mp3"))[0]
    (tmp_path / "out" / first).write_bytes(b"someone changed it")
    with pytest.raises(OutputExistsError, match="choose to replace them"):
        run(tmp_path, FakeVoice())
    assert (tmp_path / "out" / first).read_bytes() == b"someone changed it"
    ffmpeg = Counting()
    run(tmp_path, FakeVoice(), ffmpeg=ffmpeg, overwrite=True)
    assert f".{first}.partial" in ffmpeg.written  # encoded again, not taken as it was


def stopped_in(tmp_path: Path, title: str) -> None:
    def stop(text: str) -> bool:
        if title in text:
            raise KeyboardInterrupt
        return False

    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, FakeVoice(fail_on=stop))


def audio_events(tmp_path: Path, voice: FakeVoice, **kwargs) -> list[tuple[AudioProgress, int]]:  # type: ignore[no-untyped-def]
    """The job's events from the first of its audio stage on (the voice is about to be
    loaded), each with the number of engines made by then."""
    events: list[tuple[AudioProgress, int]] = []
    run(tmp_path, voice, progress=lambda event: events.append((event, voice.made)), **kwargs)
    start = next(n for n, (e, _) in enumerate(events) if e.phase is Phase.LOADING_VOICE)
    return events[start:]


def test_a_resumed_job_reports_its_made_chapters_as_playable_before_the_voice_loads(
    tmp_path: Path,
) -> None:
    """The making card offers listening from the start of a resume, not only once the
    first chapter is done again after the voice has loaded (#1065)."""
    stopped_in(tmp_path, "Beta")
    voice = FakeVoice()
    events = audio_events(tmp_path, voice)
    first, made = events[0]
    assert made == 0
    assert first.playable == (0,)
    assert all(0 in e.playable for e, _ in events)
    assert all("Alpha" not in text for text in voice.texts)
    assert events[-1][0].playable == (0, 1, 2)


def damage(tmp_path: Path, how: str) -> None:
    """Spoil the earlier run's book: chapter 2's MP3 gone or cut short, or its read-along
    file changed."""
    out = tmp_path / "out"
    if how == "missing":
        sorted(out.glob("*.mp3"))[1].unlink()
    elif how == "truncated":
        mp3 = sorted(out.glob("*.mp3"))[1]
        mp3.write_bytes(mp3.read_bytes()[:-100])
    elif how == "readalong":
        readalong = next(out.glob("*.readalong.json"))
        readalong.write_text(readalong.read_text(encoding="utf-8") + " ", encoding="utf-8")


@pytest.mark.parametrize(
    ("how", "overwrite"),
    # a changed file is not the job's own: it goes on only when told to replace it
    [("missing", False), ("truncated", True), ("readalong", True)],
)
def test_nothing_is_reported_before_the_run_writes_when_the_earlier_book_is_not_whole(
    tmp_path: Path, how: str, overwrite: bool
) -> None:
    """Until the run puts its first file in place, the Listen page plays the earlier run's
    book only as a whole: with any of its files missing or changed it plays none of it, so
    no chapter is reported, and a chapter made again only from its own `ready` on."""
    stopped_in(tmp_path, "Gamma")
    damage(tmp_path, how)
    events = audio_events(tmp_path, FakeVoice(), overwrite=overwrite)
    first_ready = next(n for n, (e, _) in enumerate(events) if e.ready is not None)
    assert all(e.playable == () for e, _ in events[:first_ready])
    ready = next(n for n, (e, _) in enumerate(events) if e.ready == 1)
    assert all(1 not in e.playable for e, _ in events[:ready])
    assert events[-1][0].playable == (0, 1, 2)


def test_made_chapters_are_not_reported_once_the_settings_changed(tmp_path: Path) -> None:
    """Under the same settings a resume reports the chapters made so far; under others
    (replace all, D-909) none of them, each only once it is made again."""
    stopped_in(tmp_path / "same", "Gamma")
    assert audio_events(tmp_path / "same", FakeVoice())[0][0].playable == (0, 1)
    stopped_in(tmp_path, "Gamma")
    events = audio_events(tmp_path, FakeVoice(), settings=JobSettings(speed=1.2), overwrite=True)
    assert events[0][0].playable == ()
    seen: tuple[int, ...] = ()
    for event, _ in events:
        assert set(event.playable) <= set(seen) | ({event.ready} - {None})
        seen = event.playable
    assert seen == (0, 1, 2)


def test_a_finished_audiobook_is_still_refused_without_overwrite(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    voice = FakeVoice()
    with pytest.raises(OutputExistsError, match="exist already"):
        run(tmp_path, voice)
    assert voice.made == 0
    ffmpeg = Counting()
    again = run(tmp_path, voice, overwrite=True, ffmpeg=ffmpeg)
    assert again.spoken == 0
    assert ffmpeg.written == []  # with overwrite, the same chapters are taken as they are


def test_a_chapter_whose_every_sentence_failed_gets_no_file_and_keeps_the_numbers(
    tmp_path: Path,
) -> None:
    job = run(tmp_path, FakeVoice(fail_on=lambda text: "Beta" in text))
    names = [p.name for p in job.written.mp3s]
    assert len(names) == 2
    assert " 1 Alpha" in names[0] or " 01 Alpha" in names[0]
    assert " 3 Gamma" in names[1] or " 03 Gamma" in names[1]
    assert [c.title for c in read_readalong(job.written.readalong).chapters] == ["Alpha", "Gamma"]
    assert {s.chapter for s in job.skipped} == {1}
    record = read_record(tmp_path / "work")
    assert record is not None
    assert [(c.index, c.number) for c in record.chapters] == [(0, 1), (2, 3)]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        '{"format": "sci2audio-chapters", "version": 3}',
        '{"format": "other", "version": 1}',
        json.dumps(
            {
                "format": "sci2audio-chapters",
                "version": 1,
                "complete": False,
                "settings": "x",
                "planned": [0],
                "chapters": [],
                "book": [{"name": "../escape.mp3", "bytes": 1, "sha256": "0" * 64}],
                "pending": [],
            }
        ),
        json.dumps(
            {
                "format": "sci2audio-chapters",
                "version": 1,
                "complete": "no",
                "settings": "x",
                "planned": [0],
                "chapters": [],
                "book": [],
                "pending": [],
            }
        ),
    ],
    ids=["empty", "not-json", "newer", "foreign", "path-in-name", "bad-flag"],
)
def test_a_broken_or_foreign_record_reads_as_none(tmp_path: Path, text: str) -> None:
    (tmp_path / RECORD).write_text(text, encoding="utf-8")
    assert read_record(tmp_path) is None
    assert playable_chapters(tmp_path, tmp_path) == ()


def test_a_linked_or_huge_record_reads_as_none(tmp_path: Path) -> None:
    run(tmp_path, FakeVoice())
    record = tmp_path / "work" / RECORD
    assert read_record(tmp_path / "work") is not None
    record.write_bytes(b" " * (4 * 1024 * 1024 + 1))
    assert read_record(tmp_path / "work") is None
    record.unlink()
    target = tmp_path / "elsewhere.json"
    target.write_text("{}", encoding="utf-8")
    try:
        record.symlink_to(target)
    except OSError:
        pytest.skip("no symbolic links here")
    assert read_record(tmp_path / "work") is None


def test_a_recorded_file_matches_only_with_its_size_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "a.mp3"
    path.write_bytes(b"abc")
    sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert RecordedFile("a.mp3", 3, sha).matches(tmp_path)
    assert not RecordedFile("a.mp3", 4, sha).matches(tmp_path)
    assert not RecordedFile("a.mp3", 3, "0" * 64).matches(tmp_path)
    assert not RecordedFile("b.mp3", 3, sha).matches(tmp_path)


def test_the_records_snapshot_of_a_chapters_only_job(
    tmp_path: Path, snapshot: SnapshotAssertion
) -> None:
    job = run(tmp_path, FakeVoice())
    record = json.loads(job.record.read_text(encoding="utf-8"))
    record["sci2audio"] = "<version>"
    record["cache_bytes"] = "<size>"
    record["characters_per_second"] = "<measured>"
    chapters = json.loads((tmp_path / "work" / RECORD).read_text(encoding="utf-8"))
    chapters["settings"] = "<sha256 of the settings, the voice and the book>"
    for entry in [*chapters["chapters"]]:
        entry["fingerprint"] = "<sha256 of the chapter's input>"
        entry["spoken"] = f"<sha256 of spoken/{entry['index']}.json>"
        for file in entry["files"]:
            file["sha256"] = f"<sha256 of {file['name']}>"
            file["bytes"] = "<size>"
    for file in chapters["book"]:
        file["sha256"] = f"<sha256 of {file['name']}>"
        file["bytes"] = "<size>"
    readalong = json.loads(job.written.readalong.read_text(encoding="utf-8"))
    assert {
        "audio.json": record,
        "chapters.json": chapters,
        "readalong.json": readalong,
    } == snapshot
