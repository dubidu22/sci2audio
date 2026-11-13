"""Fault injection for the audio job (#10, tests.md "resume, download or any file writing"):
killed mid-run and resumed without speaking finished chunks again, no network after the
voice setup (VA-04), a full disk, the output folder or a chunk removed during the run.
Never a half-written file afterwards."""

from __future__ import annotations

import errno
import json
import shutil
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import AudioProgress, JobError, JobSettings, Phase, run_audio_job
from sci2audio.output import Ffmpeg, find_ffmpeg
from sci2audio.output import readalong as readalong_module
from sci2audio.testing import no_network
from sci2audio.voices import wav as voices_wav

UNIT = Path(__file__).resolve().parent
PYMEDPHYS = UNIT.parent / "corpus" / "papers" / "joss2022-biggs-pymedphys.pdf"


def run(folder: Path, voice: FakeVoice, **kwargs):  # type: ignore[no-untyped-def]
    settings = JobSettings(output_folder=folder / "out")
    return run_audio_job(PYMEDPHYS, settings, folder / "work", voice=voice.source(), **kwargs)


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
    from audio_fakes import FakeVoice
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
    assert len(voice.spoken) == 41 - 12
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
    assert job.spoken == 41
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
    assert len(rest.spoken) == 41 - (at - 1)


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


@pytest.mark.parametrize("at", [1, 3, 5])  # an MP3, another MP3, the M4B
def test_a_full_disk_while_encoding_leaves_no_half_file(tmp_path: Path, at: int) -> None:
    ffmpeg = FailingFfmpeg(find_ffmpeg(), fail_at=at, calls=[])
    with pytest.raises(JobError, match="No space left on device"):
        run(tmp_path, FakeVoice(), ffmpeg=ffmpeg)
    assert leftovers(tmp_path) == []
    assert not any(name.endswith(".readalong.json") for name in outputs(tmp_path))
    job = run(tmp_path, FakeVoice(), overwrite=True)  # completed files of the failed run stay
    assert job.reused == 41


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
    assert job.reused == 41


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
    assert json.loads(job.record.read_text())["chunks"]["reused"] == 41
