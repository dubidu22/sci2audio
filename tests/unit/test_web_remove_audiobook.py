"""Removing a project deletes its audiobook files after the warning (#470, D-751, D-754).

Only files the project's record lists, in a project audiobook folder sci2audio made, are
deleted, and only while their size and SHA-256 still match; everything else stays and is
named with its reason. Each S test fails with its guard taken out (the mutants are listed
in the pull request)."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

import platformdirs
import pytest
from audio_fakes import FakeVoice
from fastapi.testclient import TestClient
from pdf_maker import Text, make_pdf
from web_helpers import (
    book_folder,
    browser,
    make_config,
    offline,  # noqa: F401 - fixture
    program,
    upload,
    wait,
)

from sci2audio.app.lock import work_folder_lock
from sci2audio.web import api, create_app, i18n, removal
from sci2audio.web.player import write_record
from sci2audio.web.project import (
    PROJECT,
    AudiobookFile,
    AudiobookFolder,
    Project,
    read_project,
    record_files,
    write_project,
)

pytestmark = pytest.mark.usefixtures("offline")


def note(text: str = "A short note.") -> bytes:
    lines = (text, "It has two lines.")
    return make_pdf([Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(lines)])


def server(tmp_path: Path, **changes: Any) -> tuple[Any, TestClient, Any]:
    config = make_config(tmp_path, **changes)
    voice = FakeVoice()
    app = create_app(config, voice=lambda models_dir: voice.source())
    return app, program(app, config), config


def made(client: TestClient, data: bytes, name: str = "note.pdf") -> dict[str, Any]:
    """A document with an analysis and an audiobook in its project folder."""
    doc = upload(client, data, name)
    for kind in ("script", "audio"):
        job = client.post("/api/v1/jobs", json={"kind": kind, "document": doc["id"]})
        assert job.status_code == 202, job.text
        assert wait(client, job.json()["id"])["state"] == "done"
    return doc


def remove(client: TestClient, document: str, keep: str | None = "false") -> Any:
    query = "" if keep is None else f"?keep_audiobook={keep}"
    return client.delete(f"/api/v1/documents/{document}{query}")


def files_of(folder: Path) -> dict[str, bytes]:
    if not folder.is_dir():
        return {}
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir()) if p.is_file()}


def entry(path: Path) -> AudiobookFile:
    data = path.read_bytes()
    return AudiobookFile(path.name, len(data), hashlib.sha256(data).hexdigest())


def record(work: Path, document: str, folder: Path, *files: AudiobookFile) -> None:
    """Make the project's record list `files` in `folder` (a crafted record)."""
    project = read_project(work, document)
    assert project is not None
    write_project(work, Project(document, project.name, (AudiobookFolder(folder, files),)))


def kept(response: Any) -> dict[str, str]:
    return {Path(k["path"]).name: k["reason"] for k in response.json()["kept"]}


def first_file(one: dict[str, Any]) -> Path:
    """The record's first audiobook file: the first one the removal tries."""
    project = read_project(one["work"], one["doc"])
    assert project is not None
    return project.audiobooks[0].folder / project.audiobooks[0].files[0].name


@pytest.fixture
def one(tmp_path: Path) -> dict[str, Any]:
    app, client, config = server(tmp_path)
    doc = made(client, note())
    book = book_folder(config.output_folder, "note.pdf")
    files = files_of(book)
    assert len(files) >= 2
    return {
        "app": app,
        "client": client,
        "config": config,
        "doc": doc["id"],
        "work": config.work_root / doc["id"],
        "book": book,
        "files": files,
    }


# ---- what goes ---------------------------------------------------------------------------


def test_the_recorded_files_and_their_folder_go_by_default(one: dict[str, Any]) -> None:
    client, book, files = one["client"], one["book"], one["files"]
    response = remove(client, one["doc"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted_files"] == len(files)
    assert body["deleted_bytes"] == sum(len(data) for data in files.values())
    assert body["kept"] == []
    assert body["kept_more"] == 0
    assert not book.exists()
    assert one["config"].output_folder.is_dir()  # the output folder itself stays
    assert not one["work"].exists()


def test_a_recorded_file_already_gone_is_skipped_and_the_rest_goes(one: dict[str, Any]) -> None:
    """A stale record entry (#552) is not an error: it is simply not there."""
    gone = sorted(one["files"])[0]
    (one["book"] / gone).unlink()
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == len(one["files"]) - 1
    assert response.json()["kept"] == []
    assert not one["book"].exists()


def test_an_empty_project_folder_left_by_a_failed_first_run_goes(one: dict[str, Any]) -> None:
    """A folder recorded with no files yet (#552) is removed with `rmdir`."""
    for name in one["files"]:
        (one["book"] / name).unlink()
    record(one["work"], one["doc"], one["book"])
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == 0
    assert response.json()["kept"] == []
    assert not one["book"].exists()


def test_s8_keep_deletes_no_audiobook_file(one: dict[str, Any]) -> None:
    response = remove(one["client"], one["doc"], "true")
    assert response.status_code == 200
    assert response.json()["deleted_files"] == 0
    assert kept(response) == {one["book"].name: "kept-by-choice"}
    assert files_of(one["book"]) == one["files"]
    assert not one["work"].exists()


@pytest.mark.parametrize("keep", [None, "", "maybe"])
def test_s8_without_a_clear_choice_nothing_is_deleted(one: dict[str, Any], keep: Any) -> None:
    response = remove(one["client"], one["doc"], keep)
    assert response.status_code == 422
    assert files_of(one["book"]) == one["files"]
    assert (one["work"] / "source").is_dir()


# ---- what stays (R4, R5) -----------------------------------------------------------------


def test_s1_a_file_the_person_put_there_stays_and_so_does_the_folder(
    one: dict[str, Any],
) -> None:
    mine = one["book"] / "my notes.txt"
    mine.write_bytes(b"\x00mine\xff")
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200
    assert response.json()["deleted_files"] == len(one["files"])
    assert kept(response) == {"my notes.txt": "not-recorded"}
    assert files_of(one["book"]) == {"my notes.txt": b"\x00mine\xff"}


def test_s2_a_file_of_another_size_stays(one: dict[str, Any]) -> None:
    name = sorted(one["files"])[0]
    (one["book"] / name).write_bytes(one["files"][name] + b"more")
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200
    assert kept(response) == {name: "changed"}
    assert files_of(one["book"]) == {name: one["files"][name] + b"more"}


def test_s2_same_size_and_time_but_other_bytes_stays(one: dict[str, Any]) -> None:
    """Hash, never time and size: those collide on Windows."""
    name = sorted(one["files"])[0]
    path = one["book"] / name
    before = path.stat()
    changed = bytes(b ^ 0xFF for b in one["files"][name])
    path.write_bytes(changed)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert (path.stat().st_size, path.stat().st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    response = remove(one["client"], one["doc"])
    assert kept(response) == {name: "changed"}
    assert path.read_bytes() == changed


def test_s3_a_recorded_name_that_is_now_a_link_stays_and_its_target_too(
    one: dict[str, Any], tmp_path: Path
) -> None:
    name = sorted(one["files"])[0]
    target = tmp_path / "elsewhere" / name
    target.parent.mkdir()
    target.write_bytes(one["files"][name])  # the same bytes: only the link check keeps it
    (one["book"] / name).unlink()
    try:
        (one["book"] / name).symlink_to(target)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    response = remove(one["client"], one["doc"])
    assert kept(response) == {name: "link"}
    assert target.read_bytes() == one["files"][name]
    assert (one["book"] / name).is_symlink()


def test_a_file_that_can_t_be_read_to_be_checked_stays(
    one: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An iCloud file not downloaded while offline: never delete what can't be checked."""
    name = sorted(one["files"])[0]
    real = removal._sha256

    def evicted(path: Path) -> str:
        if path.name == name:
            raise OSError(errno.EIO, "Resource deadlock avoided", str(path))
        return real(path)

    monkeypatch.setattr(removal, "_sha256", evicted)
    response = remove(one["client"], one["doc"])
    assert kept(response) == {name: "unreadable"}
    assert files_of(one["book"]) == {name: one["files"][name]}


def test_at_most_fifty_kept_paths_are_named_and_the_rest_counted(one: dict[str, Any]) -> None:
    for n in range(removal.KEPT_LIMIT + 7):
        (one["book"] / f"mine {n:03}.txt").write_text("mine")
    body = remove(one["client"], one["doc"]).json()
    assert len(body["kept"]) == removal.KEPT_LIMIT
    assert body["kept_more"] == 7
    assert len(files_of(one["book"])) == removal.KEPT_LIMIT + 7


def test_a_whole_folder_that_stayed_is_listed_before_the_limit_cuts_files(
    one: dict[str, Any], tmp_path: Path
) -> None:
    """Whole folders come first, so the count of files that stayed stays exact
    (#569)."""
    for n in range(removal.KEPT_LIMIT + 7):
        (one["book"] / f"mine {n:03}.txt").write_text("mine")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    linked = one["config"].output_folder / "note (2)"
    try:
        linked.symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    project = read_project(one["work"], one["doc"])
    assert project is not None
    write_project(
        one["work"],
        Project(one["doc"], project.name, (*project.audiobooks, AudiobookFolder(linked, ()))),
    )
    body = remove(one["client"], one["doc"]).json()
    assert body["kept"][0] == {"path": str(linked), "reason": "link", "folder": str(linked)}
    assert all(k["path"] != k["folder"] for k in body["kept"][1:])
    assert len(body["kept"]) == removal.KEPT_LIMIT
    assert body["kept_more"] == 8  # 57 files, 49 of them named


# ---- folders that are never deleted in (R3) -----------------------------------------------


def _guarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    home, documents = tmp_path / "home", tmp_path / "home" / "Documents"
    documents.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(platformdirs, "user_documents_path", lambda: documents)
    return {"home": home, "documents": documents}


@pytest.mark.parametrize(
    "where",
    ["output", "work", "config", "models", "legacy", "home", "documents", "saved", "above"],
)
def test_s4_a_record_naming_a_protected_folder_deletes_nothing_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    paths = _guarded(tmp_path, monkeypatch)
    _app, client, config = server(tmp_path, legacy_root=tmp_path / "legacy")
    doc = made(client, note())
    saved = tmp_path / "saved"
    saved.mkdir()
    assert client.put("/api/v1/settings", json={"output_folder": str(saved)}).status_code == 200
    folder = {
        "output": config.output_folder,
        "work": config.work_root,
        "config": config.config_file.parent,
        "models": config.models_dir,
        "legacy": tmp_path / "legacy",
        "home": paths["home"],
        "documents": paths["documents"],
        "saved": saved,
        "above": tmp_path,  # holds the output folder
    }[where].absolute()
    folder.mkdir(parents=True, exist_ok=True)
    book = folder / "book.mp3"
    book.write_bytes(b"ID3 an audiobook of the person's")
    work = config.work_root / doc["id"]
    record(work, doc["id"], folder, entry(book))
    response = remove(client, doc["id"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == 0
    assert [(k["path"], k["reason"]) for k in response.json()["kept"]] == [(str(folder), "outside")]
    assert book.read_bytes() == b"ID3 an audiobook of the person's"


@pytest.mark.parametrize("resolves", [True, False])
def test_s4_a_drive_or_file_system_root_is_never_a_project_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resolves: bool
) -> None:
    """The root of a protected folder's drive is protected even when that folder's real
    place can't be found (an unplugged drive, a link loop)."""
    guard = tmp_path / "out"
    if not resolves:
        real = Path.resolve

        def resolve(self: Path, strict: bool = False) -> Path:
            if self == guard:
                raise OSError(errno.ELOOP, "Too many levels of symbolic links", str(self))
            return real(self, strict=strict)

        monkeypatch.setattr(Path, "resolve", resolve)
    root = Path(tmp_path.absolute().anchor)
    project = Project("a" * 16, "x", (AudiobookFolder(root, (AudiobookFile("x", 1, "0" * 64),)),))
    planned = removal.plan(project, [guard], [])
    assert planned.delete == ()
    assert planned.folders == ()
    assert planned.kept == (removal.Kept(root, "outside", root),)


@pytest.mark.parametrize(
    "name", ["../book.mp3", "sub/book.mp3", "sub\\book.mp3", "/book.mp3", "C:book.mp3", "a\x00b"]
)
def test_s5_a_file_entry_that_is_not_a_bare_name_is_refused(one: dict[str, Any], name: str) -> None:
    outside = one["book"].parent / "book.mp3"  # where "../book.mp3" leads
    outside.write_bytes(b"ID3 elsewhere")
    sub = one["book"] / "sub"
    sub.mkdir()
    (sub / "book.mp3").write_bytes(b"ID3 elsewhere")
    crafted = AudiobookFile(
        name, len(b"ID3 elsewhere"), hashlib.sha256(b"ID3 elsewhere").hexdigest()
    )
    record(one["work"], one["doc"], one["book"], crafted)
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200
    assert response.json()["deleted_files"] == 0
    refused = [k for k in response.json()["kept"] if k["reason"] != "not-recorded"]
    assert [k["reason"] for k in refused] == ["outside"]
    assert refused[0]["folder"] == str(one["book"])  # its project folder, not its own path
    assert outside.read_bytes() == b"ID3 elsewhere"
    assert (sub / "book.mp3").read_bytes() == b"ID3 elsewhere"


def test_s5_a_folder_with_a_parent_step_is_refused(one: dict[str, Any]) -> None:
    sneaky = one["book"] / ".." / one["book"].name
    record(one["work"], one["doc"], sneaky, *(entry(one["book"] / n) for n in one["files"]))
    response = remove(one["client"], one["doc"])
    assert response.json()["deleted_files"] == 0
    assert kept(response) == {one["book"].name: "outside"}
    assert files_of(one["book"]) == one["files"]


def test_s3_a_project_folder_that_is_a_link_is_never_followed(
    one: dict[str, Any], tmp_path: Path
) -> None:
    real = tmp_path / "real books"
    one["book"].rename(real)
    try:
        one["book"].symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    response = remove(one["client"], one["doc"])
    assert kept(response) == {one["book"].name: "link"}
    assert files_of(real) == one["files"]


# ---- other projects (S6) -------------------------------------------------------------------


def test_s6_two_projects_of_the_same_name_keep_each_other_s_audiobook(tmp_path: Path) -> None:
    _app, client, config = server(tmp_path)
    first = made(client, note("One note."), "paper.pdf")
    second = made(client, note("Another note."), "paper.pdf")
    folders = sorted(p.name for p in config.output_folder.iterdir())
    assert folders == ["paper", "paper (2)"]
    other = files_of(config.output_folder / "paper (2)")
    assert remove(client, first["id"]).status_code == 200
    assert not (config.output_folder / "paper").exists()
    assert files_of(config.output_folder / "paper (2)") == other
    assert client.get(f"/api/v1/documents/{second['id']}").status_code == 200


def test_s6_a_file_another_project_lists_too_stays(tmp_path: Path) -> None:
    _app, client, config = server(tmp_path)
    first = made(client, note("One note."), "one.pdf")
    second = made(client, note("Another note."), "two.pdf")
    book = book_folder(config.output_folder, "one.pdf")
    files = files_of(book)
    shared = sorted(files)[0]
    record(config.work_root / second["id"], second["id"], book, entry(book / shared))
    response = remove(client, first["id"])
    assert kept(response) == {shared: "shared"}
    assert files_of(book) == {shared: files[shared]}


# ---- busy, failures and races (S7, S9, S10) --------------------------------------------------


def test_s7_nothing_goes_while_another_process_holds_the_project(one: dict[str, Any]) -> None:
    with work_folder_lock(one["work"]):
        busy = remove(one["client"], one["doc"])
    assert busy.status_code == 409
    assert files_of(one["book"]) == one["files"]
    assert remove(one["client"], one["doc"]).status_code == 200
    assert not one["book"].exists()


def test_s7_nothing_goes_while_a_job_of_this_server_runs(
    one: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "_job_on", lambda state, document_id: "job-1 works on it")
    busy = remove(one["client"], one["doc"])
    assert busy.status_code == 409
    assert files_of(one["book"]) == one["files"]
    assert (one["work"] / "source").is_dir()


def test_s9_a_file_that_can_t_be_deleted_is_named_and_a_second_press_finishes(
    one: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    stuck = one["book"] / sorted(one["files"])[0]
    real = os.unlink

    def unlink(path: Any, *args: Any, **kwargs: Any) -> None:
        if Path(path) == stuck:
            raise OSError(errno.EBUSY, "Device or resource busy", str(path))
        real(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    response = remove(one["client"], one["doc"])
    assert response.status_code == 500
    assert response.json()["error"] == "remove-failed"
    assert response.json()["message"] == f"could not delete {stuck}: Device or resource busy"
    assert stuck.read_bytes() == one["files"][stuck.name]
    assert (one["work"] / "source").is_dir()  # the project is still listed
    assert one["client"].get(f"/api/v1/documents/{one['doc']}").status_code == 200
    monkeypatch.undo()
    again = remove(one["client"], one["doc"])
    assert again.status_code == 200
    assert not one["book"].exists()
    assert not one["work"].exists()


@pytest.mark.skipif(os.name != "nt", reason="only Windows refuses to delete an open file")
def test_s9_a_file_held_open_on_windows_is_named_and_a_second_press_finishes(
    one: dict[str, Any],
) -> None:
    """A real fault, not a patched one (#569): every audiobook file is held
    open, so the first one of the record can't go and nothing of the project goes."""
    book, files = one["book"], one["files"]
    held = [(book / name).open("rb") for name in sorted(files)]
    try:
        response = remove(one["client"], one["doc"])
        assert response.status_code == 500, response.text
        assert response.json()["error"] == "remove-failed"
        assert response.json()["message"].startswith(f"could not delete {first_file(one)}: ")
        assert files_of(book) == files
        assert (one["work"] / "source").is_dir()  # the project is still listed
        assert one["client"].get(f"/api/v1/documents/{one['doc']}").status_code == 200
    finally:
        for file in held:
            file.close()
    again = remove(one["client"], one["doc"])
    assert again.status_code == 200, again.text
    assert again.json()["deleted_files"] == len(files)
    assert not book.exists()
    assert not one["work"].exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows has no folder write bit")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes anyway")
def test_s9_a_read_only_folder_is_named_and_a_second_press_finishes(
    one: dict[str, Any],
) -> None:
    """A real fault, not a patched one (#569): the audiobook folder is made
    read-only, so its first recorded file can't be deleted."""
    book, files = one["book"], one["files"]
    book.chmod(0o555)
    try:
        response = remove(one["client"], one["doc"])
        assert response.status_code == 500, response.text
        assert response.json()["error"] == "remove-failed"
        assert response.json()["message"].startswith(f"could not delete {first_file(one)}: ")
        assert files_of(book) == files
        assert (one["work"] / "source").is_dir()
        assert one["client"].get(f"/api/v1/documents/{one['doc']}").status_code == 200
    finally:
        book.chmod(0o755)
    again = remove(one["client"], one["doc"])
    assert again.status_code == 200, again.text
    assert again.json()["deleted_files"] == len(files)
    assert not book.exists()
    assert not one["work"].exists()


def test_s9_a_read_only_audiobook_file_is_made_writable_once(
    one: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to delete a read-only file; here every system does."""
    locked = one["book"] / sorted(one["files"])[0]
    locked.chmod(stat.S_IREAD)
    real = os.unlink
    refused: list[str] = []

    def windows_like(path: Any, *args: Any, **kwargs: Any) -> None:
        if Path(path).parent == one["book"] and not os.stat(path).st_mode & stat.S_IWUSR:
            refused.append(Path(path).name)
            raise PermissionError(errno.EACCES, "Access is denied", str(path))
        real(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", windows_like)
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert refused == [locked.name]
    assert not one["book"].exists()


def test_s10_a_folder_swapped_for_a_link_after_the_check_is_not_followed(
    one: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    real_plan = removal.plan

    def swapped(*args: Any, **kwargs: Any) -> removal.AudiobookPlan:
        planned = real_plan(*args, **kwargs)
        one["book"].rename(elsewhere)  # same files, same hashes, now reached through a link
        one["book"].symlink_to(elsewhere, target_is_directory=True)
        return planned

    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    monkeypatch.setattr(api, "plan", swapped)
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == 0
    assert set(kept(response).values()) == {"changed"}
    assert files_of(elsewhere) == one["files"]


def test_s10_a_folder_swapped_after_the_check_keeps_the_person_s_clutter(
    one: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The folder is checked again before its entries are listed (#569): a
    link to a folder of the person's that holds only a `.DS_Store` deletes nothing."""
    mine, moved = tmp_path / "mine", tmp_path / "moved"
    mine.mkdir()
    (mine / ".DS_Store").write_bytes(b"the person's own")
    real_plan = removal.plan

    def swapped(*args: Any, **kwargs: Any) -> removal.AudiobookPlan:
        planned = real_plan(*args, **kwargs)
        one["book"].rename(moved)
        one["book"].symlink_to(mine, target_is_directory=True)
        return planned

    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    monkeypatch.setattr(api, "plan", swapped)
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == 0
    assert kept(response) == {one["book"].name: "changed"}
    assert response.json()["kept"][0]["folder"] == str(one["book"])
    assert files_of(mine) == {".DS_Store": b"the person's own"}
    assert files_of(moved) == one["files"]


def test_s10_a_file_swapped_for_a_link_after_the_check_is_not_followed(
    one: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = sorted(one["files"])[0]
    target = tmp_path / "elsewhere.mp3"
    real_plan = removal.plan

    def swapped(*args: Any, **kwargs: Any) -> removal.AudiobookPlan:
        planned = real_plan(*args, **kwargs)
        (one["book"] / name).rename(target)
        (one["book"] / name).symlink_to(target)
        return planned

    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    monkeypatch.setattr(api, "plan", swapped)
    response = remove(one["client"], one["doc"])
    assert kept(response) == {name: "changed"}
    assert response.json()["kept"][0]["folder"] == str(one["book"])
    assert target.read_bytes() == one["files"][name]


def test_s10_a_folder_above_swapped_after_the_check_is_seen_by_its_real_path(
    one: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The output folder is swapped for a link to a folder of the person's that holds a
    folder of the same name (#569): the project folder lstats as a plain
    folder, so only its real path shows the change, and nothing of the person's goes."""
    output, book = one["config"].output_folder, one["book"]
    moved, mine = tmp_path / "moved output", tmp_path / "mine"
    theirs = mine / book.name
    theirs.mkdir(parents=True)
    (theirs / ".DS_Store").write_bytes(b"the person's own")
    for name, data in one["files"].items():
        (theirs / name).write_bytes(data)  # same names, same bytes: only the place differs
    real_plan = removal.plan

    def swapped(*args: Any, **kwargs: Any) -> removal.AudiobookPlan:
        planned = real_plan(*args, **kwargs)
        output.rename(moved)
        output.symlink_to(mine, target_is_directory=True)
        return planned

    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    monkeypatch.setattr(api, "plan", swapped)
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == 0
    assert files_of(theirs) == {".DS_Store": b"the person's own", **one["files"]}
    assert files_of(moved / book.name) == one["files"]
    stayed = {k["path"]: (k["reason"], k["folder"]) for k in response.json()["kept"]}
    assert stayed == {
        str(book): ("changed", str(book)),
        **{str(book / name): ("changed", str(book)) for name in one["files"]},
    }


# ---- the folder goes by rmdir only (S11) -----------------------------------------------------


@pytest.mark.parametrize(
    ("name", "data", "stays"),
    [
        ("notes.txt", b"mine", True),
        (".DS_Store", b"\x00\x00\x00\x01Bud1", False),
        ("Thumbs.db", b"thumbs", False),
        ("desktop.ini", b"[.ShellClassInfo]", False),
        (".DS_Store", b"x" * (removal.CLUTTER_LIMIT + 1), True),
    ],
)
def test_s11_only_system_clutter_lets_the_folder_go(
    one: dict[str, Any], name: str, data: bytes, stays: bool
) -> None:
    (one["book"] / name).write_bytes(data)
    assert remove(one["client"], one["doc"]).status_code == 200
    assert one["book"].exists() is stays
    if stays:
        assert files_of(one["book"]) == {name: data}


def test_s11_clutter_that_is_a_link_keeps_the_folder(one: dict[str, Any], tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"mine")
    try:
        (one["book"] / ".DS_Store").symlink_to(target)
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    response = remove(one["client"], one["doc"])
    assert kept(response) == {".DS_Store": "not-recorded"}
    assert (one["book"] / ".DS_Store").is_symlink()
    assert target.read_bytes() == b"mine"


def test_s11_a_folder_inside_the_project_folder_keeps_it(one: dict[str, Any]) -> None:
    (one["book"] / "extra").mkdir()
    (one["book"] / "extra" / "file.txt").write_text("mine")
    response = remove(one["client"], one["doc"])
    assert kept(response) == {"extra": "not-recorded"}
    assert (one["book"] / "extra" / "file.txt").read_text() == "mine"


# ---- audiobooks made before #469 -------------------------------------------------------


def test_s12_an_audiobook_made_before_its_own_folder_stays_and_is_named(
    one: dict[str, Any],
) -> None:
    """Flat in the output folder, with no project folder: never deleted (D-751, Q4)."""
    output, book, work = one["config"].output_folder, one["book"], one["work"]
    for name in one["files"]:
        (book / name).rename(output / name)
    book.rmdir()
    (work / PROJECT).unlink()
    write_record(work, one["doc"], output)
    page = browser(one["app"], one["config"]).get(f"/documents/{one['doc']}").text
    assert f"Your earlier audiobook in {output.absolute()} stays" in page
    assert 'class="remove-keep"' not in page
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200
    assert response.json()["deleted_files"] == 0
    assert files_of(output) == one["files"]


# ---- long names (S13) ------------------------------------------------------------------------


def test_s13_the_longest_names_are_written_and_removed(tmp_path: Path) -> None:
    """A 60-character project folder and a 120-character file name, as `output.names`
    cuts them: they go on every system, Windows' path limit included."""
    _app, client, config = server(tmp_path)
    doc = made(client, note(), "x" * 90 + ".pdf")
    book = book_folder(config.output_folder, "x" * 90 + ".pdf")
    assert len(book.name) == 60
    long = book / ("c" * 116 + ".mp3")
    long.write_bytes(b"ID3 a chapter")
    work = config.work_root / doc["id"]
    record_files(work, doc["id"], book, [long])
    response = remove(client, doc["id"])
    assert response.status_code == 200, response.text
    assert not book.exists()


# ---- the box (R7) ----------------------------------------------------------------------------


def test_the_box_names_what_goes_and_the_keep_box_in_german(one: dict[str, Any]) -> None:
    page = browser(one["app"], one["config"])
    german = page.get(f"/documents/{one['doc']}", headers={"Accept-Language": "de"}).text
    assert f"Hörbuchdateien in {one['book']} werden ebenfalls gelöscht" in german
    assert "Hörbuchdateien behalten" in german
    english = page.get(f"/documents/{one['doc']}").text
    keep = f'<input type="checkbox" class="remove-keep" id="remove-keep-{one["doc"]}">'
    assert keep in english  # deleted by default
    assert english.count('<button type="button" class="danger remove-now"') == 1


def test_a_record_that_can_t_be_read_says_so_and_nothing_is_deleted(one: dict[str, Any]) -> None:
    """Not the line about an audiobook made before #469, which would be untrue (#569):
    the box says the record can't be read and names it."""
    record_path = one["work"] / PROJECT
    record_path.write_text("{not json", encoding="utf-8")
    page = browser(one["app"], one["config"])
    english = page.get(f"/documents/{one['doc']}").text
    assert (
        f"Your audiobook files stay: sci2audio can’t read its record of them, “{record_path}”."  # noqa: RUF001
        in english
    )
    assert "<p>Your earlier audiobook" not in english
    assert 'class="remove-keep"' not in english
    assert 'data-earlier=""' in english
    german = page.get(f"/documents/{one['doc']}", headers={"Accept-Language": "de"}).text
    assert (
        f"Ihre Hörbuchdateien bleiben: sci2audio kann seine Aufzeichnung darüber nicht lesen, "
        f"„{record_path}“." in german
    )
    response = remove(one["client"], one["doc"])
    assert response.status_code == 200, response.text
    assert response.json()["deleted_files"] == 0
    assert files_of(one["book"]) == one["files"]


def test_the_message_after_the_press_in_german_names_the_folder() -> None:
    """The script's strings (#569): files counted with their folder, whole
    folders in a sentence of their own."""
    de = i18n.strings("de")
    script = json.loads(de.script_json())
    assert {"remove.kept_some.one", "remove.kept_folder.other"} <= set(script)
    assert de.t("remove.kept_some", n=2, folder="/b/paper") == (
        "2 Dateien sind in /b/paper geblieben: sci2audio hat sie nicht geschrieben, "
        "oder sie haben sich seitdem geändert."
    )
    assert de.t("remove.kept_folder", n=1, folder="/b/paper") == (
        "Der Ordner /b/paper bleibt, wie er ist: sci2audio konnte nicht sicher sein, "
        "dass es noch der Hörbuchordner ist, den es erstellt hat."
    )
    assert de.t("remove.kept_folder", n=3, folder="/b/paper").startswith(
        "3 Hörbuchordner bleiben, wie sie sind, darunter /b/paper: "
    )


def test_the_box_counts_only_files_still_there(one: dict[str, Any]) -> None:
    gone = sorted(one["files"])[0]
    (one["book"] / gone).unlink()
    text = browser(one["app"], one["config"]).get("/").text
    left = len(one["files"]) - 1
    book = one["book"]
    line = (
        f"The {left} audiobook files in {book} go too"
        if left > 1
        else (f"The audiobook file in {book} goes too")
    )
    assert line in text


def test_the_record_is_read_as_the_button_is_pressed_not_as_drawn(one: dict[str, Any]) -> None:
    """The box counts by size; the hashes are checked only when the button is pressed, so
    a file changed after the box was drawn still stays."""
    browser(one["app"], one["config"]).get("/")
    name = sorted(one["files"])[0]
    (one["book"] / name).write_bytes(b"changed after the box was drawn")
    response = remove(one["client"], one["doc"])
    assert kept(response) == {name: "changed"}
