"""`app.files`: each write has its own temporary name, so writers of one file never clash (#778)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from sci2audio.app import files

ROUNDS = 300


def test_two_threads_writing_the_same_file_never_fail_each_other(tmp_path: Path) -> None:
    target = tmp_path / "position.json"
    texts = {"a": "A" * 5000 + "\n", "b": "B" * 5000 + "\n"}
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def writer(text: str) -> None:
        barrier.wait()
        for _ in range(ROUNDS):
            try:
                files.write_texts({target: text}, overwrite=True)
            except BaseException as error:
                errors.append(error)

    threads = [threading.Thread(target=writer, args=(text,)) for text in texts.values()]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    assert errors == []
    assert target.read_text(encoding="utf-8") in texts.values()  # complete, from one writer
    assert [p.name for p in tmp_path.iterdir()] == [target.name]  # no temporary file left


def test_every_write_gets_its_own_temporary_name(tmp_path: Path) -> None:
    target = tmp_path / "markers.json"
    names = {files.partial_path(target) for _ in range(50)}
    assert len(names) == 50
    assert all(name.parent == tmp_path and name.name.endswith(".partial") for name in names)
    assert all(name.name.startswith(f".{target.name}") for name in names)


def test_no_two_writes_share_a_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []
    real = files._write_partial

    def spy(partial: Path, content: str | bytes) -> None:
        seen.append(partial)
        real(partial, content)

    monkeypatch.setattr(files, "_write_partial", spy)
    files.write_texts({tmp_path / "a.txt": "a", tmp_path / "b.txt": "b"}, overwrite=True)
    files.write_texts({tmp_path / "a.txt": "a2"}, overwrite=True)
    assert len(set(seen)) == 3


def test_a_failed_write_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "x.json"
    target.write_text("old", encoding="utf-8")
    real = files._write_partial

    def full(partial: Path, content: str | bytes) -> None:
        real(partial, content)
        if partial.name.startswith(".second"):
            raise OSError(28, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space"):
        files.write_texts({target: "new", tmp_path / "second.json": "2"}, overwrite=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x.json"]
    assert target.read_text(encoding="utf-8") == "old"


def _finished_pid() -> int:
    """The id of a process that has ended."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def _leave(path: Path, *, age: float) -> Path:
    """A partial file left behind, last written `age` seconds ago."""
    path.write_text("half", encoding="utf-8")
    then = time.time() - age
    os.utime(path, (then, then))
    return path


OLD = files.STALE_AFTER_SECONDS + 60
YOUNG = 60


def test_a_write_removes_an_old_partial_file_of_a_process_that_is_gone(tmp_path: Path) -> None:
    dead = _finished_pid()
    target = tmp_path / "x.json"
    _leave(tmp_path / f".x.json.{dead:x}-0123abcd.partial", age=OLD)
    other = _leave(tmp_path / f".y.json.{dead:x}-0123abcd.partial", age=OLD)  # another file
    files.write_texts({target: "whole"}, overwrite=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([target.name, other.name])


def test_a_write_keeps_a_young_partial_file_even_if_its_process_looks_gone(
    tmp_path: Path,
) -> None:
    """The process id may belong to another machine or PID namespace sharing the folder."""
    dead = _finished_pid()
    young = _leave(tmp_path / f".x.json.{dead:x}-0123abcd.partial", age=YOUNG)
    files.write_texts({tmp_path / "x.json": "whole"}, overwrite=True)
    assert young.exists()


def test_a_write_keeps_the_partial_files_of_live_processes(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    own = _leave(tmp_path / f".x.json.{os.getpid():x}-0123abcd.partial", age=OLD)  # our thread
    parent = _leave(tmp_path / f".x.json.{os.getppid():x}-0123abcd.partial", age=OLD)  # alive
    files.write_texts({target: "whole"}, overwrite=True)
    assert own.exists()
    assert parent.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, 0) is the POSIX check")
def test_a_write_keeps_a_partial_file_when_the_process_check_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doubt means keep: a process of another user answers PermissionError."""

    def refused(pid: int, sig: int) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(files.os, "kill", refused)
    held = _leave(tmp_path / ".x.json.1-0123abcd.partial", age=OLD)
    files.write_texts({tmp_path / "x.json": "whole"}, overwrite=True)
    assert held.exists()


class _RefusedReplace:
    """`os.replace` (or `os.rename`) that raises `error` `refusals` times, then moves."""

    def __init__(
        self,
        refusals: int,
        error: OSError | None = None,
        real: Callable[[Path, Path], None] = os.replace,
    ) -> None:
        self.refusals = refusals
        self.error = error if error is not None else PermissionError(13, "Access is denied")
        self.calls = 0
        self.real = real

    def __call__(self, source: Path, target: Path) -> None:
        self.calls += 1
        if self.calls <= self.refusals:
            raise self.error
        self.real(source, target)


def _refuse_replace(
    monkeypatch: pytest.MonkeyPatch, refusals: int, *, windows: bool
) -> tuple[_RefusedReplace, list[float]]:
    replace = _RefusedReplace(refusals)
    pauses: list[float] = []
    monkeypatch.setattr(files, "_REPLACE_IS_RETRIED", windows)
    monkeypatch.setattr(files, "_replace_once", replace)
    monkeypatch.setattr(files, "_sleep", pauses.append)
    return replace, pauses


def test_a_replace_refused_on_windows_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses a replace while another writer is replacing the same file (#828)."""
    target = tmp_path / "position.json"
    target.write_text("old", encoding="utf-8")
    replace, pauses = _refuse_replace(monkeypatch, 3, windows=True)
    files.write_texts({target: "new"}, overwrite=True)
    assert target.read_text(encoding="utf-8") == "new"
    assert [p.name for p in tmp_path.iterdir()] == [target.name]
    assert replace.calls == 4
    assert len(pauses) == 3
    assert pauses == sorted(pauses)
    assert pauses[0] == files.REPLACE_FIRST_PAUSE


def test_a_replace_refused_every_time_gives_up_and_keeps_the_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "position.json"
    target.write_text("old", encoding="utf-8")
    replace, pauses = _refuse_replace(monkeypatch, 10_000, windows=True)
    with pytest.raises(PermissionError):
        files.write_bytes_atomically(target, b"new", overwrite=True)
    assert replace.calls == files.REPLACE_ATTEMPTS
    assert len(pauses) == files.REPLACE_ATTEMPTS - 1
    assert max(pauses) <= files.REPLACE_MAX_PAUSE
    assert sum(pauses) < 1.0  # a file another program holds open fails quickly
    assert target.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_a_refused_replace_off_windows_is_not_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Elsewhere a refused rename is a real permission problem, not a passing clash."""
    target = tmp_path / "position.json"
    replace, pauses = _refuse_replace(monkeypatch, 1, windows=False)
    with pytest.raises(PermissionError):
        files.write_texts({target: "new"}, overwrite=True)
    assert replace.calls == 1
    assert pauses == []
    assert list(tmp_path.iterdir()) == []


def test_a_windows_replace_never_retries_another_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a refused replace is a passing clash; a full disk is raised at once (#860)."""
    target = tmp_path / "position.json"
    target.write_text("old", encoding="utf-8")
    replace, pauses = _refuse_replace(monkeypatch, 1, windows=True)
    replace.error = OSError(28, "No space left on device")
    with pytest.raises(OSError, match="No space left") as raised:
        files.write_texts({target: "new"}, overwrite=True)
    assert type(raised.value) is OSError
    assert replace.calls == 1
    assert pauses == []
    assert target.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_the_retry_patches_stay_inside_app_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry tests patch seams of `app.files`, never `os.replace` or `time.sleep` (#860)."""
    real_replace, real_sleep = os.replace, time.sleep
    _refuse_replace(monkeypatch, 0, windows=True)
    _refuse_rename(monkeypatch, 0)
    assert os.replace is real_replace
    assert time.sleep is real_sleep
    assert os.rename is not files._rename_once


def _refuse_rename(
    monkeypatch: pytest.MonkeyPatch, refusals: int, error: OSError | None = None
) -> tuple[_RefusedReplace, list[float]]:
    """A Windows no-overwrite rename (simulated on every system) that raises `error`."""
    rename = _RefusedReplace(refusals, error, real=os.rename)
    pauses: list[float] = []
    monkeypatch.setattr(files, "_IS_WINDOWS", True)
    monkeypatch.setattr(files, "_REPLACE_IS_RETRIED", True)
    monkeypatch.setattr(files, "_rename_once", rename)
    monkeypatch.setattr(files, "_sleep", pauses.append)
    return rename, pauses


def test_a_windows_rename_refused_by_a_racing_writer_says_the_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses the rename with access denied while another writer replaces the
    target; the caller gets FileExistsError as on POSIX, and the other file stays (#850)."""
    target = tmp_path / "script.txt"
    target.write_text("theirs", encoding="utf-8")
    rename, pauses = _refuse_rename(monkeypatch, 10_000)
    with pytest.raises(FileExistsError) as raised:
        files.write_texts({target: "mine"}, overwrite=False)
    assert isinstance(raised.value.__cause__, PermissionError)
    assert rename.calls == 1
    assert pauses == []
    assert target.read_text(encoding="utf-8") == "theirs"
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_a_windows_rename_refused_for_a_moment_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "script.txt"
    rename, pauses = _refuse_rename(monkeypatch, 2)
    files.write_texts({target: "mine"}, overwrite=False)
    assert target.read_text(encoding="utf-8") == "mine"
    assert rename.calls == 3
    assert pauses == [files.REPLACE_FIRST_PAUSE, 2 * files.REPLACE_FIRST_PAUSE]
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_a_windows_rename_refused_every_time_without_a_target_stays_a_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No file at the target: a real permission problem, raised after the bounded retry."""
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    calls: list[Path] = []

    def refuse_second(source: Path, target: Path) -> None:
        calls.append(Path(target))
        if Path(target) == second:
            raise PermissionError(13, "Access is denied")
        os.rename(source, target)

    _refuse_rename(monkeypatch, 0)
    monkeypatch.setattr(files, "_rename_once", refuse_second)
    with pytest.raises(PermissionError):
        files.write_texts({first: "1", second: "2"}, overwrite=False)
    assert calls.count(second) == files.REPLACE_ATTEMPTS
    assert list(tmp_path.iterdir()) == []  # all or nothing: the first file is taken back


def test_a_windows_rename_never_retries_another_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "script.txt"
    rename, pauses = _refuse_rename(monkeypatch, 1, FileNotFoundError(2, "gone"))
    with pytest.raises(FileNotFoundError):
        files.write_texts({target: "mine"}, overwrite=False)
    assert rename.calls == 1
    assert pauses == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="the refused rename is a Windows answer")
def test_on_windows_a_rename_refused_while_the_target_exists_says_the_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same as above on Windows itself, with no platform flag patched (#850)."""
    target = tmp_path / "script.txt"
    target.write_text("theirs", encoding="utf-8")
    rename = _RefusedReplace(10_000, real=os.rename)
    monkeypatch.setattr(files, "_rename_once", rename)
    with pytest.raises(FileExistsError):
        files.write_text_atomically(target, "mine", overwrite=False)
    assert rename.calls == 1
    assert target.read_text(encoding="utf-8") == "theirs"
    assert [p.name for p in tmp_path.iterdir()] == [target.name]
