"""The move of the old working folders into the project folders (#469, D-747, D-748):
nothing lost, nothing replaced, finished by the next run whenever it is cut off."""

from __future__ import annotations

import contextlib
import errno
import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from project_helpers import V1_1, V1_3, can_link, old_folder, old_library, tree_digest

from sci2audio.app import config as config_module
from sci2audio.app import projects
from sci2audio.app.job import JobBusyError
from sci2audio.app.lock import file_lock, work_folder_lock
from sci2audio.app.projects import (
    EARLIER,
    MIGRATE_LOCK,
    Moved,
    migrate_all,
    migrate_one,
    project_folder,
    project_work_folder,
)

ID = "00000000000000a0"


@pytest.fixture
def legacy(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "sci2audio" / "jobs"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "data" / "sci2audio" / "projects"


def digests(legacy: Path, ids: list[str]) -> dict[str, dict[str, tuple[int, str]]]:
    return {project: tree_digest(legacy / project) for project in ids}


# ---- the plain move ---------------------------------------------------------------------


@pytest.mark.parametrize("files", [V1_1, V1_3], ids=["v1.1", "v1.3"])
def test_every_old_folder_moves_with_every_file(
    legacy: Path, root: Path, files: dict[str, bytes]
) -> None:
    ids = old_library(legacy, 3, files)
    before = digests(legacy, ids)
    outcomes = migrate_all(legacy, root)
    assert [(o.id, o.moved) for o in outcomes] == [(i, Moved.MOVED) for i in ids]
    assert {project: tree_digest(root / project) for project in ids} == before
    assert not legacy.exists()  # the old root goes once it is empty


def test_running_it_again_changes_nothing(legacy: Path, root: Path) -> None:
    ids = old_library(legacy, 2)
    migrate_all(legacy, root)
    after = tree_digest(root)
    assert migrate_all(legacy, root) == []
    assert migrate_one(legacy, root, ids[0]).moved is Moved.ABSENT
    assert tree_digest(root) == after


def test_without_an_old_root_nothing_happens(legacy: Path, root: Path) -> None:
    assert migrate_all(legacy, root) == []
    assert not root.exists()


def test_other_entries_of_the_old_root_stay(legacy: Path, root: Path) -> None:
    old_library(legacy, 1)
    (legacy / "preview").mkdir()
    (legacy / "preview" / "voice.wav").write_bytes(b"RIFF")
    (legacy / "notes.txt").write_text("mine")
    migrate_all(legacy, root)
    assert (legacy / "preview" / "voice.wav").read_bytes() == b"RIFF"
    assert (legacy / "notes.txt").read_text() == "mine"


def test_stale_uploads_go_and_fresh_ones_stay(legacy: Path, root: Path) -> None:
    incoming = legacy / ".incoming"
    incoming.mkdir(parents=True)
    stale, fresh, other = incoming / "a.part", incoming / "b.part", incoming / "c.txt"
    for path in (stale, fresh, other):
        path.write_bytes(b"x")
    old = time.time() - 2 * projects.STALE_UPLOAD
    os.utime(stale, (old, old))
    os.utime(other, (old, old))
    migrate_all(legacy, root)
    assert not stale.exists()
    assert fresh.exists()
    assert other.exists()


# ---- a folder that can't be moved now -----------------------------------------------------


def test_a_busy_folder_stays_and_moves_next_time(legacy: Path, root: Path) -> None:
    old_folder(legacy, ID)
    before = tree_digest(legacy / ID)
    with work_folder_lock(legacy / ID):  # a job of an older version works on it
        outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.SKIPPED
    assert tree_digest(legacy / ID) == before
    assert project_folder(root, legacy, ID) == legacy / ID  # still used where it is
    assert migrate_one(legacy, root, ID).moved is Moved.MOVED
    assert tree_digest(root / ID) == before


def test_a_refused_rename_leaves_the_folder_where_it_is(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to rename a folder holding a file another program has open."""
    old_folder(legacy, ID)
    before = tree_digest(legacy / ID)

    def refuse(source: Path, target: Path) -> None:
        raise PermissionError(errno.EACCES, "in use", str(source))

    monkeypatch.setattr(projects, "_rename", refuse)
    outcome = migrate_one(legacy, root, ID)
    assert (outcome.moved, outcome.reason) == (Moved.SKIPPED, "in use")
    assert tree_digest(legacy / ID) == before
    assert project_folder(root, legacy, ID) == legacy / ID


def test_another_process_moving_means_waiting_then_using_the_old_folders(
    legacy: Path, root: Path
) -> None:
    old_folder(legacy, ID)
    with file_lock(root / MIGRATE_LOCK, wait=0) as held:
        assert held
        assert migrate_all(legacy, root, wait=0.2) == []
        assert migrate_one(legacy, root, ID, wait=0.2).moved is Moved.SKIPPED
    assert (legacy / ID / "source").is_dir()
    assert migrate_one(legacy, root, ID).moved is Moved.MOVED


def test_a_link_in_place_of_an_old_folder_is_never_followed(
    legacy: Path, root: Path, tmp_path: Path
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    elsewhere = old_folder(tmp_path / "elsewhere", ID)
    before = tree_digest(elsewhere)
    legacy.mkdir(parents=True)
    os.symlink(elsewhere, legacy / ID, target_is_directory=True)
    [outcome] = migrate_all(legacy, root)
    assert outcome.moved is Moved.SKIPPED
    assert tree_digest(elsewhere) == before
    assert not (root / ID).exists()
    assert project_folder(root, legacy, ID) == root / ID  # a link is never used as a folder


def test_a_link_inside_an_old_folder_is_moved_as_a_link_never_followed(
    legacy: Path, root: Path, tmp_path: Path
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    outside = tmp_path / "outside.txt"
    outside.write_text("the person's")
    old_folder(legacy, ID)
    os.symlink(outside, legacy / ID / "chunks" / "odd")
    migrate_all(legacy, root)
    assert (root / ID / "chunks" / "odd").is_symlink()
    assert outside.read_text() == "the person's"


# ---- across file systems -------------------------------------------------------------------


def across_file_systems(legacy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Renames out of the old root fail as they do between two file systems."""
    rename = projects._rename

    def cross(source: Path, target: Path) -> None:
        if legacy in source.parents:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        rename(source, target)

    def no_link(source: Path, target: Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(projects, "_rename", cross)
    monkeypatch.setattr(projects, "_link", no_link)


def test_across_file_systems_the_folder_is_copied_checked_then_removed(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID)
    before = tree_digest(legacy / ID)
    across_file_systems(legacy, monkeypatch)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.COPIED
    assert tree_digest(root / ID) == before
    assert not (legacy / ID).exists()
    assert not (root / f"{projects.MOVING}{ID}").exists()


def test_a_copy_that_differs_is_thrown_away_and_the_old_folder_stays(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID)
    before = tree_digest(legacy / ID)
    across_file_systems(legacy, monkeypatch)
    digest = projects._digest

    def damaged(path: Path) -> tuple[int, str]:
        size, sha = digest(path)
        return (size, "0" * 64) if projects.MOVING in str(path) else (size, sha)

    monkeypatch.setattr(projects, "_digest", damaged)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.SKIPPED
    assert "differs" in outcome.reason
    assert tree_digest(legacy / ID) == before
    assert not (root / ID).exists()
    assert not (root / f"{projects.MOVING}{ID}").exists()


# ---- into a project folder that exists ---------------------------------------------------


def test_the_same_files_already_there_are_removed_from_the_old_folder(
    legacy: Path, root: Path
) -> None:
    old_folder(legacy, ID)
    old_folder(root, ID)  # the same contents, moved before a cut-off
    before = tree_digest(root / ID)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.MERGED
    assert tree_digest(root / ID) == before
    assert not (legacy / ID).exists()


def test_different_files_never_replace_the_new_ones(legacy: Path, root: Path) -> None:
    old = old_folder(legacy, ID)
    old_before = tree_digest(old)
    new = root / ID
    (new / "source").mkdir(parents=True)
    (new / "source" / "paper.pdf").write_bytes(old.joinpath("source/paper.pdf").read_bytes())
    (new / "position.json").write_bytes(b'{"seconds": 900}')  # written by the new version
    (new / "chunks" / "ab").mkdir(parents=True)
    (new / "chunks" / "ab" / "ab01.wav").write_bytes(b"RIFF newer")
    outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.MERGED
    assert (new / "position.json").read_bytes() == b'{"seconds": 900}'
    assert (new / "chunks/ab/ab01.wav").read_bytes() == b"RIFF newer"
    earlier = new / EARLIER
    assert (earlier / "position.json").read_bytes() == V1_3["position.json"] + ID.encode()
    assert (earlier / "chunks/ab/ab01.wav").is_file()
    after = tree_digest(new)
    # every old file is somewhere in the new folder, under its name or in EARLIER
    for name, digest in old_before.items():
        assert after.get(name) == digest or after.get(f"{EARLIER}/{name}") == digest
    assert not (legacy / ID).exists()


def test_a_name_taken_in_earlier_gets_a_number(legacy: Path, root: Path) -> None:
    old_folder(legacy, ID, {"position.json": b"old"})
    new = root / ID
    (new / EARLIER).mkdir(parents=True)
    (new / "position.json").write_bytes(b"new")
    (new / EARLIER / "position.json").write_bytes(b"older still")
    migrate_one(legacy, root, ID)
    assert (new / "position.json").read_bytes() == b"new"
    assert (new / EARLIER / "position.json").read_bytes() == b"older still"
    assert (new / EARLIER / "position (2).json").read_bytes() == b"old" + ID.encode()


def test_without_hard_links_a_file_that_appears_is_never_replaced(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard after copying: a file put at the name meanwhile is kept, and so is the old
    file; without the check the rename would replace the new file on Linux and macOS."""
    old_folder(legacy, ID, {"position.json": b"old"})
    (root / ID).mkdir(parents=True)
    copy = projects._copy_checked

    def no_link(source: Path, target: Path) -> None:
        raise OSError(errno.EPERM, "no hard links here")

    def racing(source: Path, target: Path) -> None:
        copy(source, target)
        (root / ID / "position.json").write_bytes(b"written meanwhile")

    monkeypatch.setattr(projects, "_link", no_link)
    monkeypatch.setattr(projects, "_copy_checked", racing)
    outcome = migrate_one(legacy, root, ID)
    assert (root / ID / "position.json").read_bytes() == b"written meanwhile"
    assert (legacy / ID / "position.json").read_bytes() == b"old" + ID.encode()
    assert outcome.left == (legacy / ID / "position.json",)
    assert not list((root / ID).glob(f"*{projects.PART}"))


def test_a_link_inside_an_old_folder_stays_there_when_merging(
    legacy: Path, root: Path, tmp_path: Path
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    outside = tmp_path / "outside.txt"
    outside.write_text("the person's")
    old_folder(legacy, ID, {"position.json": b"old"})
    os.symlink(outside, legacy / ID / "odd")
    (root / ID).mkdir(parents=True)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.left == (legacy / ID / "odd",)
    assert (legacy / ID / "odd").is_symlink()
    assert outside.read_text() == "the person's"
    assert not (root / ID / "odd").exists()


def test_a_file_where_the_new_folder_should_be_is_left_alone(legacy: Path, root: Path) -> None:
    old_folder(legacy, ID)
    root.mkdir(parents=True)
    (root / ID).write_text("not a folder")
    assert migrate_one(legacy, root, ID).moved is Moved.SKIPPED
    assert (root / ID).read_text() == "not a folder"
    assert (legacy / ID / "source").is_dir()


# ---- cut off at any point (MT2) ----------------------------------------------------------


class Cut(BaseException):
    """The process is killed: nothing below it runs, no `except OSError` catches it."""


OPERATIONS = ("_rename", "_link", "_unlink", "_create")


def cut_after(monkeypatch: pytest.MonkeyPatch, count: int) -> list[int]:
    """Let `count` file operations of the move run, then cut the process off."""
    done = [0]
    for name in OPERATIONS:
        real: Callable[..., Any] = getattr(projects, name)

        def counted(*args: Any, _real: Callable[..., Any] = real) -> Any:
            if done[0] >= count:
                raise Cut
            done[0] += 1
            return _real(*args)

        monkeypatch.setattr(projects, name, counted)
    return done


def setup_case(case: str, legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_folder(legacy, ID)
    if case == "across":
        across_file_systems(legacy, monkeypatch)
    elif case == "merge":  # half of it moved before: some files there, one different
        new = root / ID
        (new / "source").mkdir(parents=True)
        source = legacy / ID / "source" / "paper.pdf"
        (new / "source" / "paper.pdf").write_bytes(source.read_bytes())
        (new / "position.json").write_bytes(b"newer")
    elif case == "merge-across":
        across_file_systems(legacy, monkeypatch)
        (root / ID).mkdir(parents=True)


def every_file_is_somewhere(original: dict[str, tuple[int, str]], legacy: Path, root: Path) -> None:
    old, new = tree_digest(legacy / ID), tree_digest(root / ID)
    for name, digest in original.items():
        assert digest in (old.get(name), new.get(name), new.get(f"{EARLIER}/{name}")), name


CASES = ["fast", "across", "merge", "merge-across"]


def cut_run(folder: Path, case: str, count: int | None) -> int:
    """One move in `folder`, cut off after `count` file operations (None: not cut), then
    the next start; checks that nothing is lost and the move is finished. Returns how many
    file operations the cut run made."""
    legacy, root = folder / "jobs", folder / "projects"
    with pytest.MonkeyPatch.context() as patch:
        setup_case(case, legacy, root, patch)
        original, own = tree_digest(legacy / ID), tree_digest(root / ID)
        with patch.context() as cut:
            done = cut_after(cut, 10**6 if count is None else count)
            with contextlib.suppress(Cut):
                migrate_all(legacy, root)
        every_file_is_somewhere(original, legacy, root)
        # the document is still found: the old or the new folder has its copy of the file
        assert any((f / ID / "source" / "paper.pdf").is_file() for f in (legacy, root))
        migrate_all(legacy, root)  # the next start
        assert not (legacy / ID).exists()
        assert not (root / f"{projects.MOVING}{ID}").exists()
        every_file_is_somewhere(original, legacy, root)
        assert not list((root / ID).rglob(f"*{projects.PART}"))
        after = tree_digest(root / ID)
        assert {name: after.get(name) for name in own} == own  # the new folder's own files
        if case in ("fast", "across"):
            assert after == original  # nothing went to from-earlier-version
        return done[0]


@pytest.mark.parametrize("case", CASES)
def test_a_move_cut_off_at_every_point_loses_nothing_and_finishes_next_time(
    tmp_path: Path, case: str
) -> None:
    """MT2, exhaustive: an uncut run counts the file operations; then the move is cut off
    after each number of them, from none to all, inside M8 across file systems too."""
    total = cut_run(tmp_path / "uncut", case, None)
    assert total > 0
    for count in range(total + 1):
        cut_run(tmp_path / str(count), case, count)


# ---- the default folders ------------------------------------------------------------------


def test_the_command_line_moves_its_file_s_old_folder_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config_module.platformdirs, "user_data_path", lambda *a, **k: tmp_path / "d"
    )
    monkeypatch.setattr(
        config_module.platformdirs, "user_cache_path", lambda *a, **k: tmp_path / "c"
    )
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7 the paper")
    project = config_module.file_id(source)
    old_folder(tmp_path / "c" / "jobs", project)
    before = tree_digest(tmp_path / "c" / "jobs" / project)
    work = project_work_folder(source)
    assert (
        work == tmp_path / "d" / "projects" / project == config_module.default_work_folder(source)
    )
    assert tree_digest(work) == before
    assert not (tmp_path / "c" / "jobs" / project).exists()


def test_the_command_line_uses_an_old_folder_it_can_t_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config_module.platformdirs, "user_data_path", lambda *a, **k: tmp_path / "d"
    )
    monkeypatch.setattr(
        config_module.platformdirs, "user_cache_path", lambda *a, **k: tmp_path / "c"
    )
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7 the paper")
    old = old_folder(tmp_path / "c" / "jobs", config_module.file_id(source))
    with work_folder_lock(old):
        assert project_work_folder(source) == old


def test_a_project_id_is_checked() -> None:
    with pytest.raises(ValueError, match="not a project id"):
        migrate_one(Path("jobs"), Path("projects"), "../escape")


def test_a_leftover_copy_is_thrown_away_without_following_its_links(
    legacy: Path, root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("the person's")
    staging = root / f"{projects.MOVING}{ID}"
    staging.mkdir(parents=True)
    os.symlink(outside, staging / "odd", target_is_directory=True)
    old_folder(legacy, ID)
    across_file_systems(legacy, monkeypatch)
    assert migrate_one(legacy, root, ID).moved is Moved.COPIED
    assert (outside / "keep.txt").read_text() == "the person's"
    assert not staging.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows thing")
def test_a_junction_in_place_of_an_old_folder_is_never_followed(
    legacy: Path, root: Path, tmp_path: Path
) -> None:
    import _winapi  # type: ignore[import-not-found]

    elsewhere = old_folder(tmp_path / "elsewhere", ID)
    before = tree_digest(elsewhere)
    legacy.mkdir(parents=True)
    _winapi.CreateJunction(str(elsewhere), str(legacy / ID))
    [outcome] = migrate_all(legacy, root)
    assert outcome.moved is Moved.SKIPPED
    assert tree_digest(elsewhere) == before
    assert not (root / ID).exists()


# ---- review round 1 of PR #532 -------------------------------------------------------------


@pytest.mark.timeout(30)
def test_r1_a_file_named_like_the_earlier_folder_ends_the_merge(legacy: Path, root: Path) -> None:
    """The numbering never loops: a place that is in the way ends the attempt, the old
    file stays where it is and is named, and the server starts."""
    old_folder(legacy, ID, {"position.json": b"old"})
    new = root / ID
    new.mkdir(parents=True)
    (new / "position.json").write_bytes(b"new")
    (new / EARLIER).write_bytes(b"a file, not a folder")
    before = tree_digest(new)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.MERGED
    assert outcome.left == (legacy / ID / "position.json",)
    assert (legacy / ID / "position.json").read_bytes() == b"old" + ID.encode()
    assert tree_digest(new) == before
    assert len(migrate_all(legacy, root)) == 1  # and again: it returns


@pytest.mark.timeout(30)
def test_r1_a_place_that_can_t_be_looked_at_ends_the_merge(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID, {"position.json": b"old"})
    new = root / ID
    (new / EARLIER).mkdir(parents=True)
    (new / "position.json").write_bytes(b"new")
    real = Path.lstat
    asked: list[str] = []

    def refused(self: Path) -> os.stat_result:
        if EARLIER in self.parts and self.name != EARLIER:
            asked.append(self.name)
            raise PermissionError(errno.EACCES, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "lstat", refused)
    outcome = migrate_one(legacy, root, ID)
    monkeypatch.undo()
    assert asked == ["position.json"]  # the first place that can't be looked at ends it
    assert outcome.left == (legacy / ID / "position.json",)
    assert (legacy / ID / "position.json").read_bytes() == b"old" + ID.encode()
    assert list((new / EARLIER).iterdir()) == []


@pytest.mark.timeout(30)
def test_r1_the_numbering_stops(legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_folder(legacy, ID, {"position.json": b"old"})
    new = root / ID
    (new / EARLIER).mkdir(parents=True)
    (new / "position.json").write_bytes(b"new")
    for name in ("position.json", "position (2).json", "position (3).json"):
        (new / EARLIER / name).write_bytes(name.encode())
    monkeypatch.setattr(projects, "MAX_EARLIER", 3)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.left == (legacy / ID / "position.json",)
    assert len(list((new / EARLIER).iterdir())) == 3


def job_tries(folder: Path, tried: list[str]) -> None:
    """What a job of an older version does: take the folder's lock and write its record."""
    try:
        with work_folder_lock(folder):
            (folder / "audio.json").write_bytes(b"the newest record")
            tried.append("took it")
    except JobBusyError:
        tried.append("busy")


def test_r2_no_job_takes_the_folder_while_it_is_copied(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID)
    across_file_systems(legacy, monkeypatch)
    tried: list[str] = []
    copy = projects._copy_checked

    def copying(source: Path, target: Path) -> None:
        if source.name == "position.json" and not tried:  # after audio.json was copied
            job_tries(legacy / ID, tried)
        copy(source, target)

    monkeypatch.setattr(projects, "_copy_checked", copying)
    assert migrate_one(legacy, root, ID).moved is Moved.COPIED
    assert tried == ["busy"]
    migrate_all(legacy, root)  # the next start
    assert not (root / ID / EARLIER).exists()


def test_r2_no_job_takes_the_folder_while_it_is_merged(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID)
    (root / ID).mkdir(parents=True)
    tried: list[str] = []
    place = projects._place

    def placing(path: Path, target: Path) -> None:
        if not tried:
            job_tries(legacy / ID, tried)
        place(path, target)

    monkeypatch.setattr(projects, "_place", placing)
    assert migrate_one(legacy, root, ID).moved is Moved.MERGED
    assert tried == ["busy"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows lets the lock go for the rename")
def test_r2_no_job_takes_the_folder_while_it_is_renamed(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID)
    tried: list[str] = []
    rename = projects._rename

    def renaming(source: Path, target: Path) -> None:
        job_tries(source, tried)
        rename(source, target)

    monkeypatch.setattr(projects, "_rename", renaming)
    assert migrate_one(legacy, root, ID).moved is Moved.MOVED
    assert tried == ["busy"]


def test_r3_same_size_and_time_but_other_bytes_is_another_file(legacy: Path, root: Path) -> None:
    old = old_folder(legacy, ID, {"position.json": b"old"}) / "position.json"
    data = old.read_bytes()
    other = bytes(byte ^ 1 for byte in data)
    new = root / ID / "position.json"
    new.parent.mkdir(parents=True)
    new.write_bytes(other)
    info = old.stat()
    os.utime(new, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert migrate_one(legacy, root, ID).moved is Moved.MERGED
    assert new.read_bytes() == other
    assert (root / ID / EARLIER / "position.json").read_bytes() == data


def test_r4_an_old_file_changed_after_its_copy_is_not_removed(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = old_folder(legacy, ID) / "position.json"
    original = old.read_bytes()
    changed = bytes(byte ^ 1 for byte in original)  # the same size
    across_file_systems(legacy, monkeypatch)
    copy = projects._copy_checked

    def writer(source: Path, target: Path) -> None:
        copy(source, target)
        if source == old:  # a writer that ignores the lock
            old.write_bytes(changed)

    monkeypatch.setattr(projects, "_copy_checked", writer)
    assert migrate_one(legacy, root, ID).moved is Moved.COPIED
    assert old.read_bytes() == changed
    monkeypatch.setattr(projects, "_copy_checked", copy)
    migrate_all(legacy, root)  # the next start
    assert (root / ID / "position.json").read_bytes() == original
    assert (root / ID / EARLIER / "position.json").read_bytes() == changed
    assert not (legacy / ID).exists()


def test_r5_the_merge_never_works_through_a_link_in_the_project_folder(
    legacy: Path, root: Path, tmp_path: Path
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    old = old_folder(legacy, ID)
    original = tree_digest(old)
    chunks = sorted(name for name in original if name.startswith("chunks/"))
    assert chunks
    outside = tmp_path / "outside"
    first = outside / chunks[0].removeprefix("chunks/")
    first.parent.mkdir(parents=True)
    first.write_bytes((old / chunks[0]).read_bytes())  # the same file, through the link
    new = root / ID
    new.mkdir(parents=True)
    os.symlink(outside, new / "chunks", target_is_directory=True)
    before = tree_digest(outside)
    migrate_one(legacy, root, ID)
    assert tree_digest(outside) == before
    old_now, new_now = tree_digest(old), tree_digest(new)
    for name in chunks:
        assert original[name] in (old_now.get(name), new_now.get(f"{EARLIER}/{name}")), name


def test_r5_folders_are_never_made_through_a_link(tmp_path: Path) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, tmp_path / "link", target_is_directory=True)
    with pytest.raises(OSError, match="is not a folder"):
        projects._make_folders(tmp_path / "link" / "a" / "b")
    assert list(outside.iterdir()) == []


def test_r5_across_file_systems_links_are_never_copied(
    legacy: Path, root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    outside_file, outside_folder = tmp_path / "outside.txt", tmp_path / "outside"
    outside_file.write_text("the person's")
    outside_folder.mkdir()
    (outside_folder / "keep.txt").write_text("the person's too")
    old = old_folder(legacy, ID)
    os.symlink(outside_file, old / "odd-file")
    os.symlink(outside_folder, old / "chunks" / "odd-folder", target_is_directory=True)
    across_file_systems(legacy, monkeypatch)
    outcome = migrate_one(legacy, root, ID)
    assert outcome.moved is Moved.COPIED
    assert set(outcome.left) == {old / "odd-file", old / "chunks" / "odd-folder"}
    assert not os.path.lexists(root / ID / "odd-file")
    assert not os.path.lexists(root / ID / "chunks" / "odd-folder")
    assert (old / "odd-file").is_symlink()
    assert outside_file.read_text() == "the person's"
    assert [p.name for p in outside_folder.iterdir()] == ["keep.txt"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows refuses to rename it then")
def test_r7_a_file_held_open_keeps_the_folder_where_it_is(legacy: Path, root: Path) -> None:
    old = old_folder(legacy, ID)
    before = tree_digest(old)
    with (old / "position.json").open("rb"):
        outcome = migrate_one(legacy, root, ID)
        assert outcome.moved is Moved.SKIPPED
        assert tree_digest(old) == before
        assert project_folder(root, legacy, ID) == old
    assert migrate_one(legacy, root, ID).moved is Moved.MOVED
    assert tree_digest(root / ID) == before


def test_r8_the_terminal_says_how_many_projects_move(
    legacy: Path, root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    old_library(legacy, 2)
    with caplog.at_level(logging.WARNING, logger="sci2audio.app.projects"):
        migrate_all(legacy, root)
    assert caplog.messages == ["Moving 2 projects to their new folders…"]
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="sci2audio.app.projects"):
        assert migrate_all(legacy, root) == []  # nothing left: no line
    assert caplog.messages == []
    old_folder(legacy, ID)
    with caplog.at_level(logging.WARNING, logger="sci2audio.app.projects"):
        migrate_all(legacy, root)
    assert caplog.messages == ["Moving 1 project to its new folder…"]


def test_r8_the_terminal_says_when_the_old_root_is_a_link(
    tmp_path: Path, root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    elsewhere = tmp_path / "elsewhere"
    old_folder(elsewhere, ID)
    legacy = tmp_path / "jobs"
    os.symlink(elsewhere, legacy, target_is_directory=True)
    with caplog.at_level(logging.WARNING, logger="sci2audio.app.projects"):
        assert migrate_all(legacy, root) == []
    assert caplog.messages == [f"the old working folders in {legacy} are not moved: it is a link"]
    assert (elsewhere / ID / "source").is_dir()


def test_r11_a_copy_whose_commit_failed_is_thrown_away_next_time(
    legacy: Path, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_folder(legacy, ID)
    original = tree_digest(legacy / ID)
    across_file_systems(legacy, monkeypatch)
    rename = projects._rename
    staging = root / f"{projects.MOVING}{ID}"

    def appears(source: Path, target: Path) -> None:
        if source == staging:  # the project folder appeared during the copy
            target.mkdir()
            raise FileExistsError(errno.EEXIST, "File exists", str(target))
        rename(source, target)

    monkeypatch.setattr(projects, "_rename", appears)
    assert migrate_one(legacy, root, ID).moved is Moved.SKIPPED
    assert staging.is_dir()
    monkeypatch.setattr(projects, "_rename", rename)
    assert migrate_one(legacy, root, ID).moved is Moved.MERGED
    assert not os.path.lexists(staging)
    assert tree_digest(root / ID) == original
    assert not (legacy / ID).exists()
