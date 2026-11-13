"""Fault injection for the audio job (#10, tests.md "resume, download or any file writing"):
killed mid-run and resumed without speaking finished chunks again, no network after the
voice setup (VA-04), a full disk, the output folder or a chunk removed during the run.
Never a half-written file afterwards."""

from __future__ import annotations

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
from sci2audio.output import Ffmpeg, find_ffmpeg
from sci2audio.output import readalong as readalong_module
from sci2audio.testing import no_network
from sci2audio.voices import wav as voices_wav

UNIT = Path(__file__).resolve().parent
PYMEDPHYS = UNIT.parent / "corpus" / "papers" / "joss2022-biggs-pymedphys.pdf"


def run(folder: Path, voice: FakeVoice, **kwargs):  # type: ignore[no-untyped-def]
    settings = JobSettings(output_folder=folder / "out")
    return run_audio_job(PYMEDPHYS, settings, folder / "work", voice=voice.source(), **kwargs)


def chunks() -> int:
    return chunk_count(PYMEDPHYS)


def leftovers(folder: Path) -> list[str]:
    """Partial files anywhere under the folder."""
    return [p.name for p in folder.rglob("*") if p.name.endswith((".part", ".partial"))]


def outputs(folder: Path) -> list[str]:
    out = folder / "out"
    return sorted(p.name for p in out.iterdir()) if out.exists() else []


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
            assert time.monotonic() < deadline
            time.sleep(0.05)
        child.kill()  # SIGKILL / TerminateProcess: no clean-up runs
        child.wait(timeout=60)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    assert outputs(killed) == []
    # a chunk was being written when it died: its .part file is cleared on the rerun
    stale = next((killed / "work" / "chunks").glob("*/*.wav"))
    stale.with_name(stale.name + ".part").write_bytes(b"half a chunk")

    voice = FakeVoice()
    job = run(killed, voice)
    assert len(voice.spoken) == chunks() - 12
    assert job.reused == 12
    assert leftovers(killed) == []
    whole = run(tmp_path / "uninterrupted", FakeVoice())
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
        calls[0] += 1
        if calls[0] == at:
            raise OSError(errno.ENOSPC, "No space left on device")
        real(source, target)

    monkeypatch.setattr(voices_wav.os, "replace", replace)
    voice = FakeVoice()
    with pytest.raises(JobError, match=r"No space left on device.*kept for a rerun"):
        run(tmp_path, voice)
    assert leftovers(tmp_path) == []
    assert outputs(tmp_path) == []
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
def test_a_full_disk_while_encoding_leaves_no_file_and_the_rerun_needs_no_overwrite(
    tmp_path: Path, at: int
) -> None:
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=at, calls=[])
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert ffmpeg.calls == [1] * at
    assert leftovers(tmp_path) == []
    assert outputs(tmp_path) == []  # the MP3s finished before the failure are removed too
    job = run(tmp_path, FakeVoice())  # without overwrite: nothing of the failed run is left
    assert job.reused == chunks()
    assert len(outputs(tmp_path)) == ENCODES + 1  # and the read-along file


def cancel_at(call: int, cancel: threading.Event):  # type: ignore[no-untyped-def]
    def before(n: int) -> None:
        if n == call:
            cancel.set()

    return before


@pytest.mark.parametrize("at", [2, ENCODES])  # the second MP3, the M4B (the last run)
def test_cancel_part_way_through_encoding_leaves_no_file_and_the_rerun_needs_no_overwrite(
    tmp_path: Path, at: int
) -> None:
    cancel = threading.Event()
    ffmpeg = FailingFfmpeg(find_ffmpeg(), before=cancel_at(at, cancel), calls=[])
    with pytest.raises(JobCancelledError):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg, cancel=cancel)
    assert ffmpeg.calls == [1] * at
    assert leftovers(tmp_path) == []
    assert outputs(tmp_path) == []
    voice = FakeVoice()
    job = run(tmp_path, voice)
    assert (job.reused, voice.made) == (chunks(), 0)  # every chunk was kept, the voice not loaded


def test_ctrl_c_while_encoding_leaves_no_file(tmp_path: Path) -> None:
    def interrupt(call: int) -> None:
        if call == 3:
            raise KeyboardInterrupt

    ffmpeg = FailingFfmpeg(find_ffmpeg(), before=interrupt, calls=[])
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert leftovers(tmp_path) == []
    assert outputs(tmp_path) == []
    assert run(tmp_path, FakeVoice()).reused == chunks()


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
    assert outputs(tmp_path) == [fourth]  # the three MP3s of this run are gone, theirs stays
    assert theirs.read_bytes() == b"theirs"
    assert leftovers(tmp_path) == []


def test_a_rerun_that_fails_while_encoding_leaves_no_old_record(tmp_path: Path) -> None:
    first = run(tmp_path, FakeVoice())
    assert first.record.exists()
    assert first.document_file.exists()
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=3, calls=[])
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg, overwrite=True)
    # the records named files this rerun replaced (MP3s 1 and 2) or vouched for a set
    # that is now mixed: they are gone, as is the read-along file (D-119)
    assert not first.record.exists()
    assert not first.document_file.exists()
    assert not any(name.endswith(".readalong.json") for name in outputs(tmp_path))
    job = run(tmp_path, FakeVoice(), overwrite=True)
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
    job = run(tmp_path, FakeVoice())
    assert job.reused == chunks()


def test_a_chunk_removed_before_encoding_gives_a_clear_message(tmp_path: Path) -> None:
    def progress(event: AudioProgress) -> None:
        if event.phase is Phase.ENCODING:
            next((tmp_path / "work" / "chunks").glob("*/*.wav")).unlink()

    with pytest.raises(JobError, match=r"audio chunk is missing.*run the job again"):
        run(tmp_path, FakeVoice(), progress=progress)
    assert outputs(tmp_path) == []
    assert leftovers(tmp_path) == []
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
