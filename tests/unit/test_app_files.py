"""`app.files`: each write has its own temporary name, so writers of one file never clash (#778)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
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
    """`os.replace` that refuses with access denied `refusals` times, then replaces."""

    def __init__(self, refusals: int) -> None:
        self.refusals = refusals
        self.calls = 0
        self.real = os.replace

    def __call__(self, source: Path, target: Path) -> None:
        self.calls += 1
        if self.calls <= self.refusals:
            raise PermissionError(13, "Access is denied")
        self.real(source, target)


def _refuse_replace(
    monkeypatch: pytest.MonkeyPatch, refusals: int, *, windows: bool
) -> tuple[_RefusedReplace, list[float]]:
    replace = _RefusedReplace(refusals)
    pauses: list[float] = []
    monkeypatch.setattr(files, "_REPLACE_IS_RETRIED", windows)
    monkeypatch.setattr(files.os, "replace", replace)
    monkeypatch.setattr(files.time, "sleep", pauses.append)
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
