"""The audio job on files (#71) with a fake voice and the real ffmpeg (a few seconds of
audio, D-118): what it writes, resume from the chunk cache, progress and the estimate,
cancel, one job at a time, and the errors a person can act on."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from audio_fakes import FakeVoice, chunk_count
from pdf_maker import Text, glyph_number_pdf, joined_pdf, make_pdf

from sci2audio.app import (
    AudioProgress,
    JobBusyError,
    JobCancelledError,
    JobError,
    JobRunner,
    JobSettings,
    OutputExistsError,
    Phase,
    UnreadableFileError,
    UnreadableTextError,
    clean_work_folder,
    run_audio_job,
)
from sci2audio.app import audio as audio_module
from sci2audio.app.lock import work_folder_lock
from sci2audio.app.playable import read_record
from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.core.export import from_data
from sci2audio.output import FfmpegNotFoundError, OutputSettings, read_readalong
from sci2audio.textprep import Category, Stage, StepContext, TextStep
from sci2audio.voices import ModelNotFoundError

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PYMEDPHYS = CORPUS / "papers" / "joss2022-biggs-pymedphys.pdf"


def chunks() -> int:
    """The chunks a default job on the PyMedPhys paper speaks (41 before #66's steps)."""
    return chunk_count(PYMEDPHYS)


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
    # the whole book, as the command line writes it; the job's own default is
    # test_app_audio_chapters.py's
    kwargs.setdefault("output_settings", OutputSettings())
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
    assert (job.spoken, job.reused, job.skipped) == (chunks(), 0, ())
    assert voice.made == voice.released == voice.sessions_disposed == 1
    readalong = read_readalong(job.written.readalong)
    planned = [u.span for u in job.result.utterances if not u.pause]
    assert [c.span for c in readalong.chunks] == planned
    assert [c.title for c in readalong.chapters] == [
        c.chapter.title for c in job.result.chapters if c.selected
    ]
    record = json.loads(job.record.read_text(encoding="utf-8"))
    assert (record["format"], record["version"]) == ("sci2audio-audio", 1)
    assert record["chunks"] == {"total": chunks(), "spoken": chunks(), "reused": 0, "skipped": 0}
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
    assert (again.spoken, again.reused, voice.made) == (0, chunks(), 0)
    assert again.written.readalong.read_text(encoding="utf-8") == before
    assert json.loads(again.record.read_text())["chunks"]["reused"] == chunks()


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
    voice = FakeVoice()
    job = run(PYMEDPHYS, tmp_path, voice, progress=events.append, clock=Clock())
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
    # one event per chunk; the event that a chapter became playable (#723) is its own
    events_spoken = [
        e for e in events if e.phase is Phase.SPEAKING and e.chunks_done > 0 and e.ready is None
    ]
    assert [e.chunks_done for e in events_spoken] == list(range(1, chunks() + 1))
    assert all(e.chunks_total == chunks() and e.chapters == 4 for e in events_spoken)
    done = [e.characters_done for e in events_spoken]
    assert done == sorted(done)
    assert done[-1] == events_spoken[-1].characters_total
    # the speed: every chunk takes 1 s on the clock; the first four (warm-up) are not
    # measured (D-381)
    warm_up = 4  # D-381
    assert warm_up == audio_module.WARM_UP_CALLS
    texts = [u.text for u in job.result.utterances if not u.pause]
    measured = sum(len(t) for t in texts[warm_up:])
    assert events_spoken[-1].characters_per_second == pytest.approx(measured / (chunks() - warm_up))
    first_chapter = [e for e in events_spoken if e.chapter == 0]
    shown = 0
    for event in events_spoken:
        measured_so_far = event.characters_done - sum(len(t) for t in texts[:warm_up])
        ready = event.chunks_done >= len(first_chapter) and measured_so_far >= 1000  # D-382
        assert (event.seconds_left is not None) == ready, event
        if event.seconds_left is not None:  # every call costs 1 s whatever its length, and
            shown += 1  # the cost model finds that: one second per chunk left (D-380), except
            # that a chunk longer than any measured one costs that one's second per character
            # (D-384): at the default limit (#494) such chunks are still to come here
            spoken = [len(text) for text in voice.texts]
            longest = max(spoken[warm_up : event.chunks_done])
            left = sum(1.0 if n <= longest else n / longest for n in spoken[event.chunks_done :])
            assert event.seconds_left == pytest.approx(left)
    assert shown > 0
    assert events_spoken[-1].seconds_left == 0


def test_progress_numbers_the_chapter_and_says_when_it_is_done(tmp_path: Path) -> None:
    """D-695: `chapter_number` is the chapter's place among those spoken, in the order
    read; `chapter_done` marks a chapter's last chunk, so the next chunk is the next
    chapter's first. The chosen order (#119) counts, not the document's."""
    events: list[AudioProgress] = []
    run(
        PYMEDPHYS,
        tmp_path,
        FakeVoice(),
        settings=JobSettings(chapters=(2, 0)),
        progress=events.append,
    )
    spoken = [
        e for e in events if e.phase is Phase.SPEAKING and e.chunks_done > 0 and e.ready is None
    ]
    assert [e.chapter_number for e in spoken] == sorted(e.chapter_number for e in spoken)
    assert {e.chapter: e.chapter_number for e in spoken} == {2: 1, 0: 2}
    assert all(e.chapters == 2 for e in spoken)
    boundary = [n for n, e in enumerate(spoken) if e.chapter_done]
    assert len(boundary) == 2  # one last chunk per chapter
    last_of_first = boundary[0]
    assert spoken[last_of_first].chapter_number == 1
    assert spoken[last_of_first + 1].chapter_number == 2
    assert not spoken[last_of_first + 1].chapter_done
    assert spoken[-1].chapter_done
    assert boundary[1] == len(spoken) - 1
    # the phases before the first chunk carry neither
    before = [e for e in events if e.phase is not Phase.SPEAKING or e.chunks_done == 0]
    assert all(e.chapter_number == 0 and not e.chapter_done for e in before)


class CostClock:
    """A clock the fake voice moves on: each call costs `cost(characters)` seconds, the
    first `slow` calls twice that (a voice warming up)."""

    def __init__(self, cost, slow: int = 0) -> None:  # type: ignore[no-untyped-def]
        self.now = 0.0
        self.cost = cost
        self.slow = slow
        self.calls = 0

    def __call__(self) -> float:
        return self.now

    def speak(self, text: str) -> None:
        self.calls += 1
        self.now += self.cost(len(text)) * (2 if self.calls <= self.slow else 1)


def test_the_estimate_fits_a_cost_per_call_per_character_and_per_square(
    tmp_path: Path,
) -> None:
    """A voice whose calls cost 0.4 s + 0.02 s per character + 0.0001 s per character
    squared, and whose first four calls are twice as slow: once shown, the estimate is the
    real time left (D-380, D-381); the plain rate would be off."""

    def cost(characters: int) -> float:
        return 0.4 + 0.02 * characters + 0.0001 * characters**2

    assert audio_module.WARM_UP_CALLS == 4  # D-381
    clock = CostClock(cost, slow=4)
    voice = FakeVoice(on_speak=clock.speak)
    events: list[AudioProgress] = []
    # the 300-character limit this test was written for (#494 raised the default)
    run(PYMEDPHYS, tmp_path, voice, progress=events.append, clock=clock, max_chars=300)
    lengths = [len(text) for text in voice.texts]
    estimates = [
        e for e in events if e.phase is Phase.SPEAKING and e.chunks_done and e.seconds_left
    ]
    assert len(estimates) > 5
    plain_rate_off = 0.0
    for event in estimates:
        real = sum(cost(n) for n in lengths[event.chunks_done :])
        # D-384: a chunk longer than every measured one costs the longest one's time per
        # character, so the fitted curve is never stretched past what it saw; which chunks
        # come later than the longest measured one depends on where the text is cut (#477)
        longest = max(lengths[audio_module.WARM_UP_CALLS : event.chunks_done])
        fitted = sum(
            cost(n) if n <= longest else n * cost(longest) / longest
            for n in lengths[event.chunks_done :]
        )
        assert event.seconds_left == pytest.approx(fitted, rel=1e-6)
        assert event.characters_per_second is not None
        plain = (event.characters_total - event.characters_done) / event.characters_per_second
        plain_rate_off = max(plain_rate_off, abs(plain - real) / real)
    assert plain_rate_off > 0.05


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
    assert (len(rest.spoken), job.reused) == (chunks() - 5, 5)


def test_cancel_while_encoding_the_book_leaves_its_whole_chapters_and_no_m4b(
    tmp_path: Path,
) -> None:
    cancel = threading.Event()

    def progress(event: AudioProgress) -> None:
        if event.phase is Phase.ENCODING:
            cancel.set()

    with pytest.raises(JobCancelledError):
        run(PYMEDPHYS, tmp_path, FakeVoice(), cancel=cancel, progress=progress)
    # every chapter was playable before the M4B was begun (#723); no partial file, no M4B
    names = outputs(tmp_path)
    assert [n for n in names if n.endswith(".mp3")]
    assert not [n for n in names if ".m4b" in n]
    assert not [n for n in names if n.endswith(".partial")]
    job = run(PYMEDPHYS, tmp_path, FakeVoice())
    assert job.reused == chunks()


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


def test_the_pieces_of_a_cut_sentence_are_joined_by_the_clause_pause(tmp_path: Path) -> None:
    """#480: the voice's own silence at a cut is trimmed and the clause pause put in its
    place; between whole sentences the silence stays."""
    source = small_pdf(tmp_path, "One sentence first. A long sentence, cut at its comma here.")
    voice = FakeVoice(edge_silence=12_000)  # half a second on each side, as Kokoro
    job = run(source, tmp_path, voice, max_chars=30)
    assert voice.texts == ["One sentence first.", "A long sentence,", "cut at its comma here."]
    chunks = read_readalong(job.written.readalong).chunks
    assert [c.joins for c in chunks] == [False, False, True]
    settings = OutputSettings()
    # the pause between the chunks: the clause pause at the cut, the sentence pause before it
    assert chunks[2].start - chunks[1].end == pytest.approx(settings.clause_pause, abs=0.002)
    assert chunks[1].start - chunks[0].end == pytest.approx(settings.sentence_pause, abs=0.002)
    # each piece keeps 30 ms (up to one 10 ms step more) of its 0.5 s quiet at the cut, so
    # what is heard there is the clause pause and about 60 ms, not a second of silence
    lengths = [c.end - c.start for c in chunks]
    rate, quiet, keep = 24_000, 0.5, 0.03
    assert lengths[0] == pytest.approx(2 * quiet + 190 / rate, abs=0.001)  # untrimmed
    assert lengths[1] == pytest.approx(quiet + 160 / rate + keep, abs=0.011)
    assert lengths[2] == pytest.approx(keep + 220 / rate + quiet, abs=0.011)


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


def test_subtitles_show_the_text_as_spoken_and_leave_out_what_was_not(tmp_path: Path) -> None:
    """#214: a replacement is shown as spoken, removed text and a sentence the voice failed
    on are not shown at all (D-606)."""
    source = small_pdf(tmp_path, "A short note [1].", "", "Bad line.", "", "Last line.")
    steps = [
        Replacing(
            Edit(Span(0, 8, 12), EditKind.REPLACE, "a test", "x", "notice"),
            Edit(Span(0, 12, 16), EditKind.REMOVE, "a test", "x"),
        )
    ]
    voice = FakeVoice(fail_on=lambda text: text.startswith("Bad"))
    job = run(source, tmp_path, voice, steps=steps, settings=JobSettings(subtitles=True))
    names = [path.name for path in job.written.subtitles]
    assert names == ["note - 01 note.srt", "note - 01 note.vtt", "note.srt", "note.vtt"]
    assert json.loads(job.record.read_text())["files"]["subtitles"] == names
    # the fake voice speaks 10 samples (0.42 ms) a character; the cues sit on the chunks
    assert (tmp_path / "out" / "note.vtt").read_text(encoding="utf-8") == (
        "WEBVTT\n\n"
        "00:00:02.000 --> 00:00:02.006\nA short notice.\n\n"
        "00:00:02.306 --> 00:00:02.310\nLast line.\n"
    )
    assert (tmp_path / "out" / "note.srt").read_text(encoding="utf-8") == (
        "1\n00:00:02,000 --> 00:00:02,006\nA short notice.\n\n"
        "2\n00:00:02,306 --> 00:00:02,310\nLast line.\n"
    )
    times = read_readalong(job.written.readalong)
    assert [(c.start, c.end) for c in times.chunks] == [(2.0, 2.006), (2.306, 2.31)]


def test_subtitles_are_off_unless_asked_for(tmp_path: Path) -> None:
    job = run(small_pdf(tmp_path), tmp_path, FakeVoice())
    assert job.written.subtitles == ()
    assert json.loads(job.record.read_text())["files"]["subtitles"] == []
    assert not [name for name in outputs(tmp_path) if name.endswith((".srt", ".vtt"))]


def test_existing_subtitles_are_refused_before_the_voice_is_made(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "note.vtt").write_text("mine", encoding="utf-8")
    voice = FakeVoice()
    with pytest.raises(OutputExistsError, match=r"note\.vtt"):
        run(source, tmp_path, voice, settings=JobSettings(subtitles=True))
    assert voice.made == 0
    run(source, tmp_path, voice)  # without subtitles the file is not in the way
    assert (tmp_path / "out" / "note.vtt").read_text(encoding="utf-8") == "mine"


def test_a_failed_run_with_subtitles_leaves_nothing_in_the_way_of_a_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = small_pdf(tmp_path)
    original = Path.write_text

    def full(self: Path, text: str, *args, **kwargs) -> int:  # type: ignore[no-untyped-def]
        if self.name.endswith(".readalong.json.partial"):
            raise OSError(28, "No space left on device")
        return original(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", full)
    with pytest.raises(JobError):
        run(source, tmp_path, FakeVoice(), settings=JobSettings(subtitles=True))
    # the chapter's MP3 and subtitles were in place before the read-along file failed
    # (#723): the record names them, so they are the rerun's own, not in its way
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.owned(tmp_path / "out") == set(outputs(tmp_path))
    monkeypatch.setattr(Path, "write_text", original)
    job = run(source, tmp_path, FakeVoice(), settings=JobSettings(subtitles=True))
    assert len(job.written.subtitles) == 4


def test_the_audiobook_follows_the_chosen_order(tmp_path: Path) -> None:
    """#119: the MP3 numbering, the M4B's chapter marks, the read-along file and the
    record follow the order the person chose."""
    from test_output_ffmpeg import chapters_of, ffmetadata

    voice = FakeVoice()
    job = run(PYMEDPHYS, tmp_path, voice, settings=JobSettings(chapters=(2, 0)))
    titles = {c.chapter.index: c.chapter.title for c in job.result.chapters}
    readalong = read_readalong(job.written.readalong)
    assert [c.title for c in readalong.chapters] == [titles[2], titles[0]]
    first, second = (p.name.split(" - ", 1)[-1] for p in job.written.mp3s)
    assert first.startswith(f"01 {titles[2][:9]}"), first
    assert second.startswith(f"02 {titles[0][:9]}"), second
    assert job.written.m4b is not None
    assert [title for _start, _end, title in chapters_of(ffmetadata(job.written.m4b))] == [
        titles[2],
        titles[0],
    ]
    starts = [c.start for c in readalong.chunks]
    assert starts == sorted(starts)  # one timeline, in the order heard
    record = json.loads(job.record.read_text(encoding="utf-8"))
    assert record["settings"]["chapters"] == [2, 0]
    assert [(c["index"], c["selected"]) for c in record["chapters"]][:2] == [(2, True), (0, True)]


# ---- a PDF whose text can't be read (#442 part B, AC-442.3) -----------------------------------

GLYPH_LINES = [
    "Das Buch wurde in einer Zeit geschrieben, in der die Arbeit in den Quartieren",
    "neu gedacht werden musste. Die Menschen, die dort leben, kennen ihre Nachbarn,",
]


def test_a_pdf_of_glyph_numbers_stops_before_the_voice_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """The #442 file's kind: every page is glyph numbers, so no voice is made, nothing is
    spoken, and neither the output folder nor the working folder gets a file."""
    source = tmp_path / "gemeinwesenarbeit.pdf"
    source.write_bytes(joined_pdf(*[glyph_number_pdf(GLYPH_LINES)] * 3))
    voice = FakeVoice()
    seen: list[AudioProgress] = []
    with pytest.raises(UnreadableTextError) as raised:
        run(source, tmp_path, voice, progress=seen.append)
    assert isinstance(raised.value, UnreadableFileError)  # the command line's exit 5
    assert str(raised.value) == (
        "gemeinwesenarbeit.pdf: the text of pages 1\u20133 cannot be read: the PDF's fonts "
        "give glyph numbers or wrong letters there, so the voice would read nonsense; no "
        "audiobook is made from it"
    )
    assert voice.made == 0
    assert voice.texts == []
    assert Phase.TEXT_STEPS not in {event.phase for event in seen}  # stopped right after reading
    assert outputs(tmp_path) == []
    work = tmp_path / "work"
    left = sorted(p.name for p in work.rglob("*") if p.is_file()) if work.exists() else []
    assert all(name.endswith(".lock") for name in left), left


def test_the_stop_comes_before_a_missing_voice(tmp_path: Path) -> None:
    """The person learns first that the file can't be read: setting up the voice would not
    help."""
    source = tmp_path / "glyphs.pdf"
    source.write_bytes(glyph_number_pdf(GLYPH_LINES))
    missing = replace(FakeVoice().source(), installed=lambda voice: False)
    settings = JobSettings(output_folder=tmp_path / "out")
    with pytest.raises(UnreadableTextError):
        run_audio_job(source, settings, tmp_path / "work", voice=missing)


def test_a_glyph_number_page_among_longer_plain_pages_is_voiced(tmp_path: Path) -> None:
    """Less than half of the characters: the audiobook is made, and the report (the script
    job's) names the page."""
    plain = make_pdf(
        [Text("A plain line of English text that reads well.", 72, 100 + 14 * k) for k in range(8)]
    )
    source = tmp_path / "mixed.pdf"
    source.write_bytes(joined_pdf(plain, glyph_number_pdf(GLYPH_LINES), plain))
    job = run(source, tmp_path, FakeVoice())
    assert job.spoken > 0
    assert job.written.readalong.is_file()


def plugin_steps():  # type: ignore[no-untyped-def]
    from test_cli_script import AMPERSAND

    from sci2audio.textprep import installed_steps

    return installed_steps(entry_points=[AMPERSAND])


def test_the_record_names_the_plugins_that_made_it(tmp_path: Path) -> None:
    source = small_pdf(tmp_path, "Salt & pepper are on the table.")
    run(source, tmp_path, FakeVoice(), steps=plugin_steps())
    record = json.loads((tmp_path / "work" / "audio.json").read_text(encoding="utf-8"))
    assert record["plugins"] == [{"step": "ampersand-and", "distribution": "", "version": ""}]
    assert record["version"] == 1  # an addition: the format stays version 1


def test_a_record_without_plugins_has_no_plugin_key(tmp_path: Path) -> None:
    source = small_pdf(tmp_path, "Salt & pepper are on the table.")
    run(source, tmp_path, FakeVoice())
    record = json.loads((tmp_path / "work" / "audio.json").read_text(encoding="utf-8"))
    assert "plugins" not in record
    assert "plugins" not in record["settings"]
    off = tmp_path / "off"
    settings = JobSettings(plugins=False, output_folder=off / "out")
    JobRunner(plugin_steps()).run_audio(source, settings, off / "work", voice=FakeVoice().source())
    record = json.loads((off / "work" / "audio.json").read_text(encoding="utf-8"))
    assert "plugins" not in record
    assert record["settings"]["plugins"] is False


def test_records_with_and_without_plugins_load_in_the_player(tmp_path: Path) -> None:
    """The 1.4.0 player reads named fields only, so the new key is safe both ways (#669)."""
    from sci2audio.web.player import read_audio_record

    source = small_pdf(tmp_path, "Salt & pepper are on the table.")
    run(source, tmp_path, FakeVoice(), steps=plugin_steps())
    work = tmp_path / "work"
    data = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    document_id = data["source"]["sha256"][:16]
    assert read_audio_record(work, document_id).readalong
    del data["plugins"]  # as a record made before #669
    (work / "audio.json").write_text(json.dumps(data), encoding="utf-8")
    assert read_audio_record(work, document_id).readalong
