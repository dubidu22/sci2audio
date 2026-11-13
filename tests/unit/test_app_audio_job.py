"""The audio job on files (#71) with a fake voice and the real ffmpeg (a few seconds of
audio, D-118): what it writes, resume from the chunk cache, progress and the estimate,
cancel, one job at a time, and the errors a person can act on."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf

from sci2audio.app import (
    AudioProgress,
    JobBusyError,
    JobCancelledError,
    JobError,
    JobRunner,
    JobSettings,
    OutputExistsError,
    Phase,
    clean_work_folder,
    run_audio_job,
)
from sci2audio.app import audio as audio_module
from sci2audio.app.lock import work_folder_lock
from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.core.export import from_data
from sci2audio.output import FfmpegNotFoundError, OutputSettings, read_readalong
from sci2audio.textprep import Category, Stage, StepContext, TextStep
from sci2audio.voices import ModelNotFoundError

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PYMEDPHYS = CORPUS / "papers" / "joss2022-biggs-pymedphys.pdf"


class Replacing(TextStep):
    """A text step that proposes the edits it is given."""

    id = "replacing"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def __init__(self, *edits: Edit) -> None:
        self.edits = [replace(edit, step=self.id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


def small_pdf(folder: Path, *lines: str) -> Path:
    path = folder / "note.pdf"
    texts = lines or ("A short note.", "It has two lines.")
    path.write_bytes(
        make_pdf([Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(texts)])
    )
    return path


def run(source: Path, folder: Path, voice: FakeVoice, **kwargs):  # type: ignore[no-untyped-def]
    settings = kwargs.pop("settings", JobSettings())
    if settings.output_folder is None:
        settings = JobSettings(**{**settings.__dict__, "output_folder": folder / "out"})
    return run_audio_job(source, settings, folder / "work", voice=voice.source(), **kwargs)


def outputs(folder: Path) -> list[str]:
    return sorted(p.name for p in (folder / "out").iterdir()) if (folder / "out").exists() else []


class Clock:
    """One second per call: the job reads it before and after each chunk it speaks, so
    every spoken chunk takes one second."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


def test_a_paper_becomes_mp3s_an_m4b_a_read_along_file_and_records(tmp_path: Path) -> None:
    voice = FakeVoice()
    job = run(PYMEDPHYS, tmp_path, voice)
    names = outputs(tmp_path)
    assert len(names) == 6  # 4 chapters (the reference list is not chosen), M4B, read-along
    assert sum(n.endswith(".mp3") for n in names) == 4
    assert job.written.m4b is not None
    assert job.written.m4b.name in names
    assert (job.spoken, job.reused, job.skipped) == (41, 0, ())
    assert voice.made == voice.released == voice.sessions_disposed == 1
    readalong = read_readalong(job.written.readalong)
    planned = [u.span for u in job.result.utterances if not u.pause]
    assert [c.span for c in readalong.chunks] == planned
    assert [c.title for c in readalong.chapters] == [
        c.chapter.title for c in job.result.chapters if c.selected
    ]
    record = json.loads(job.record.read_text(encoding="utf-8"))
    assert (record["format"], record["version"]) == ("sci2audio-audio", 1)
    assert record["chunks"] == {"total": 41, "spoken": 41, "reused": 0, "skipped": 0}
    assert record["duration"] == readalong.duration == job.duration
    assert [c["selected"] for c in record["chapters"]] == [True, True, True, True, False]
    assert record["files"]["m4b"] == job.written.m4b.name
    assert record["cache_bytes"] > 0
    document = from_data(Document, json.loads(job.document_file.read_text(encoding="utf-8")))
    assert document == job.result.document  # the player can show the block text (#78)
    assert not list((tmp_path / "work").rglob("*.part*"))


def test_a_rerun_reuses_every_chunk_and_never_loads_the_voice(tmp_path: Path) -> None:
    first = run(PYMEDPHYS, tmp_path, FakeVoice())
    before = first.written.readalong.read_text(encoding="utf-8")
    voice = FakeVoice()
    again = run(PYMEDPHYS, tmp_path, voice, overwrite=True)
    assert (again.spoken, again.reused, voice.made) == (0, 41, 0)
    assert again.written.readalong.read_text(encoding="utf-8") == before
    assert json.loads(again.record.read_text())["chunks"]["reused"] == 41


def test_existing_audiobook_files_are_refused_before_the_voice_is_made(tmp_path: Path) -> None:
    run(PYMEDPHYS, tmp_path, FakeVoice())
    voice = FakeVoice()
    with pytest.raises(OutputExistsError, match=r"exist already.*choose to replace them"):
        run(PYMEDPHYS, tmp_path, voice)
    assert (voice.made, voice.spoken) == (0, [])


def test_another_speed_voice_or_text_speaks_again_and_only_what_changed(
    tmp_path: Path,
) -> None:
    source = small_pdf(tmp_path, "A short note [1].", "It has two lines.")
    run(source, tmp_path, FakeVoice())
    faster = FakeVoice()
    run(source, tmp_path, faster, overwrite=True, settings=JobSettings(speed=1.5))
    assert len(faster.spoken) == 2
    assert {s for _, _, s in faster.spoken} == {1.5}
    george = FakeVoice()
    run(source, tmp_path, george, overwrite=True, settings=JobSettings(voice="bm_george"))
    assert {v for _, v, _ in george.spoken} == {"bm_george"}
    changed = FakeVoice()  # a text step's edit changes one sentence: only it is spoken again
    step = Replacing(Edit(Span(0, 13, 16), EditKind.REPLACE, "a test", "x", "one"))
    job = run(source, tmp_path, changed, overwrite=True, steps=[step])
    assert changed.texts == ["A short note one."]
    assert job.reused == 1


def test_the_same_text_twice_is_spoken_once(tmp_path: Path) -> None:
    source = small_pdf(tmp_path, "Once more.", "", "Once more.")
    voice = FakeVoice()
    job = run(source, tmp_path, voice)
    texts = [u.text for u in job.result.utterances if not u.pause]
    assert texts.count("Once more.") == 2
    assert voice.texts.count("Once more.") == 1
    assert job.reused == 1


def test_progress_goes_through_the_phases_and_estimates_after_the_first_chapter(
    tmp_path: Path,
) -> None:
    events: list[AudioProgress] = []
    job = run(PYMEDPHYS, tmp_path, FakeVoice(), progress=events.append, clock=Clock())
    phases = list(dict.fromkeys(e.phase for e in events))
    assert phases == [
        Phase.READING,
        Phase.LAYOUT,
        Phase.TEXT_STEPS,
        Phase.LOADING_VOICE,
        Phase.SPEAKING,
        Phase.ENCODING,
        Phase.DONE,
    ]
    chunks = [e for e in events if e.phase is Phase.SPEAKING and e.chunks_done > 0]
    assert [e.chunks_done for e in chunks] == list(range(1, 42))
    assert all(e.chunks_total == 41 and e.chapters == 4 for e in chunks)
    done = [e.characters_done for e in chunks]
    assert done == sorted(done)
    assert done[-1] == chunks[-1].characters_total
    # the speed: every chunk takes 1 s on the clock; the first one (warm-up) is not measured
    texts = [u.text for u in job.result.utterances if not u.pause]
    measured = sum(len(t) for t in texts[1:])
    assert chunks[-1].characters_per_second == pytest.approx(measured / 40)
    first_chapter = [e for e in chunks if e.chapter == 0]
    for event in chunks:
        measured_so_far = event.characters_done - len(texts[0])
        ready = event.chunks_done >= len(first_chapter) and measured_so_far >= 500
        assert (event.seconds_left is not None) == ready, event
        if event.seconds_left is not None:  # what is left, at the speed measured so far
            left = event.characters_total - event.characters_done
            assert event.characters_per_second is not None
            assert event.seconds_left == pytest.approx(left / event.characters_per_second)
    assert chunks[-1].seconds_left == 0


def test_cancel_before_the_start_does_nothing(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    voice = FakeVoice()
    with pytest.raises(JobCancelledError, match="cancelled"):
        run(PYMEDPHYS, tmp_path, voice, cancel=cancel)
    assert (voice.made, outputs(tmp_path)) == (0, [])


def test_cancel_while_speaking_keeps_the_finished_chunks_for_a_rerun(tmp_path: Path) -> None:
    cancel = threading.Event()

    def progress(event: AudioProgress) -> None:
        if event.chunks_done == 5:
            cancel.set()

    voice = FakeVoice()
    with pytest.raises(JobCancelledError):
        run(PYMEDPHYS, tmp_path, voice, cancel=cancel, progress=progress)
    assert len(voice.spoken) == 5
    assert voice.released == 1
    assert outputs(tmp_path) == []
    rest = FakeVoice()
    job = run(PYMEDPHYS, tmp_path, rest)
    assert (len(rest.spoken), job.reused) == (36, 5)


def test_cancel_while_encoding_leaves_no_audiobook_file(tmp_path: Path) -> None:
    cancel = threading.Event()

    def progress(event: AudioProgress) -> None:
        if event.phase is Phase.ENCODING:
            cancel.set()

    with pytest.raises(JobCancelledError):
        run(PYMEDPHYS, tmp_path, FakeVoice(), cancel=cancel, progress=progress)
    assert outputs(tmp_path) == []  # no partial file, no target
    job = run(PYMEDPHYS, tmp_path, FakeVoice())
    assert job.reused == 41


def test_an_unknown_voice_is_refused_before_any_work(tmp_path: Path) -> None:
    voice = FakeVoice()
    with pytest.raises(JobError, match="no fake voice 'nobody'"):
        run(PYMEDPHYS, tmp_path, voice, settings=JobSettings(voice="nobody"))
    assert voice.made == 0
    assert not (tmp_path / "work").exists()


def test_missing_voice_files_stop_the_job_before_any_speech(tmp_path: Path) -> None:
    voice = FakeVoice(fail_to_make=ModelNotFoundError("voice file x.pt is missing"))
    with pytest.raises(JobError, match=r"the voice is not set up: voice file x.pt is missing"):
        run(PYMEDPHYS, tmp_path, voice)
    assert outputs(tmp_path) == []


def test_missing_ffmpeg_stops_the_job_before_any_speech(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing() -> Path:
        raise FfmpegNotFoundError

    monkeypatch.setattr(audio_module, "find_ffmpeg", missing)
    voice = FakeVoice()
    with pytest.raises(JobError, match="ffmpeg was not found"):
        run(PYMEDPHYS, tmp_path, voice)
    assert voice.made == 0


def test_a_sentence_the_voice_fails_on_is_left_out_and_listed(tmp_path: Path) -> None:
    source = small_pdf(tmp_path, "First line.", "", "Bad line.", "", "Last line.")
    voice = FakeVoice(fail_on=lambda text: text.startswith("Bad"))
    job = run(source, tmp_path, voice)
    assert voice.texts == ["First line.", "Last line."]
    (skipped,) = job.skipped
    assert (skipped.text, skipped.page, skipped.chapter) == ("Bad line.", 1, 0)
    assert "cannot say" in skipped.error
    record = json.loads(job.record.read_text())
    assert record["skipped"][0]["text"] == "Bad line."
    assert record["chunks"]["skipped"] == 1
    assert len(read_readalong(job.written.readalong).chunks) == 2


def test_five_failures_in_a_row_stop_the_job(tmp_path: Path) -> None:
    lines = [f"Line {n}." for n in range(7)]
    source = small_pdf(tmp_path, *[x for line in lines for x in (line, "")])
    voice = FakeVoice(fail_on=lambda text: text != "Line 0.")
    with pytest.raises(JobError, match=r"failed on 5 sentences in a row.*kept for a rerun"):
        run(source, tmp_path, voice)
    assert voice.texts == ["Line 0."]
    assert outputs(tmp_path) == []


def test_a_voice_that_speaks_nothing_at_all_fails_the_job(tmp_path: Path) -> None:
    with pytest.raises(JobError, match="could not speak any"):
        run(small_pdf(tmp_path, "Only line."), tmp_path, FakeVoice(fail_on=lambda t: True))


def test_nothing_to_say_fails_without_loading_the_voice(tmp_path: Path) -> None:
    voice = FakeVoice()
    with pytest.raises(JobError, match="nothing to read in the chosen chapters"):
        run(PYMEDPHYS, tmp_path, voice, settings=JobSettings(chapters=frozenset()))
    assert voice.made == 0


def test_only_m4b_writes_no_mp3s(tmp_path: Path) -> None:
    job = run(small_pdf(tmp_path), tmp_path, FakeVoice(), output_settings=OutputSettings(mp3=False))
    assert job.written.mp3s == ()
    assert job.written.m4b is not None
    assert json.loads(job.record.read_text())["files"]["mp3"] == []


def test_one_job_at_a_time_on_a_runner_and_per_working_folder(tmp_path: Path) -> None:
    runner = JobRunner()
    started, release = threading.Event(), threading.Event()

    def progress(event: AudioProgress) -> None:
        if event.phase is Phase.SPEAKING and event.chunks_done == 1:  # one chunk cached
            started.set()
            release.wait(30)

    settings = JobSettings(output_folder=tmp_path / "out")
    source = small_pdf(tmp_path)
    errors: list[BaseException] = []

    def first() -> None:
        try:
            runner.run_audio(
                source, settings, tmp_path / "work", voice=FakeVoice().source(), progress=progress
            )
        except BaseException as error:  # pragma: no cover - reported below
            errors.append(error)

    thread = threading.Thread(target=first)
    thread.start()
    try:
        assert started.wait(30)
        assert runner.busy
        with pytest.raises(JobBusyError, match="another job is running"):
            runner.run_audio(source, settings, tmp_path / "w2", voice=FakeVoice().source())
        with pytest.raises(JobBusyError, match="another job is running"):
            runner.run_script(source, settings, tmp_path / "w3")
        # another runner (another window) on the same working folder: the folder's lock
        with pytest.raises(JobBusyError, match="another sci2audio job"):
            JobRunner().run_audio(source, settings, tmp_path / "work", voice=FakeVoice().source())
        # nor may its chunk cache be cleaned under it (D-226)
        cached = sorted((tmp_path / "work" / "chunks").rglob("*.wav"))
        assert cached
        with pytest.raises(JobBusyError, match="another sci2audio job"):
            clean_work_folder(tmp_path / "work")
        assert sorted((tmp_path / "work" / "chunks").rglob("*.wav")) == cached
    finally:
        release.set()
        thread.join(60)
    assert errors == []
    assert not runner.busy


def test_a_working_folder_locked_elsewhere_is_refused(tmp_path: Path) -> None:
    with work_folder_lock(tmp_path / "work"), pytest.raises(JobBusyError):
        run(small_pdf(tmp_path), tmp_path, FakeVoice())


def test_the_records_snapshot(tmp_path: Path, snapshot) -> None:  # type: ignore[no-untyped-def]
    source = small_pdf(tmp_path, "A short note.", "", "It has two paragraphs. And three sentences.")
    job = run(source, tmp_path, FakeVoice(), clock=Clock())
    record = json.loads(job.record.read_text(encoding="utf-8"))
    record["sci2audio"] = "<version>"
    record["source"]["sha256"] = "<the generated PDF's>"  # may differ between pdfium builds
    readalong = json.loads(job.written.readalong.read_text(encoding="utf-8"))
    assert {"audio.json": record, "readalong.json": readalong} == snapshot
