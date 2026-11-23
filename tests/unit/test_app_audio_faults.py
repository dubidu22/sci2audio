"""Fault injection for the audio job (#10, tests.md "resume, download or any file writing"):
killed mid-run and resumed without speaking finished chunks again, no network after the
voice setup (VA-04), a full disk, the output folder or a chunk removed during the run.
Never a half-written file afterwards."""

from __future__ import annotations

import dataclasses
import errno
import json
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import wave
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from audio_fakes import FakeVoice, chunk_count
from output_helpers import NEWER, refuse_newer_names

from sci2audio.app import (
    AudioProgress,
    JobCancelledError,
    JobError,
    JobSettings,
    OutputExistsError,
    Phase,
    clean_work_folder,
    run_audio_job,
)
from sci2audio.app import audio as audio_module
from sci2audio.app.audio import JOB_OUTPUT
from sci2audio.app.playable import read_record
from sci2audio.output import Ffmpeg, OutputSettings, find_ffmpeg, read_readalong
from sci2audio.output import readalong as readalong_module
from sci2audio.testing import no_network
from sci2audio.voices import wav as voices_wav

UNIT = Path(__file__).resolve().parent
PYMEDPHYS = UNIT.parent / "corpus" / "papers" / "joss2022-biggs-pymedphys.pdf"


def run(folder: Path, voice: FakeVoice, **kwargs):  # type: ignore[no-untyped-def]
    settings = JobSettings(output_folder=folder / "out")
    kwargs.setdefault("output_settings", OutputSettings())  # the whole book, as the CLI
    return run_audio_job(PYMEDPHYS, settings, folder / "work", voice=voice.source(), **kwargs)


def chunks() -> int:
    return chunk_count(PYMEDPHYS)


def leftovers(folder: Path) -> list[str]:
    """Partial files anywhere under the folder."""
    return [p.name for p in folder.rglob("*") if p.name.endswith((".part", ".partial"))]


def outputs(folder: Path) -> list[str]:
    out = folder / "out"
    return sorted(p.name for p in out.iterdir()) if out.exists() else []


def whole_chapters(folder: Path) -> list[str]:
    """The MP3s a stopped job left, after checking they are whole chapters (#723): every
    file in the output folder is one the job's chapter record names with its size and
    SHA-256, the read-along file lists exactly these MP3s, and no partial file is left."""
    out, record = folder / "out", read_record(folder / "work")
    assert leftovers(folder) == []
    if not outputs(folder):
        return []
    assert record is not None
    assert not record.complete
    assert record.owned(out) == set(outputs(folder))
    mp3s = [name for name in outputs(folder) if name.endswith(".mp3")]
    readalong = [name for name in outputs(folder) if name.endswith(".readalong.json")]
    assert len(readalong) == 1
    assert [c.mp3 for c in read_readalong(out / readalong[0]).chapters] == mp3s
    assert [f.name for c in record.chapters for f in c.files if f.name.endswith(".mp3")] == mp3s
    return mp3s


KILLED_JOB = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    from audio_fakes import FakeVoice, chunk_count
    from sci2audio.app import JobSettings, run_audio_job

    folder, stop_after = Path(sys.argv[2]), int(sys.argv[3])
    voice = FakeVoice(marker=folder / "hanging", hang_on=lambda text: False)
    voice.hang_on = lambda text: len(voice.spoken) >= stop_after
    run_audio_job(
        Path(sys.argv[4]), JobSettings(output_folder=folder / "out"), folder / "work",
        voice=voice.source(),
    )
    """
)


def test_a_job_killed_mid_run_resumes_without_speaking_finished_chunks(tmp_path: Path) -> None:
    killed = tmp_path / "killed"
    killed.mkdir()
    child = subprocess.Popen(
        [sys.executable, "-c", KILLED_JOB, str(UNIT), str(killed), "12", str(PYMEDPHYS)]
    )
    try:
        deadline = time.monotonic() + 120
        while not (killed / "hanging").exists():
            assert child.poll() is None, "the job ended before it was killed"
            # clock-bound: the wait loop's way out after 120 s; what it waits for is far quicker
            assert time.monotonic() < deadline
            time.sleep(0.05)
        child.kill()  # SIGKILL / TerminateProcess: no clean-up runs
        child.wait(timeout=60)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    # #723: the chapters spoken before the kill are whole and playable, nothing else
    finished = whole_chapters(killed)
    assert finished
    # a chunk was being written when it died: its .part file is cleared on the rerun
    stale = next((killed / "work" / "chunks").glob("*/*.wav"))
    stale.with_name(stale.name + ".part").write_bytes(b"half a chunk")
    before = {name: (killed / "out" / name).stat().st_mtime_ns for name in finished}

    voice = FakeVoice()
    job = run(killed, voice, output_settings=JOB_OUTPUT)  # the killed job's settings
    assert len(voice.spoken) == chunks() - 12
    assert job.reused == 12
    assert leftovers(killed) == []
    # the finished chapters were taken as they were, not encoded again
    assert {name: (killed / "out" / name).stat().st_mtime_ns for name in finished} == before
    whole = run(tmp_path / "uninterrupted", FakeVoice(), output_settings=JOB_OUTPUT)
    assert job.written.readalong.read_text() == whole.written.readalong.read_text()
    assert [p.read_bytes() for p in job.written.mp3s] == [
        p.read_bytes() for p in whole.written.mp3s
    ]


def test_the_whole_job_runs_with_the_network_blocked(tmp_path: Path) -> None:
    with no_network():
        job = run(tmp_path, FakeVoice())
    assert job.spoken == chunks() > 12
    assert job.written.m4b is not None
    assert job.written.m4b.exists()


@pytest.mark.parametrize("at", [1, 7])
def test_a_full_disk_while_speaking_fails_cleanly_and_keeps_finished_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at: int
) -> None:
    calls = [0]
    real = voices_wav.os.replace

    def replace(source: str, target: str) -> None:
        if str(target).endswith(".wav"):  # the chunks only; the cover is written before
            calls[0] += 1
            if calls[0] == at:
                raise OSError(errno.ENOSPC, "No space left on device")
        real(source, target)

    monkeypatch.setattr(voices_wav.os, "replace", replace)
    voice = FakeVoice()
    with pytest.raises(JobError, match=r"No space left on device.*kept for a rerun"):
        run(tmp_path, voice)
    assert leftovers(tmp_path) == []
    whole_chapters(tmp_path)  # the chapters spoken before it, if any, are whole (#723)
    assert voice.released == 1
    monkeypatch.undo()
    rest = FakeVoice()
    job = run(tmp_path, rest)
    assert job.reused == at - 1
    assert len(rest.spoken) == chunks() - (at - 1)


@dataclass(frozen=True)
class FailingFfmpeg(Ffmpeg):
    """The real ffmpeg, made to fail on its `fail_at`-th run like a full disk would, or
    to run `before` first."""

    fail_at: int = 0
    before: object = None
    calls: list[int] | None = None

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        assert self.calls is not None
        self.calls.append(1)
        if callable(self.before):
            self.before(len(self.calls))
        if len(self.calls) == self.fail_at:
            for _ in feed:  # write part of the file, then fail
                break
            Path(args[-1]).write_bytes(b"half an mp3")
            raise OSError(errno.ENOSPC, "No space left on device", args[-1])
        return super().run(args, feed)


ENCODES = 5  # ffmpeg runs for pymedphys: 4 MP3s, then the M4B


@pytest.mark.parametrize("at", [1, 3, ENCODES])  # an MP3, another MP3, the M4B
def test_a_full_disk_while_encoding_keeps_the_whole_chapters_and_the_rerun_needs_no_overwrite(
    tmp_path: Path, at: int
) -> None:
    """#723: the chapters finished before the failure stay, whole and recorded (they were
    playable); the rerun takes them as they are and writes the rest."""
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=at, calls=[])
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert ffmpeg.calls == [1] * at
    assert len(whole_chapters(tmp_path)) == min(at - 1, ENCODES - 1)
    again, voice = FailingFfmpeg(find_ffmpeg(), calls=[]), FakeVoice()
    job = run(tmp_path, voice, ffmpeg=again)  # without overwrite: they are its own
    assert job.reused + len(voice.spoken) == chunks()  # nothing spoken twice
    assert len(again.calls) == ENCODES - min(at - 1, ENCODES - 1)
    assert len(outputs(tmp_path)) == ENCODES + 1  # and the read-along file


def cancel_at(call: int, cancel: threading.Event):  # type: ignore[no-untyped-def]
    def before(n: int) -> None:
        if n == call:
            cancel.set()

    return before


@pytest.mark.parametrize("at", [2, ENCODES])  # the second MP3, the M4B (the last run)
def test_cancel_part_way_through_encoding_keeps_the_whole_chapters_and_the_rerun_needs_no_overwrite(
    tmp_path: Path, at: int
) -> None:
    cancel = threading.Event()
    ffmpeg = FailingFfmpeg(find_ffmpeg(), before=cancel_at(at, cancel), calls=[])
    with pytest.raises(JobCancelledError):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg, cancel=cancel)
    assert ffmpeg.calls == [1] * at
    assert len(whole_chapters(tmp_path)) == at - 1  # #723: the chapters before it stay
    voice = FakeVoice()
    job = run(tmp_path, voice)
    assert job.reused + len(voice.spoken) == chunks()  # every chunk spoken was kept
    if at == ENCODES:  # all was spoken: the voice is not even loaded
        assert (job.reused, voice.made) == (chunks(), 0)


def test_ctrl_c_while_encoding_leaves_only_whole_chapters(tmp_path: Path) -> None:
    def interrupt(call: int) -> None:
        if call == 3:
            raise KeyboardInterrupt

    ffmpeg = FailingFfmpeg(find_ffmpeg(), before=interrupt, calls=[])
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert len(whole_chapters(tmp_path)) == 2  # #723: chapters 1 and 2 stay, whole
    voice = FakeVoice()
    assert run(tmp_path, voice).reused + len(voice.spoken) == chunks()


def test_a_failed_encoding_never_removes_a_file_that_came_from_elsewhere(tmp_path: Path) -> None:
    whole = run(tmp_path / "names", FakeVoice())
    fourth = whole.written.mp3s[3].name
    theirs = tmp_path / "out" / fourth

    def appear(call: int) -> None:
        if call == 2:  # another program puts a file where the fourth MP3 goes
            theirs.write_bytes(b"theirs")

    ffmpeg = FailingFfmpeg(find_ffmpeg(), before=appear, calls=[])
    with pytest.raises(OutputExistsError, match=re.escape(fourth)):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert theirs.read_bytes() == b"theirs"
    assert leftovers(tmp_path) == []
    # #723: the three chapters of this run stay, whole and recorded; theirs is not recorded
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.owned(tmp_path / "out") == set(outputs(tmp_path)) - {fourth}
    assert [name for name in outputs(tmp_path) if name.endswith(".mp3")] == [
        p.name for p in whole.written.mp3s
    ]


def test_a_rerun_that_fails_while_encoding_leaves_no_old_record(tmp_path: Path) -> None:
    first = run(tmp_path, FakeVoice())
    assert first.record.exists()
    assert first.document_file.exists()
    first.document_file.write_text("the old run's document", encoding="utf-8")
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=3, calls=[])
    other = OutputSettings(mp3_bitrate="96k")  # every file differs: none is taken as it is
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg, overwrite=True, output_settings=other)
    # the records named files this rerun replaced (MP3s 1 and 2) or vouched for a set
    # that is now mixed: they are gone (D-119); the read-along file lists only the two
    # chapters this rerun finished (#723); the laid-out document is this rerun's, written
    # before its first chapter's files, so a page reads along in them (#724)
    assert not first.record.exists()
    clean = run(tmp_path / "clean", FakeVoice(), output_settings=other)
    assert first.document_file.read_bytes() == clean.document_file.read_bytes()
    readalong = read_readalong(first.written.readalong)
    assert [c.mp3 for c in readalong.chapters] == [p.name for p in first.written.mp3s[:2]]
    record = read_record(tmp_path / "work")
    assert record is not None
    assert [c.number for c in record.chapters] == [1, 2]
    job = run(tmp_path, FakeVoice(), overwrite=True, output_settings=other)
    assert job.record.exists()
    assert job.reused == chunks()


def test_cached_chunks_at_different_sample_rates_say_to_clean_the_working_folder(
    tmp_path: Path,
) -> None:
    run(tmp_path, FakeVoice())
    chunk = next((tmp_path / "work" / "chunks").glob("*/*.wav"))
    with wave.open(str(chunk), "rb") as audio:
        frames = audio.readframes(audio.getnframes())
    with wave.open(str(chunk), "wb") as audio:  # a complete chunk, at another rate
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(frames)
    message = r"different sample rates \(\[22050, 24000\] Hz\).*clean the working folder"
    for _ in range(2):  # a plain rerun gives the same answer, not "run it again"
        with pytest.raises(JobError, match=message):
            run(tmp_path, FakeVoice(), overwrite=True)
    clean_work_folder(tmp_path / "work")
    voice = FakeVoice()
    assert run(tmp_path, voice, overwrite=True).spoken == chunks()


def test_a_full_disk_while_writing_the_read_along_file_leaves_no_half_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(data: object) -> str:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(readalong_module, "to_json", full)
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice())
    assert leftovers(tmp_path) == []
    assert not any(name.endswith(".readalong.json") for name in outputs(tmp_path))


def test_the_output_folder_removed_during_the_run_gives_a_clear_message(tmp_path: Path) -> None:
    def remove(call: int) -> None:
        if call == 2:
            shutil.rmtree(tmp_path / "out")

    ffmpeg = FailingFfmpeg(find_ffmpeg(), before=remove, calls=[])
    with pytest.raises(JobError, match="output folder out was removed during the run"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert not (tmp_path / "out").exists()
    assert leftovers(tmp_path) == []
    # the job stopped at the second chapter (#723): what it had spoken is kept
    voice = FakeVoice()
    job = run(tmp_path, voice)
    assert job.reused + len(voice.spoken) == chunks()
    assert job.reused > 0


def test_a_chunk_removed_before_encoding_gives_a_clear_message(tmp_path: Path) -> None:
    def progress(event: AudioProgress) -> None:
        if event.phase is Phase.ENCODING:
            next((tmp_path / "work" / "chunks").glob("*/*.wav")).unlink()

    # the chapters are written by then (#723); the M4B is the file that needs the chunk
    with pytest.raises(JobError, match=r"audio chunk was removed.*run the job again"):
        run(tmp_path, FakeVoice(), progress=progress)
    assert not any(name.endswith(".m4b") for name in outputs(tmp_path))
    assert len(whole_chapters(tmp_path)) == ENCODES - 1
    voice = FakeVoice()
    run(tmp_path, voice)
    assert len(voice.spoken) == 1  # only the removed chunk is spoken again


def test_records_are_written_last_and_a_failed_record_says_the_audiobook_is_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sci2audio.app import audio as audio_module

    def full(texts: object, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(audio_module, "write_texts", full)
    with pytest.raises(JobError, match="audiobook is written, but its record could not be"):
        run(tmp_path, FakeVoice())
    assert any(name.endswith(".m4b") for name in outputs(tmp_path))
    assert not (tmp_path / "work" / "audio.json").exists()
    monkeypatch.undo()
    job = run(tmp_path, FakeVoice(), overwrite=True)
    assert json.loads(job.record.read_text())["chunks"]["reused"] == chunks()


# ---- a name the Mac refuses (#493, CRIT-02) ------------------------------------------------


def newer_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """The book's title holds a character newer than an older Mac's Unicode table."""
    real = audio_module.book_info
    monkeypatch.setattr(
        audio_module,
        "book_info",
        lambda document: dataclasses.replace(real(document), title=f"{NEWER} PyMedPhys"),
    )


def test_a_refused_book_name_is_written_under_the_retried_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    newer_title(monkeypatch)
    refuse_newer_names(monkeypatch)
    job = run(tmp_path, FakeVoice())
    assert job.written.readalong.name == "PyMedPhys.readalong.json"
    assert all(NEWER not in name for name in outputs(tmp_path))
    assert len(outputs(tmp_path)) == ENCODES + 1
    record = json.loads(job.record.read_text(encoding="utf-8"))
    assert record["files"]["readalong"] == "PyMedPhys.readalong.json"


def test_the_check_before_speech_names_the_retried_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The person's own file under the retried name: refused before any speech (D-163),
    named in the refusal, and kept byte for byte."""
    newer_title(monkeypatch)
    refuse_newer_names(monkeypatch)
    out = tmp_path / "out"
    out.mkdir()
    (out / "PyMedPhys.m4b").write_bytes(b"the person's own file")
    voice = FakeVoice()
    with pytest.raises(OutputExistsError, match=r"PyMedPhys\.m4b"):
        run(tmp_path, voice)
    assert voice.made == 0
    assert (out / "PyMedPhys.m4b").read_bytes() == b"the person's own file"
    assert outputs(tmp_path) == ["PyMedPhys.m4b"]


def test_a_failed_run_keeps_its_whole_chapters_under_retried_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The output folder does not exist before the run: its names are tried once it is made,
    so the files this run put in place, and recorded, are under the names written."""
    newer_title(monkeypatch)
    refuse_newer_names(monkeypatch)
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=3, calls=[])
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    # #723: the two chapters before it stay, under the retried names, and are recorded
    assert len(whole_chapters(tmp_path)) == 2


# ---- chapter by chapter (#723, LW-01) ------------------------------------------------------

BOOK = "\n\n".join(
    f"# {t}\n\nThe chapter {t} starts here. It ends with {t}." for t in ("Alpha", "Beta", "Gamma")
)
BOOK_CHUNKS = 9  # three chunks a chapter: the title and two sentences


def book_run(folder: Path, voice: FakeVoice, **kwargs):  # type: ignore[no-untyped-def]
    """The three-chapter Markdown book under the job's own settings (no M4B)."""
    source = folder / "in" / "book.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(BOOK, encoding="utf-8")
    settings = JobSettings(output_folder=folder / "out")
    return run_audio_job(source, settings, folder / "work", voice=voice.source(), **kwargs)


STOPPED_JOB = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    from audio_fakes import FakeVoice
    from sci2audio.app import JobSettings, run_audio_job
    from sci2audio.output import Ffmpeg, find_ffmpeg
    from sci2audio.output import write

    folder, how, at = Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    marker = folder / "hanging"

    def hang():
        marker.write_text(how)
        while True:
            time.sleep(1)

    voice = FakeVoice(marker=marker, hang_on=lambda text: how == "speaking" and at in text)

    class Hanging(Ffmpeg):
        calls = 0

        def run(self, args, feed=()):
            Hanging.calls += 1
            if how == "encoding" and Hanging.calls == int(at):
                for _ in feed:  # part of the chapter is written, then it hangs
                    break
                Path(args[-1]).write_bytes(b"half an mp3")
                hang()
            return super().run(args, feed)

    commit = write._commit
    name, _, nth = at.partition("#")
    seen = []

    def _commit(partial, target, overwrite):
        if target.name.endswith(name):
            seen.append(target.name)
        if how == "after-rename" and len(seen) == int(nth or 1) and target.name.endswith(name):
            commit(partial, target, overwrite)
            hang()
        if how == "before-rename" and len(seen) == int(nth or 1) and target.name.endswith(name):
            hang()
        commit(partial, target, overwrite)

    write._commit = _commit
    from sci2audio.app import audio
    document = audio._write_document

    def _write_document(work, laid_out):
        document(work, laid_out)
        if how == "after-document":
            hang()

    audio._write_document = _write_document
    source = folder / "in" / "book.md"
    source.parent.mkdir()
    source.write_text(sys.argv[5], encoding="utf-8")
    run_audio_job(
        source, JobSettings(output_folder=folder / "out"), folder / "work",
        voice=voice.source(), ffmpeg=Hanging(find_ffmpeg()),
    )
    """
)


def kill_while(folder: Path, how: str, at: str) -> None:
    """Run the book's job in another process and kill it outright (SIGKILL, no clean-up)
    while it is `how`: speaking a chunk with `at` in it, running ffmpeg the `at`-th time,
    or putting the file ending in `at` in place (before or after the rename; `name#n`: the
    n-th time a file ending in `name` is put in place); "after-document": once the laid-out
    document is written (#724)."""
    folder.mkdir()
    child = subprocess.Popen(
        [sys.executable, "-c", STOPPED_JOB, str(UNIT), str(folder), how, at, BOOK]
    )
    try:
        deadline = time.monotonic() + 120
        while not (folder / "hanging").exists():
            assert child.poll() is None, "the job ended before it was killed"
            # clock-bound: the wait loop's way out after 120 s; what it waits for is far quicker
            assert time.monotonic() < deadline
            time.sleep(0.05)
        child.kill()
        child.wait(timeout=60)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


class Encodes(Ffmpeg):
    """The real ffmpeg, noting the name of each file it writes."""

    def __init__(self) -> None:
        super().__init__(find_ffmpeg())
        object.__setattr__(self, "names", [])

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        self.names.append(Path(args[-1]).name)  # type: ignore[attr-defined]
        return super().run(args, feed)


def resumed_like_an_uninterrupted_run(tmp_path: Path, folder: Path, kept: list[str]) -> FakeVoice:
    """Resume `folder`'s job: the chapters `kept` are taken as they are (neither spoken nor
    encoded again), nothing is left half-written, and every file is byte-equal to a run
    that was never stopped."""
    before = {name: (folder / "out" / name).stat().st_mtime_ns for name in kept}
    voice, ffmpeg = FakeVoice(), Encodes()
    job = book_run(folder, voice, ffmpeg=ffmpeg)
    assert leftovers(folder) == []
    assert not any(n.endswith(tuple(kept)) for n in ffmpeg.names)  # type: ignore[attr-defined]
    assert {name: (folder / "out" / name).stat().st_mtime_ns for name in kept} == before
    assert job.reused + len(voice.spoken) == BOOK_CHUNKS
    whole = book_run(tmp_path / "uninterrupted", FakeVoice())
    assert outputs(folder) == outputs(tmp_path / "uninterrupted")
    for name in outputs(folder):
        assert (folder / "out" / name).read_bytes() == (
            tmp_path / "uninterrupted" / "out" / name
        ).read_bytes(), name
    assert job.written.readalong.read_text() == whole.written.readalong.read_text()
    record = read_record(folder / "work")
    assert record is not None
    assert record.complete
    assert record.pending == ()
    return voice


def test_a_job_killed_mid_chapter_leaves_whole_chapters_and_resumes(tmp_path: Path) -> None:
    killed = tmp_path / "killed"
    kill_while(killed, "speaking", "It ends with Beta.")  # the second chapter's last chunk
    assert whole_chapters(killed) == ["book - 01 Alpha.mp3"]
    voice = resumed_like_an_uninterrupted_run(tmp_path, killed, ["book - 01 Alpha.mp3"])
    # only the chunk it died on and the third chapter are spoken
    assert len(voice.spoken) == 1 + 3


def test_a_job_killed_while_a_chapter_is_encoded_resumes_and_leaves_no_partial(
    tmp_path: Path,
) -> None:
    killed = tmp_path / "killed"
    kill_while(killed, "encoding", "2")  # ffmpeg hangs on the second chapter's MP3
    # the half-written MP3 is under its hidden temporary name only
    assert [p.name for p in (killed / "out").glob(".*.partial")] == [".book - 02 Beta.mp3.partial"]
    assert [n for n in outputs(killed) if not n.startswith(".")] == [
        "book - 01 Alpha.mp3",
        "book.readalong.json",
    ]
    record = read_record(killed / "work")
    assert record is not None
    assert [c.number for c in record.chapters] == [1]
    resumed_like_an_uninterrupted_run(tmp_path, killed, ["book - 01 Alpha.mp3"])


@pytest.mark.parametrize("when", ["before-rename", "after-rename"])
def test_a_kill_between_vouching_and_renaming_resumes_cleanly(tmp_path: Path, when: str) -> None:
    """The record names a file before it is put in place (`pending`): killed before the
    rename, the file is not there; after it, the file is there and the record names it, but
    its chapter is not complete. Either way the resume replaces it without `overwrite`."""
    killed = tmp_path / "killed"
    kill_while(killed, when, "02 Beta.mp3")
    record = read_record(killed / "work")
    assert record is not None
    assert [c.number for c in record.chapters] == [1]
    assert [f.name for f in record.pending] == ["book - 02 Beta.mp3"]
    assert ((killed / "out" / "book - 02 Beta.mp3").exists()) == (when == "after-rename")
    assert record.owned(killed / "out") == {n for n in outputs(killed) if not n.startswith(".")}
    resumed_like_an_uninterrupted_run(tmp_path, killed, ["book - 01 Alpha.mp3"])


@pytest.mark.parametrize("when", ["before-rename", "after-rename"])
@pytest.mark.parametrize("nth", [2, 3])
def test_a_kill_while_the_readalong_file_is_replaced_resumes_cleanly(
    tmp_path: Path, when: str, nth: int
) -> None:
    """The read-along file is replaced after every chapter. Until the new one is in place
    the record still names the old one, so a kill on either side of the rename leaves a
    file the resume takes as its own, without `overwrite`."""
    killed = tmp_path / "killed"
    kill_while(killed, when, f"readalong.json#{nth}")
    record = read_record(killed / "work")
    assert record is not None
    assert [c.number for c in record.chapters] == list(range(1, nth))
    assert record.owned(killed / "out") == {n for n in outputs(killed) if not n.startswith(".")}
    kept = ["book - 01 Alpha.mp3", "book - 02 Beta.mp3"][: nth - 1]
    resumed_like_an_uninterrupted_run(tmp_path, killed, kept)


def test_a_kill_after_the_document_is_written_resumes_without_overwrite(tmp_path: Path) -> None:
    """The laid-out document is written just before the first chapter's files are put in
    place (#724, D-902). Killed right after it, no file of this run is in the output folder
    yet and no old record vouches for one: the resume needs no `overwrite` and ends like a
    run that was never stopped."""
    killed = tmp_path / "killed"
    kill_while(killed, "after-document", "")
    work = killed / "work"
    assert (work / "document.json").is_file()
    assert not (work / "audio.json").exists()
    assert outputs(killed) == []
    voice = resumed_like_an_uninterrupted_run(tmp_path, killed, [])
    # the first chapter was spoken before the kill: the resume takes it from the cache
    assert len(voice.spoken) == BOOK_CHUNKS - 3


def test_a_full_disk_while_a_chapter_is_encoded_keeps_the_chapters_before_it(
    tmp_path: Path,
) -> None:
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=2, calls=[])
    voice = FakeVoice()
    with pytest.raises(JobError, match="No space left on device"):
        book_run(tmp_path, voice, ffmpeg=ffmpeg)
    assert whole_chapters(tmp_path) == ["book - 01 Alpha.mp3"]
    # the job stopped there: the third chapter was never spoken
    assert not any("Gamma" in text for text in voice.spoken)
    assert voice.released == 1
    resumed_like_an_uninterrupted_run(tmp_path, tmp_path, ["book - 01 Alpha.mp3"])


def test_the_output_folder_removed_after_a_chapter_fails_with_a_message(tmp_path: Path) -> None:
    def progress(event: AudioProgress) -> None:
        if event.ready == 0:  # the first chapter is playable: the folder goes
            shutil.rmtree(tmp_path / "out")

    voice = FakeVoice()
    with pytest.raises(JobError, match="output folder out was removed during the run"):
        book_run(tmp_path, voice, progress=progress)
    assert not (tmp_path / "out").exists()
    assert leftovers(tmp_path) == []
    assert not any("Gamma" in text for text in voice.spoken)
    # what it had spoken is kept; the rerun writes every chapter again
    again = FakeVoice()
    job = book_run(tmp_path, again)
    assert job.reused + len(again.spoken) == BOOK_CHUNKS
    assert job.reused >= 6
    assert len(job.written.mp3s) == 3
