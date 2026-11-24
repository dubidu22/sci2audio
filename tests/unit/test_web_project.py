"""The project's own audiobook folder and its record of the files written (#469, D-749,
D-750), and the acceptance walk: a whole web job writes nowhere else (MT12)."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import platformdirs
import pytest
from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf
from project_helpers import can_link
from test_web_player import make, player_data, server, work_of
from web_helpers import (
    PORT,
    book_folder,
    offline,  # noqa: F401 - fixture
    program,
    set_capture,
    wait,
)

from sci2audio.output.names import older
from sci2audio.web import create_app, project
from sci2audio.web.config import server_config
from sci2audio.web.player import write_record
from sci2audio.web.project import (
    NAME_BYTES,
    NAME_CHARS,
    PROJECT,
    AudiobookFile,
    ProjectError,
    audiobook_folder,
    folder_name,
    read_project,
    record_files,
)

pytestmark = pytest.mark.usefixtures("offline")

ID = "00000000000000a0"


# ---- the folder's name ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("opened", "name"),
    [
        ("Smith 2024 attention.pdf", "Smith 2024 attention"),
        ("a:b|c?.epub", "a b c"),  # characters Windows forbids
        ("C:paper.pdf", "C paper"),  # never read as a drive, on any system
        ("dir\\paper.pdf", "dir paper"),  # nor a backslash as a folder
        ("CON.pdf", "_CON"),  # a name Windows reserves
        ("notes. .txt", "notes"),  # no trailing dots or spaces
        ("͸odd\ud800.md", "odd"),  # an unassigned and a surrogate code point (#491, #493)
        (".pdf", "pdf"),  # a name of a suffix only is a name
        ("...", "audiobook"),
    ],
)
def test_the_folder_is_named_after_the_opened_file(opened: str, name: str) -> None:
    assert folder_name(opened) == name


def test_a_long_name_is_cut_in_characters_and_in_bytes() -> None:
    assert len(folder_name("x" * 300 + ".pdf")) == NAME_CHARS
    greek = folder_name("λ" * 200 + ".pdf")
    assert len(greek.encode()) <= NAME_BYTES
    assert greek == "λ" * (NAME_BYTES // 2)


# ---- making the folder ------------------------------------------------------------------


def test_the_folder_is_made_recorded_and_kept(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    folder = audiobook_folder(work, ID, "paper.pdf", out)
    assert folder == out / "paper"
    assert folder.is_dir()
    project = read_project(work, ID)
    assert project is not None
    assert (project.name, project.folders()) == ("paper", [folder])
    # opened again under another name: the same folder
    assert audiobook_folder(work, ID, "renamed.pdf", out) == folder
    assert read_project(work, ID) == project


def test_a_folder_or_file_that_exists_is_never_taken_over(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    (out / "paper").mkdir(parents=True)
    (out / "paper" / "mine.mp3").write_bytes(b"the person's")
    (out / "paper (2)").write_text("a file")
    folder = audiobook_folder(work, ID, "paper.pdf", out)
    assert folder == out / "paper (3)"
    assert (out / "paper" / "mine.mp3").read_bytes() == b"the person's"
    assert (out / "paper (2)").read_text() == "a file"


def test_a_numbered_long_name_still_fits(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    long = "y" * 100
    (out / folder_name(long)).mkdir(parents=True)
    folder = audiobook_folder(work, ID, f"{long}.pdf", out)
    assert folder.name == "y" * (NAME_CHARS - 4) + " (2)"


def _old_volume(monkeypatch: pytest.MonkeyPatch, refused: Callable[[str], bool]) -> list[str]:
    """A volume whose file system refuses a folder name with EILSEQ when `refused` says so
    (an output folder on an older APFS disk or a share, #584); returns every name asked for."""
    real = os.mkdir
    asked: list[str] = []

    def mkdir(path: Any, mode: int = 0o777, *args: Any, **kwargs: Any) -> None:
        name = os.path.basename(os.fspath(path))
        asked.append(name)
        if refused(name):
            raise OSError(errno.EILSEQ, "Illegal byte sequence", os.fspath(path))
        real(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", mkdir)
    return asked


def _new_characters(name: str) -> bool:
    return older(name) != name


def test_a_folder_name_the_volume_refuses_is_made_from_its_old_characters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    out.mkdir()
    _old_volume(monkeypatch, _new_characters)
    folder = audiobook_folder(work, ID, "paper \U0001f3a7.pdf", out)
    assert folder == out / "paper"
    assert folder.is_dir()
    found = read_project(work, ID)
    assert found is not None
    # the project keeps its name: another output folder may well take it
    assert (found.name, found.folders()) == ("paper \U0001f3a7", [folder])
    assert audiobook_folder(work, ID, "paper \U0001f3a7.pdf", out) == folder


def test_a_retried_folder_name_never_takes_over_an_existing_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    (out / "paper").mkdir(parents=True)
    (out / "paper" / "mine.mp3").write_bytes(b"the person's")
    (out / "paper (2)").write_text("a file")
    _old_volume(monkeypatch, _new_characters)
    folder = audiobook_folder(work, ID, "paper \U0001f3a7.pdf", out)
    assert folder == out / "paper (3)"
    assert (out / "paper" / "mine.mp3").read_bytes() == b"the person's"
    assert (out / "paper (2)").read_text() == "a file"
    assert sorted(p.name for p in out.iterdir()) == ["paper", "paper (2)", "paper (3)"]


@pytest.mark.parametrize(
    ("opened", "refused", "made"),
    [
        ("\U0001f3a7\U0001f3a7.pdf", _new_characters, "audiobook"),  # nothing old is left
        ("paper \U0001f3a7.pdf", lambda name: name.startswith("paper"), "audiobook"),
    ],
)
def test_a_folder_name_refused_again_falls_back_to_audiobook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    opened: str,
    refused: Callable[[str], bool],
    made: str,
) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    out.mkdir()
    _old_volume(monkeypatch, refused)
    assert audiobook_folder(work, ID, opened, out) == out / made


def test_the_last_fallback_never_takes_over_an_existing_audiobook_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the last name is tried without a refusal to fall back on: it must still number (D-749)
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    (out / "audiobook").mkdir(parents=True)
    (out / "audiobook" / "mine.mp3").write_bytes(b"the person's")
    _old_volume(monkeypatch, _new_characters)
    folder = audiobook_folder(work, ID, "\U0001f3a7\U0001f3a7.pdf", out)
    assert folder == out / "audiobook (2)"
    assert sorted(p.name for p in (out / "audiobook").iterdir()) == ["mine.mp3"]
    assert (out / "audiobook" / "mine.mp3").read_bytes() == b"the person's"
    assert sorted(p.name for p in out.iterdir()) == ["audiobook", "audiobook (2)"]


def test_another_error_making_the_folder_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    out.mkdir()
    real = os.mkdir
    asked: list[str] = []

    def mkdir(path: Any, mode: int = 0o777, *args: Any, **kwargs: Any) -> None:
        if os.path.dirname(os.fspath(path)) != os.fspath(out):
            real(path, mode, *args, **kwargs)
            return
        asked.append(os.path.basename(os.fspath(path)))
        raise OSError(errno.EACCES, "Permission denied", os.fspath(path))

    monkeypatch.setattr(os, "mkdir", mkdir)
    with pytest.raises(ProjectError, match="Permission denied"):
        audiobook_folder(work, ID, "paper \U0001f3a7.pdf", out)
    assert asked == ["paper \U0001f3a7"]
    assert read_project(work, ID) is None


def test_two_documents_with_the_same_name_get_two_folders(tmp_path: Path) -> None:
    out = tmp_path / "out"
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    assert audiobook_folder(first, ID, "paper.pdf", out) == out / "paper"
    assert audiobook_folder(second, "00000000000000b0", "paper.pdf", out) == out / "paper (2)"


def test_a_folder_the_person_removed_is_made_again(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    folder = audiobook_folder(work, ID, "paper.pdf", out)
    folder.rmdir()
    assert audiobook_folder(work, ID, "paper.pdf", out) == out / "paper"


def test_a_recorded_folder_replaced_by_a_link_is_never_used(tmp_path: Path) -> None:
    if not can_link(tmp_path):
        pytest.skip("this user can't make links")
    work, out, elsewhere = tmp_path / "work", tmp_path / "out", tmp_path / "elsewhere"
    work.mkdir()
    elsewhere.mkdir()
    folder = audiobook_folder(work, ID, "paper.pdf", out)
    folder.rmdir()
    os.symlink(elsewhere, folder, target_is_directory=True)
    assert audiobook_folder(work, ID, "paper.pdf", out) == out / "paper (2)"


def test_another_output_folder_adds_a_second_folder(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    one = audiobook_folder(work, ID, "paper.pdf", tmp_path / "one")
    two = audiobook_folder(work, ID, "paper.pdf", tmp_path / "two")
    project = read_project(work, ID)
    assert project is not None
    assert project.folders() == [one, two]
    assert audiobook_folder(work, ID, "paper.pdf", tmp_path / "one") == one


def test_a_record_this_version_can_t_read_is_never_written_over(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    (work / PROJECT).write_text("{ broken")
    with pytest.raises(ProjectError, match="can't be read"):
        audiobook_folder(work, ID, "paper.pdf", out)
    assert (work / PROJECT).read_text() == "{ broken"
    assert not out.exists()


# ---- the record ---------------------------------------------------------------------------


def good_record(folder: Path) -> dict[str, Any]:
    return {
        "format": "sci2audio-web-project",
        "version": 1,
        "document": ID,
        "name": "paper",
        "audiobooks": [
            {"folder": str(folder), "files": [{"name": "a.mp3", "bytes": 3, "sha256": "0" * 64}]}
        ],
    }


@pytest.mark.parametrize(
    "change",
    [
        {"format": "other"},
        {"version": 2},
        {"version": True},
        {"document": "00000000000000b0"},
        {"name": 3},
        {"audiobooks": [{"folder": "relative", "files": []}]},
        {"audiobooks": [{"folder": "/x\u0000y", "files": []}]},
        {"audiobooks": [{"folder": "/x", "files": [{"name": "", "bytes": 1, "sha256": "0" * 64}]}]},
        {
            "audiobooks": [
                {"folder": "/x", "files": [{"name": "a", "bytes": -1, "sha256": "0" * 64}]}
            ]
        },
        {"audiobooks": [{"folder": "/x", "files": [{"name": "a", "bytes": 1, "sha256": "XY"}]}]},
        {"audiobooks": [{"files": []}]},
    ],
)
def test_a_record_that_is_not_ours_reads_as_none(tmp_path: Path, change: dict[str, Any]) -> None:
    (tmp_path / PROJECT).write_text(json.dumps({**good_record(tmp_path), **change}))
    assert read_project(tmp_path, ID) is None


def test_a_good_record_reads_back(tmp_path: Path) -> None:
    (tmp_path / PROJECT).write_text(json.dumps(good_record(tmp_path)))
    project = read_project(tmp_path, ID)
    assert project is not None
    assert project.audiobooks[0].files == (AudiobookFile("a.mp3", 3, "0" * 64),)


def test_a_linked_or_huge_record_reads_as_none(tmp_path: Path) -> None:
    huge = json.dumps(good_record(tmp_path)) + " " * (300 * 1024)  # valid, but too large
    (tmp_path / PROJECT).write_text(huge)
    assert read_project(tmp_path, ID) is None
    (tmp_path / PROJECT).write_text(huge.rstrip())
    assert read_project(tmp_path, ID) is not None  # the same record, small enough
    if can_link(tmp_path):
        real = tmp_path / "real.json"
        real.write_text(json.dumps(good_record(tmp_path)))
        (tmp_path / PROJECT).unlink()
        os.symlink(real, tmp_path / PROJECT)
        assert read_project(tmp_path, ID) is None


def test_written_files_are_recorded_with_size_and_hash(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    folder = audiobook_folder(work, ID, "paper.pdf", out)
    (folder / "a.mp3").write_bytes(b"one")
    (folder / "b.mp3").write_bytes(b"two")
    (tmp_path / "elsewhere.mp3").write_bytes(b"not here")
    record_files(work, ID, folder, [folder / "a.mp3", folder / "b.mp3", tmp_path / "elsewhere.mp3"])
    project = read_project(work, ID)
    assert project is not None

    assert project.audiobooks[0].files == (
        AudiobookFile("a.mp3", 3, hashlib.sha256(b"one").hexdigest()),
        AudiobookFile("b.mp3", 3, hashlib.sha256(b"two").hexdigest()),
    )
    # a later run replaces a.mp3 and writes c.mp3; b.mp3 of the earlier run stays recorded
    (folder / "a.mp3").write_bytes(b"one, again")
    (folder / "c.mp3").write_bytes(b"three")
    record_files(work, ID, folder, [folder / "a.mp3", folder / "c.mp3"])
    project = read_project(work, ID)
    assert project is not None
    assert [(f.name, f.bytes) for f in project.audiobooks[0].files] == [
        ("a.mp3", 10),
        ("b.mp3", 3),
        ("c.mp3", 5),
    ]
    # a file the person deleted leaves the record
    (folder / "b.mp3").unlink()
    record_files(work, ID, folder, [])
    project = read_project(work, ID)
    assert project is not None
    assert [f.name for f in project.audiobooks[0].files] == ["a.mp3", "c.mp3"]


# ---- through the server -------------------------------------------------------------------


def test_the_audiobook_goes_into_the_project_s_folder_and_is_recorded(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    folder = book_folder(config.output_folder)
    assert {f["folder"] for f in made["job"]["files"]} == {str(folder)}
    project = read_project(work_of(config, doc), doc)
    assert project is not None
    assert project.folders() == [folder]
    recorded = {f.name for f in project.audiobooks[0].files}
    assert recorded == {f["name"] for f in made["job"]["files"]}
    assert recorded == {path.name for path in folder.iterdir()}


def test_two_documents_named_alike_keep_their_own_audiobooks(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    first = make(client, name="paper.pdf")
    second = make(client, make_pdf([Text("Another paper.", 72, 100)]), "paper.pdf")
    assert {f["folder"] for f in first["job"]["files"]} == {str(config.output_folder / "paper")}
    assert {f["folder"] for f in second["job"]["files"]} == {
        str(config.output_folder / "paper (2)")
    }
    for made in (first, second):
        page = client.get(f"/documents/{made['doc']['id']}/listen").text
        assert page.count('class="s"') > 0


def test_a_project_without_a_record_gets_one_on_its_next_audiobook(tmp_path: Path) -> None:
    """A project moved from before #469 has no project.json (A7): its next audiobook
    gets a recorded folder of its own, and a folder already there is never taken over."""
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    first = book_folder(config.output_folder)
    before = {path.name: path.read_bytes() for path in first.iterdir()}
    (work_of(config, doc) / PROJECT).unlink()
    again = client.post("/api/v1/jobs", json={"kind": "audio", "document": doc}).json()
    assert wait(client, again["id"])["state"] == "done"
    project = read_project(work_of(config, doc), doc)
    assert project is not None
    assert project.folders() == [config.output_folder / "paper (2)"]
    assert {path.name: path.read_bytes() for path in first.iterdir()} == before


def test_a_whole_web_job_writes_only_into_its_project_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MT12, the acceptance of #469: open, analyse, make the audiobook, listen, save a
    position, capture a mark; every file is in the project data folder, the project's
    audiobook folder, the settings file or the voice folder."""
    home = tmp_path / "home"
    for name, folder in {
        "user_data_path": home / "data",
        "user_cache_path": home / "cache",
        "user_config_path": home / "config",
        "user_documents_path": home / "Documents",
    }.items():
        monkeypatch.setattr(platformdirs, name, lambda *a, _f=folder, **k: _f)
    voice = FakeVoice()
    config = server_config(PORT)
    client = program(create_app(config, voice=lambda models: voice.source()), config)
    assert client.put("/api/v1/settings", json={"speed": 1.1}).status_code == 200
    made = make(client)
    doc = made["doc"]["id"]
    analysed = client.post("/api/v1/jobs", json={"kind": "script", "document": doc})
    assert wait(client, analysed.json()["id"])["state"] == "done"
    page = client.get(f"/documents/{doc}/listen").text
    data = player_data(page)
    stamp = data["audiobook"]
    body = {"chapter": 0, "time": 1.0, "audiobook": stamp}
    assert client.post(f"/api/v1/documents/{doc}/position", json=body).status_code == 204
    set_capture(client, doc, "mark", 0, stamp)
    client.get("/")
    allowed = [
        config.work_root / doc,
        book_folder(config.output_folder),
        config.config_file,
        config.models_dir,
    ]
    written = [p for p in home.rglob("*") if p.is_file()]
    assert written
    stray = [p for p in written if not any(p == a or a in p.parents for a in allowed)]
    assert stray == []
    assert config.work_root.is_relative_to(home / "data")
    assert config.output_folder == home / "Documents" / "sci2audio"
    assert (config.work_root / doc / "position.json").is_file()
    assert (config.work_root / doc / "captures.json").is_file()
    assert not (home / "cache").exists()


# ---- #552 ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["../escape", "ABSOLUTE", "a/b", "a\\b", ".", "..", "", "x" * 61])
def test_r1_a_record_whose_name_is_no_folder_name_reads_as_none_and_makes_nothing(
    tmp_path: Path, name: str
) -> None:
    """The record's name is used as a folder name: one `folder_name` would not make reads
    as no record, so the job fails naming the record and nothing is made anywhere."""
    if name == "ABSOLUTE":
        name = str(tmp_path / "absolute")
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    (work / PROJECT).write_text(json.dumps({**good_record(out / "paper"), "name": name}))
    assert read_project(work, ID) is None
    before = sorted(tmp_path.rglob("*"))
    with pytest.raises(ProjectError, match="can't be read"):
        audiobook_folder(work, ID, "paper.pdf", out)
    assert sorted(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("name", ["../escape", "a/b", "..", ""])
def test_r1_a_folder_is_only_ever_made_directly_in_the_output_folder(
    tmp_path: Path, name: str
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ProjectError, match="is not a folder name"):
        project._make_folder(out, name)
    assert sorted(tmp_path.rglob("*")) == [out]


def test_r2_a_folder_made_again_is_recorded_once(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    folder = audiobook_folder(work, ID, "paper.pdf", out)
    (folder / "a.mp3").write_bytes(b"one")
    record_files(work, ID, folder, [folder / "a.mp3"])
    (folder / "a.mp3").unlink()
    folder.rmdir()  # the person deleted it
    assert audiobook_folder(work, ID, "paper.pdf", out) == folder
    found = read_project(work, ID)
    assert found is not None
    assert found.folders() == [folder]
    assert found.audiobooks[0].files == ()


def test_r3_a_version_before_the_record_still_finds_the_audiobook(tmp_path: Path) -> None:
    """Plan A7, the old reader: what a version before #469 reads, `audiobook.json` alone."""
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    (work_of(config, doc) / PROJECT).unlink()
    page = client.get(f"/documents/{doc}/listen").text
    assert page.count('class="s"') > 0


def test_r3_an_audiobook_made_before_its_own_folder_plays_and_stays(tmp_path: Path) -> None:
    """Plan A7, the old file: audiobook files flat in the output folder and no
    `project.json` still play; the next audiobook goes into the project's own folder and
    every flat file keeps its bytes."""
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    work, out = work_of(config, doc), config.output_folder.absolute()
    book = book_folder(out)
    for path in list(book.iterdir()):
        path.rename(out / path.name)
    book.rmdir()
    (work / PROJECT).unlink()
    write_record(work, doc, out)
    flat = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    assert flat
    assert client.get(f"/documents/{doc}/listen").text.count('class="s"') > 0
    job = client.post("/api/v1/jobs", json={"kind": "audio", "document": doc})
    assert job.status_code == 202, job.text
    assert wait(client, job.json()["id"])["state"] == "done"
    assert sorted(p.name for p in book.iterdir()) == sorted(flat)
    assert {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()} == flat
    assert client.get(f"/documents/{doc}/listen").text.count('class="s"') > 0
