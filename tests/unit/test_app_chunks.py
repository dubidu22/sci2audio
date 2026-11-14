"""The chunk cache (D-155, D-156, D-158), the working-folder lock (D-161) and the default
folders (D-164)."""

from __future__ import annotations

import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.app import (
    JobBusyError,
    chunk_key,
    clean_work_folder,
    default_models_folder,
    default_work_folder,
    kokoro_voice,
)
from sci2audio.app import config as config_module
from sci2audio.app.chunks import cache_size, chunk_file, is_finished, remove_partials
from sci2audio.app.lock import work_folder_lock
from sci2audio.core import AudioChunk, Span
from sci2audio.voices import DEFAULT_VOICE, ENGLISH_VOICES, VOICES


def write_wav(path: Path, frames: int = 100, channels: int = 1, width: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(24000)
        out.writeframes(b"\x01\x00" * frames * channels * (width // 2))
    return path


def test_a_complete_mono_16_bit_wav_is_finished(tmp_path: Path) -> None:
    assert is_finished(write_wav(tmp_path / "a.wav"))
    assert is_finished(write_wav(tmp_path / "empty.wav", frames=0))


def test_a_missing_cut_short_or_other_wav_is_not_finished(tmp_path: Path) -> None:
    assert not is_finished(tmp_path / "missing.wav")
    assert not is_finished(write_wav(tmp_path / "stereo.wav", channels=2))
    assert not is_finished(write_wav(tmp_path / "wide.wav", width=4))
    cut = write_wav(tmp_path / "cut.wav", frames=1000)
    cut.write_bytes(cut.read_bytes()[:-10])  # a power cut after the rename
    assert not is_finished(cut)
    (tmp_path / "junk.wav").write_bytes(b"not audio")
    assert not is_finished(tmp_path / "junk.wav")
    (tmp_path / "folder.wav").mkdir()
    assert not is_finished(tmp_path / "folder.wav")


def test_partial_files_of_a_killed_run_are_removed(tmp_path: Path) -> None:
    key = chunk_key("x", "v", 1.0, "e", "1")
    done = write_wav(tmp_path / chunk_file(key))
    part = done.with_name(done.name + ".part")
    part.write_bytes(b"half")
    assert remove_partials(tmp_path) == 1
    assert not part.exists()
    assert done.exists()
    assert remove_partials(tmp_path / "none") == 0


def test_cleaning_removes_only_the_chunk_cache(tmp_path: Path) -> None:
    write_wav(tmp_path / chunk_file(chunk_key("x", "v", 1.0, "e", "1")))
    (tmp_path / "audio.json").write_text("{}")
    (tmp_path / "document.json").write_text("{}")
    size = cache_size(tmp_path)
    assert size > 0
    assert clean_work_folder(tmp_path) == size
    # the lock file it held stays, like after every job (D-161)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["audio.json", "document.json", "job.lock"]
    assert clean_work_folder(tmp_path) == 0
    assert clean_work_folder(tmp_path / "none") == 0
    assert not (tmp_path / "none").exists()  # cleaning a folder that is not there makes none


def test_cleaning_while_a_job_holds_the_lock_is_refused_and_removes_nothing(
    tmp_path: Path,
) -> None:
    chunk = write_wav(tmp_path / chunk_file(chunk_key("x", "v", 1.0, "e", "1")))
    with work_folder_lock(tmp_path), pytest.raises(JobBusyError, match="another sci2audio job"):
        clean_work_folder(tmp_path)
    assert chunk.exists()
    assert clean_work_folder(tmp_path) > 0  # free again: it cleans
    assert not chunk.exists()


@given(
    st.text(min_size=1),
    st.sampled_from([v.id for v in ENGLISH_VOICES]),
    st.floats(0.5, 2.0),
    st.text(min_size=1, max_size=20),
)
def test_keys_are_deterministic_and_make_valid_chunk_files(
    text: str, voice: str, speed: float, version: str
) -> None:
    key = chunk_key(text, voice, speed, "kokoro", version)
    assert key == chunk_key(text, voice, speed, "kokoro", version)
    assert key != chunk_key(text + " ", voice, speed, "kokoro", version)
    AudioChunk(Span(0, 0, 0), chunk_file(key), 0.0)  # a valid relative path inside the job


def test_the_lock_keeps_a_second_job_out_and_is_free_again_afterwards(tmp_path: Path) -> None:
    with work_folder_lock(tmp_path / "work"):
        with (
            pytest.raises(JobBusyError, match="another sci2audio job"),
            work_folder_lock(tmp_path / "work"),
        ):
            pass
        with work_folder_lock(tmp_path / "other"):  # another folder is free
            pass
    with work_folder_lock(tmp_path / "work"):  # released
        pass


def test_another_process_holding_the_lock_keeps_the_job_out(tmp_path: Path) -> None:
    work = tmp_path / "work"
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from sci2audio.app.lock import work_folder_lock\n"
        "with work_folder_lock(Path(sys.argv[1])):\n"
        "    print('locked', flush=True)\n"
        "    sys.stdin.readline()\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(work)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(JobBusyError), work_folder_lock(work):
            pass
        # nor may the cache be cleaned under that job (D-226)
        chunk = write_wav(work / chunk_file(chunk_key("x", "v", 1.0, "e", "1")))
        with pytest.raises(JobBusyError):
            clean_work_folder(work)
        assert chunk.exists()
        child.kill()  # killed outright: the system frees the lock
        child.wait(timeout=30)
        # Linux and macOS free it at once; Windows "depends upon available system
        # resources" (msvcrt.locking docs): the lock itself waits WINDOWS_GRACE for it
        deadline = time.monotonic() + 15
        while True:
            try:
                with work_folder_lock(work):
                    break
            except JobBusyError:
                assert sys.platform == "win32", "the lock outlived its process"
                assert time.monotonic() < deadline, "the lock was not freed in 15 s"
                time.sleep(0.1)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_the_default_folders_come_from_platformdirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config_module.platformdirs, "user_data_path", lambda *a, **k: tmp_path / "data"
    )
    monkeypatch.setattr(
        config_module.platformdirs, "user_cache_path", lambda *a, **k: tmp_path / "cache"
    )
    assert default_models_folder() == tmp_path / "data" / "models"
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7 a")
    work = default_work_folder(source)
    assert work.parent == tmp_path / "cache" / "jobs"
    assert len(work.name) == 16
    copy = tmp_path / "moved.pdf"
    copy.write_bytes(source.read_bytes())
    assert default_work_folder(copy) == work  # the same file gets the same folder
    copy.write_bytes(b"%PDF-1.7 b")
    assert default_work_folder(copy) != work


def test_the_kokoro_source_names_its_version_and_loads_nothing(tmp_path: Path) -> None:
    source = kokoro_voice(tmp_path)
    assert source.engine == "kokoro"
    assert source.version.startswith("kokoro-82m@f3ff3571791e;kokoro ")
    assert "misaki " in source.version
    assert source.default_voice == DEFAULT_VOICE
    assert set(source.voices) == {v.id for v in VOICES}
    # English versions stay as they were before the German voice came (D-471)
    assert all(source.version_of(v.id) == source.version for v in ENGLISH_VOICES)
    german = source.version_of("dm_thorsten")
    assert german.startswith("kokoro-de-thorsten@734e593d320a;kokoro ")
    assert "espeakng-loader " in german
    check = (
        "import sys\nfrom pathlib import Path\nfrom sci2audio.app import kokoro_voice\n"
        "kokoro_voice(Path('models'))\nprint('torch' in sys.modules, 'kokoro' in sys.modules)"
    )
    done = subprocess.run([sys.executable, "-c", check], capture_output=True, text=True, check=True)
    assert done.stdout.split() == ["False", "False"]  # nothing is loaded until a chunk is due
