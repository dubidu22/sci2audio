"""Fault injection for the script job (tests.md "any file writing"): a full disk, the source
removed during the run, no network, a run killed outright and run again. Never a
half-written file afterwards."""

from __future__ import annotations

import errno
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pdf_maker import Text, make_pdf

from sci2audio.app import (
    JobError,
    JobSettings,
    OutputExistsError,
    Phase,
    UnreadableFileError,
    run_script_job,
)
from sci2audio.app import files as files_module
from sci2audio.testing import no_network

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
SEABORN = CORPUS / "papers" / "joss2021-waskom-seaborn.pdf"


def small_pdf(folder: Path, name: str = "note.pdf", text: str = "A short note.") -> Path:
    path = folder / name
    path.write_bytes(make_pdf([Text(text, 72, 100, size=11)]))
    return path


def contents(folder: Path) -> dict[str, bytes]:
    """Every file under the folder, by relative path."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def fail_on_write(monkeypatch: pytest.MonkeyPatch, at: int) -> None:
    """Make the `at`-th file write (counted from 1) fail as on a full disk."""
    calls = [0]
    real = os.fsync

    def fsync(fd: int) -> None:
        calls[0] += 1
        if calls[0] == at:
            raise OSError(errno.ENOSPC, "No space left on device")
        real(fd)

    monkeypatch.setattr(files_module.os, "fsync", fsync)


@pytest.mark.parametrize("at", [1, 2, 3])
def test_a_full_disk_fails_the_job_and_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at: int
) -> None:
    source = small_pdf(tmp_path)
    fail_on_write(monkeypatch, at)
    with pytest.raises(JobError, match=r"could not write .*No space left on device"):
        run_script_job(source, JobSettings(), tmp_path / "work")
    assert sorted(contents(tmp_path)) == ["note.pdf"]


@pytest.mark.parametrize("at", [1, 2, 3, 4])
def test_a_full_disk_leaves_the_files_of_the_last_run_as_they_were(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at: int
) -> None:
    source = small_pdf(tmp_path, text="The first version.")
    run_script_job(source, JobSettings(), tmp_path / "work")
    before = contents(tmp_path)
    small_pdf(tmp_path, text="The second version.")
    fail_on_write(monkeypatch, at)
    with pytest.raises(JobError, match="No space left on device"):
        run_script_job(source, JobSettings(), tmp_path / "work", overwrite=True)
    after = contents(tmp_path)
    del before["note.pdf"], after["note.pdf"]
    if at <= 3:  # the outputs are written together: none changes
        assert after == before
    else:  # the job record is written after them: the outputs are new, the record is old
        assert after["work/job.json"] == before["work/job.json"]
        assert b"second version" in after["note.script.txt"]
    assert not [name for name in after if name.endswith(".partial")]


def test_a_source_removed_during_the_run_fails_with_a_clear_message(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)

    def remove(phase: Phase) -> None:
        if phase is Phase.READING:
            source.unlink()

    with pytest.raises(UnreadableFileError, match=r"note\.pdf: cannot be opened"):
        run_script_job(source, JobSettings(), tmp_path / "work", progress=remove)
    assert contents(tmp_path) == {}


def test_an_output_that_appears_during_the_run_is_not_replaced(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)

    def appear(phase: Phase) -> None:
        if phase is Phase.WRITING:
            (tmp_path / "note.report.json").write_text("someone else's", encoding="utf-8")

    with pytest.raises(OutputExistsError, match=r"note\.report\.json appeared during the run"):
        run_script_job(source, JobSettings(), tmp_path / "work", progress=appear)
    assert (tmp_path / "note.report.json").read_text(encoding="utf-8") == "someone else's"
    # all or nothing: the script renamed before the clash is taken back, no record written
    assert sorted(contents(tmp_path)) == ["note.pdf", "note.report.json"]


@pytest.mark.parametrize("last", ["note.script.txt", "note.report.json", "note.report.md"])
def test_without_overwrite_the_outputs_are_put_in_place_all_or_none(
    tmp_path: Path, last: str
) -> None:
    source = small_pdf(tmp_path)

    def appear(phase: Phase) -> None:
        if phase is Phase.WRITING:
            (tmp_path / last).write_text("someone else's", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        run_script_job(source, JobSettings(), tmp_path / "work", progress=appear)
    assert contents(tmp_path) == {"note.pdf": source.read_bytes(), last: b"someone else's"}
    (tmp_path / last).unlink()
    run_script_job(source, JobSettings(), tmp_path / "work")  # a second run is not refused


def test_an_output_folder_that_is_a_file_is_refused_before_any_work(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)
    (tmp_path / "outfile").write_text("x", encoding="utf-8")
    phases: list[Phase] = []
    for folder in (tmp_path / "outfile", tmp_path / "outfile" / "below"):
        with pytest.raises(JobError, match="outfile is not a folder") as raised:
            run_script_job(source, JobSettings(output_folder=folder), tmp_path / "w",
                           progress=phases.append)  # fmt: skip
        assert not isinstance(raised.value, OutputExistsError)
    assert phases == []
    with pytest.raises(JobError, match="outfile is not a folder"):
        run_script_job(source, JobSettings(), tmp_path / "outfile" / "work")


def test_an_output_folder_that_becomes_a_file_during_the_run_is_named(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)
    folder = tmp_path / "out"

    def block(phase: Phase) -> None:
        if phase is Phase.WRITING:
            folder.write_text("x", encoding="utf-8")

    with pytest.raises(JobError, match="out is not a folder") as raised:
        run_script_job(source, JobSettings(output_folder=folder), tmp_path / "w", progress=block)
    assert not isinstance(raised.value, OutputExistsError)


def test_the_job_never_uses_the_network(tmp_path: Path) -> None:
    with no_network() as attempts:
        run_script_job(SEABORN, JobSettings(output_folder=tmp_path), tmp_path / "work")
    assert attempts == []


KILLED = """
import os, sys
from pathlib import Path
from sci2audio.app import JobSettings, run_script_job
from sci2audio.app import files

calls = [0]
real = os.fsync
def fsync(fd):
    calls[0] += 1
    if calls[0] == int(sys.argv[3]):
        os._exit(9)  # killed outright: no clean-up runs
    real(fd)
files.os.fsync = fsync
run_script_job(Path(sys.argv[1]), JobSettings(), Path(sys.argv[2]))
"""


@pytest.mark.parametrize("at", [1, 3, 4])
def test_a_run_killed_outright_can_be_run_again(tmp_path: Path, at: int) -> None:
    clean, killed = tmp_path / "clean", tmp_path / "killed"
    clean.mkdir()
    killed.mkdir()
    pdf = small_pdf(tmp_path).read_bytes()
    (clean / "note.pdf").write_bytes(pdf)
    source = killed / "note.pdf"
    source.write_bytes(pdf)
    run_script_job(clean / "note.pdf", JobSettings(), clean / "work")
    done = subprocess.run(
        [sys.executable, "-c", KILLED, str(source), str(killed / "work"), str(at)],
        check=False,
        timeout=120,
    )
    assert done.returncode == 9
    left = contents(killed)
    targets = sorted(n for n in left if not n.endswith(".partial") and n != "note.pdf")
    if at <= 3:  # killed while writing the outputs: none is in place, partial files only
        assert targets == []
    else:  # killed while writing the record: the outputs are complete, the record missing
        assert targets == ["note.report.json", "note.report.md", "note.script.txt"]
        assert all(left[name] == contents(clean)[name] for name in targets)
    run_script_job(source, JobSettings(), killed / "work", overwrite=at > 3)
    assert contents(killed) == contents(clean)
