"""The server and the project folders (#469, D-747, D-748): the old working folders are
moved before anything is served, and one that could not be moved is listed and used where
it is, so no document is ever missing."""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

import pytest
from project_helpers import V1_3, can_link, old_folder, tree_digest
from web_helpers import (
    app_and_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    program,
    upload,
)

from sci2audio.app.lock import work_folder_lock
from sci2audio.web.config import default_work_root, server_config
from sci2audio.web.documents import DocumentStore
from sci2audio.web.tasks import PREVIEW_FOLDER

pytestmark = pytest.mark.usefixtures("offline")

LIMITS = {"upload_limit": 10_000_000, "text_limit": 10_000_000}


def old_document(legacy: Path, data: bytes, name: str = "paper.pdf") -> tuple[str, Path]:
    """A working folder as a version before #469 left it, holding `data` as `name`."""
    project = hashlib.sha256(data).hexdigest()[:16]
    files = {key: value for key, value in V1_3.items() if not key.startswith("source/")}
    folder = old_folder(legacy, project, files)
    (folder / "source").mkdir()
    (folder / "source" / name).write_bytes(data)
    return project, folder


def test_the_server_moves_the_old_folders_before_serving(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    project, folder = old_document(legacy, pdf_bytes())
    before = tree_digest(folder)
    app, config = app_and_config(tmp_path, legacy_root=legacy)
    listed = program(app, config).get("/api/v1/documents").json()
    assert [(d["id"], d["name"]) for d in listed] == [(project, "paper.pdf")]
    assert tree_digest(config.work_root / project) == before
    assert not legacy.exists()


def test_a_folder_that_can_t_be_moved_is_listed_and_used_where_it_is(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    data = pdf_bytes()
    project, folder = old_document(legacy, data)
    with work_folder_lock(folder):  # a job of an older version holds it at the start
        app, config = app_and_config(tmp_path, legacy_root=legacy)
    client = program(app, config)
    assert [d["id"] for d in client.get("/api/v1/documents").json()] == [project]
    assert not (config.work_root / project).exists()
    # opening the same bytes again keeps the copy beside the folder's records
    assert upload(client, data, "again.pdf")["id"] == project
    assert (folder / "source" / "again.pdf").read_bytes() == data
    assert not (config.work_root / project).exists()
    # a removal works on it as on any other (D-353 to D-356)
    assert client.delete(f"/api/v1/documents/{project}?keep_audiobook=false").status_code == 200
    assert not folder.exists()
    assert client.get("/api/v1/documents").json() == []


def test_the_new_folder_wins_when_both_hold_the_file(tmp_path: Path) -> None:
    legacy, root = tmp_path / "legacy", tmp_path / "projects"
    data = pdf_bytes()
    project, _ = old_document(legacy, data, "old.pdf")
    (root / project / "source").mkdir(parents=True)
    (root / project / "source" / "new.pdf").write_bytes(data)
    store = DocumentStore(root, legacy_root=legacy, **LIMITS)
    document = store.get(project)
    assert document is not None
    assert document.folder == root / project
    assert [d.name for d in store.all()] == ["new.pdf"]


def test_an_old_folder_whose_file_moved_already_is_not_listed_twice(tmp_path: Path) -> None:
    legacy, root = tmp_path / "legacy", tmp_path / "projects"
    data = pdf_bytes()
    project, _ = old_document(legacy, data)
    (root / project / "source").mkdir(parents=True)
    (root / project / "source" / "paper.pdf").write_bytes(data)
    store = DocumentStore(root, legacy_root=legacy, **LIMITS)
    assert [d.folder for d in store.all()] == [root / project]


def test_a_new_folder_without_its_file_still_lists_the_old_one(tmp_path: Path) -> None:
    """A move cut off before the copy of the file went over: the old folder still has it."""
    legacy, root = tmp_path / "legacy", tmp_path / "projects"
    project, folder = old_document(legacy, pdf_bytes())
    (root / project).mkdir(parents=True)
    (root / project / "position.json").write_text("{}")
    store = DocumentStore(root, legacy_root=legacy, **LIMITS)
    assert [d.folder for d in store.all()] == [folder]


def test_without_an_old_root_only_the_project_folders_count(tmp_path: Path) -> None:
    project, _ = old_document(tmp_path / "legacy", pdf_bytes())
    store = DocumentStore(tmp_path / "projects", **LIMITS)
    assert store.all() == []
    assert store.get(project) is None


def test_the_old_preview_folder_moves_when_the_new_one_is_free(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    (legacy / PREVIEW_FOLDER).mkdir(parents=True)
    (legacy / PREVIEW_FOLDER / "voice.wav").write_bytes(b"RIFF")
    _, config = app_and_config(tmp_path, legacy_root=legacy)
    assert (config.work_root / PREVIEW_FOLDER / "voice.wav").read_bytes() == b"RIFF"
    assert not legacy.exists()


def test_the_server_s_folders_are_the_project_and_the_old_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sci2audio.app import config as app_config

    monkeypatch.setattr(app_config.platformdirs, "user_data_path", lambda *a, **k: tmp_path / "d")
    monkeypatch.setattr(app_config.platformdirs, "user_cache_path", lambda *a, **k: tmp_path / "c")
    config = server_config(8080)
    assert config.work_root == default_work_root() == tmp_path / "d" / "projects"
    assert config.legacy_root == tmp_path / "c" / "jobs"


def test_a_linked_old_preview_folder_is_not_moved(tmp_path: Path) -> None:
    """#532: a link (or a junction) in place of the old preview
    folder stays; nothing is moved through it."""
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    legacy, elsewhere = tmp_path / "legacy", tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "voice.wav").write_bytes(b"RIFF")
    legacy.mkdir()
    os.symlink(elsewhere, legacy / PREVIEW_FOLDER, target_is_directory=True)
    _, config = app_and_config(tmp_path, legacy_root=legacy)
    assert not os.path.lexists(config.work_root / PREVIEW_FOLDER)
    assert (legacy / PREVIEW_FOLDER).is_symlink()
    assert [p.name for p in elsewhere.iterdir()] == ["voice.wav"]


def test_an_old_folder_that_is_a_link_is_never_listed_or_used(tmp_path: Path) -> None:
    """#532: `<old root>/<id>` as a link to a folder holding
    `source/` is not listed, not opened through the link, and a new upload of the same
    bytes goes into the project root."""
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    legacy, root = tmp_path / "legacy", tmp_path / "projects"
    data = pdf_bytes()
    project, folder = old_document(tmp_path / "elsewhere", data)
    before = tree_digest(folder)
    legacy.mkdir()
    os.symlink(folder, legacy / project, target_is_directory=True)
    store = DocumentStore(root, legacy_root=legacy, **LIMITS)
    assert store.all() == []
    assert store.get(project) is None
    stored = store.store("paper.pdf", io.BytesIO(data))
    assert stored.folder == root / project
    assert tree_digest(folder) == before
