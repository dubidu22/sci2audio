"""An audiobook the command line made, opened in the player (#154): the server serves it
read-only and only from the two folders the person named (D-295's checks): the working
folder's records and the output folder's audio. No path is taken from a file."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from cli_helpers import Cli, small_pdf
from test_web_player import player_data
from web_helpers import make_config, program, upload
from web_helpers import offline as offline

from sci2audio.web import OutsideJob, create_app
from sci2audio.web import player as web_player

pytestmark = pytest.mark.usefixtures("offline")

LINES = ("The first sentence is here.", "A second sentence follows it.")


def outside_job(tmp_path: Path) -> tuple[OutsideJob, Any, Any]:
    """`convert` makes an audiobook into its own folders; a server opens it from there."""
    cli = Cli(tmp_path / "cli")
    source = small_pdf(tmp_path / "in", LINES)
    out = tmp_path / "book"
    assert cli("convert", source, "-o", out, "-q").code == 0
    job = OutsideJob(
        document=hashlib.sha256(source.read_bytes()).hexdigest()[:16],
        name=source.name,
        work=cli.work(source).absolute(),
        folder=out.absolute(),
    )
    config = make_config(tmp_path / "server", outside=(job,))
    return job, program(create_app(config), config), config


def test_the_listen_page_shows_a_command_line_job(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    page = client.get(f"/documents/{job.id}/listen")
    assert page.status_code == 200
    assert "Listen: note.pdf" in page.text
    data = player_data(page.text)
    assert data["document"] == job.id == f"cli-{job.document}"
    assert data["chunks"]
    for _start, _end, _chapter, element in data["chunks"]:
        assert f'id="{element}"' in page.text
    # read-only: no links to a document page the web does not have
    assert f'href="/documents/{job.id}"' not in page.text
    assert f'href="/documents/{job.id}#step-make"' not in page.text
    home = client.get("/").text
    assert f'href="/documents/{job.id}/listen"' in home
    assert client.get(f"/documents/{job.id}").status_code == 404
    # the file's own id is not the job's key: the web holds no such document
    assert client.get(f"/documents/{job.document}/listen").status_code == 404


def test_the_librarys_search_finds_a_command_line_job_by_its_name(tmp_path: Path) -> None:
    """#416 (#446 review S1b): every row is found by its title or file name, also an
    audiobook the command line made, and hidden by a query that does not match it."""
    job, client, _config = outside_job(tmp_path)

    def row(query: str) -> str:
        page = client.get("/", params={"q": query}).text
        return page.split(f'<tr id="row-{job.id}"')[1].split(">")[0]

    assert 'data-find="note.pdf' in row("NOTE")
    assert not row("NOTE").endswith(" hidden")
    assert not row("note.pdf").endswith(" hidden")
    assert row("nothing like it").endswith(" hidden")


def test_only_the_jobs_own_files_are_served(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    base = f"/api/v1/documents/{job.id}/audiobook"
    names = [p.name for p in job.folder.iterdir()]
    for name in names:
        answer = client.get(f"{base}/{name}")
        assert answer.status_code == 200, name
        assert answer.content == (job.folder / name).read_bytes()
    (job.folder / "other.mp3").write_bytes(b"x")
    for wrong in ("other.mp3", "..%2Fin%2Fnote.pdf", "%2E%2E", "audio.json", "document.json"):
        assert client.get(f"{base}/{wrong}").status_code == 404, wrong
    assert client.get(f"/api/v1/documents/0123456789abcdef/audiobook/{names[0]}").status_code == 404


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need rights on Windows")
def test_a_link_out_of_the_folder_is_not_served(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    mp3 = next(p for p in job.folder.iterdir() if p.suffix == ".mp3")
    secret = tmp_path / "secret.mp3"
    secret.write_bytes(b"not for the page")
    mp3.unlink()
    os.symlink(secret, mp3)
    answer = client.get(f"/api/v1/documents/{job.id}/audiobook/{mp3.name}")
    assert answer.status_code == 404


def test_a_renamed_file_is_not_served_and_the_page_says_why(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    mp3 = next(p for p in job.folder.iterdir() if p.suffix == ".mp3")
    mp3.rename(job.folder / "renamed.mp3")
    for name in (mp3.name, "renamed.mp3"):
        assert client.get(f"/api/v1/documents/{job.id}/audiobook/{name}").status_code == 404
    page = client.get(f"/documents/{job.id}/listen").text
    assert "The audiobook files are no longer in" in page
    assert "player-data" not in page


def test_only_the_named_folder_is_tried(tmp_path: Path) -> None:
    """The saved and the default output folder are the web's own: an outside job is
    never looked for there."""
    job, _client, config = outside_job(tmp_path)
    config.output_folder.mkdir(parents=True, exist_ok=True)
    for path in job.folder.iterdir():
        path.rename(config.output_folder / path.name)
    client = program(create_app(config), config)
    page = client.get(f"/documents/{job.id}/listen").text
    assert "player-data" not in page
    name = next(p.name for p in config.output_folder.iterdir())
    assert client.get(f"/api/v1/documents/{job.id}/audiobook/{name}").status_code == 404


def test_an_outside_job_cannot_be_changed(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    for key in (job.id, job.document):
        assert client.delete(f"/api/v1/documents/{key}?keep_audiobook=false").status_code == 404
        assert client.delete(f"/api/v1/documents/{key}/chunks").status_code == 404
        body = {"kind": "audio", "document": key}
        assert client.post("/api/v1/jobs", json=body).status_code == 404
    assert job.work.is_dir()
    assert any(p.suffix == ".mp3" for p in job.folder.iterdir())


def test_opening_an_outside_job_writes_nothing_into_its_folders(tmp_path: Path) -> None:
    """The library notes when a document was opened (#389), but a command-line job's
    folders are read-only to the server (#154): its Listen page and the library leave
    both folders exactly as they were, and keep no opened.json anywhere."""
    job, client, config = outside_job(tmp_path)

    def snapshot() -> dict[str, tuple[int, int]]:
        return {
            p.relative_to(tmp_path).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for root in (job.work, job.folder)
            for p in sorted(root.rglob("*"))
        }

    before = snapshot()
    for path in (f"/documents/{job.id}/listen", "/", f"/documents/{job.id}/listen"):
        assert client.get(path).status_code == 200, path
    assert snapshot() == before
    assert not list(tmp_path.rglob("opened.json"))
    assert not (config.work_root / job.document).exists()
    assert not (config.work_root / job.id).exists()


def test_an_outside_job_keeps_its_position_in_its_working_folder(tmp_path: Path) -> None:
    """#153 for a `listen` job: the position goes to the job's working folder, and the
    next run of `listen` offers to continue there. Here that folder is apart from the
    server's; with the default folders it is the file's cache folder, which the interface
    shares (`test_the_cache_folder_shared_with_the_interface_*`, #381)."""
    job, client, config = outside_job(tmp_path)
    data = player_data(client.get(f"/documents/{job.id}/listen").text)
    start, _end, chapter, _element = data["chunks"][-1]  # past the first sentence
    body = {"chapter": chapter, "time": start + 0.01, "audiobook": data["audiobook"]}
    answer = client.post(f"/api/v1/documents/{job.id}/position", json=body)
    assert answer.status_code == 204, answer.text
    assert (job.work / "position.json").is_file()
    assert not (config.work_root / job.document).exists()
    again = program(create_app(config), config)
    assert 'id="resume-continue"' in again.get(f"/documents/{job.id}/listen").text
    other = {**body, "audiobook": "0" * 16}
    assert client.post(f"/api/v1/documents/{job.id}/position", json=other).status_code == 409
    unknown = "/api/v1/documents/0123456789abcdef/position"
    assert client.post(unknown, json=body).status_code == 404


def test_a_file_also_opened_in_the_interface_keeps_the_two_apart(tmp_path: Path) -> None:
    """#378 review S1: the web document of the same file has the same file id; the start
    page's command-line link still plays the command line's audiobook, and the web
    document's own listen page looks only in its own folders."""
    job, client, _config = outside_job(tmp_path)
    web = upload(client, (tmp_path / "in" / job.name).read_bytes(), name=job.name)
    assert web["id"] == job.document
    home = client.get("/").text
    assert f'href="/documents/{job.id}/listen"' in home
    page = client.get(f"/documents/{job.id}/listen").text
    assert player_data(page)["document"] == job.id
    name = next(p.name for p in job.folder.iterdir() if p.suffix == ".mp3")
    assert client.get(f"/api/v1/documents/{job.id}/audiobook/{name}").status_code == 200
    own = client.get(f"/documents/{job.document}/listen").text
    assert "player-data" not in own  # the web made no audiobook of it
    assert "There is no audiobook of this document yet." in own
    assert client.get(f"/api/v1/documents/{job.document}/audiobook/{name}").status_code == 404


def moved_away(job: OutsideJob, tmp_path: Path) -> Path:
    """The job's files moved out of its named folder, which stays, empty."""
    real = tmp_path / "real"
    real.mkdir()
    for path in job.folder.iterdir():
        path.rename(real / path.name)
    return real


def nothing_served(client: Any, job: OutsideJob, real: Path) -> None:
    assert "player-data" not in client.get(f"/documents/{job.id}/listen").text
    for path in real.iterdir():
        answer = client.get(f"/api/v1/documents/{job.id}/audiobook/{path.name}")
        assert answer.status_code == 404, path.name


def test_the_web_record_of_a_folder_is_not_tried(tmp_path: Path) -> None:
    """#378 review S2 (M2): a web record in the job's working folder names where the files
    are; a command-line job never follows it."""
    job, client, _config = outside_job(tmp_path)
    real = moved_away(job, tmp_path)
    record = {
        "format": web_player.RECORD_FORMAT,
        "version": web_player.RECORD_VERSION,
        "document": job.document,
        "folder": str(real.absolute()),
    }
    (job.work / web_player.RECORD).write_text(json.dumps(record), encoding="utf-8")
    assert web_player.recorded_folder(job.work, job.document) == real.absolute()
    nothing_served(client, job, real)


def test_the_settings_output_folder_is_not_tried(tmp_path: Path) -> None:
    """#378 review S2 (M3): the interface's saved output folder holds the files; a
    command-line job never looks there."""
    job, client, config = outside_job(tmp_path)
    real = moved_away(job, tmp_path)
    config.config_file.parent.mkdir(parents=True, exist_ok=True)
    config.config_file.write_text(json.dumps({"output_folder": str(real)}), encoding="utf-8")
    nothing_served(client, job, real)


def shared_job(tmp_path: Path) -> tuple[OutsideJob, Any, Any, Path]:
    """#381: with the default folders, `listen`'s working folder is the file's cache
    folder, `<cache>/sci2audio/jobs/<file id>` (`default_work_folder`), the very folder of
    the web document of that file (`default_work_root`). The command line's records are put
    into the folder of the same file opened in the interface; the web's own record there
    points to a copy of the audiobook in another folder. Returns the job, the client, the
    config and the copy's folder."""
    cli = Cli(tmp_path / "cli")
    source = small_pdf(tmp_path / "in", LINES)
    out = tmp_path / "book"
    assert cli("convert", source, "-o", out, "-q").code == 0
    document = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    work_root = make_config(tmp_path / "server").work_root
    job = OutsideJob(
        document=document, name=source.name, work=(work_root / document).absolute(), folder=out
    )
    config = make_config(tmp_path / "server", outside=(job,))
    client = program(create_app(config), config)
    assert upload(client, source.read_bytes(), name=source.name)["id"] == document
    for path in cli.work(source).iterdir():
        if path.is_file():
            shutil.copy2(path, job.work / path.name)
    copy = tmp_path / "web-book"
    shutil.copytree(out, copy)
    record = {
        "format": web_player.RECORD_FORMAT,
        "version": web_player.RECORD_VERSION,
        "document": document,
        "folder": str(copy.absolute()),
    }
    (job.work / web_player.RECORD).write_text(json.dumps(record), encoding="utf-8")
    assert web_player.recorded_folder(job.work, document) == copy.absolute()
    return job, client, config, copy


def readalong_of(folder: Path) -> Path:
    return next(p for p in folder.iterdir() if p.name.endswith(".readalong.json"))


def test_the_cache_folder_shared_with_the_interface_serves_only_the_jobs_folder(
    tmp_path: Path,
) -> None:
    """#381 (a): the command-line job's Listen page and audiobook route serve from the
    job's named folder only, though the web record in the shared folder names a valid
    folder that holds the same files."""
    job, client, _config, copy = shared_job(tmp_path)
    page = client.get(f"/documents/{job.id}/listen").text
    assert player_data(page)["document"] == job.id
    web = client.get(f"/documents/{job.document}/listen").text
    assert player_data(web)["document"] == job.document  # the web finds its copy
    base = f"/api/v1/documents/{job.id}/audiobook"
    mp3 = next(p for p in job.folder.iterdir() if p.suffix == ".mp3")
    assert client.get(f"{base}/{mp3.name}").content == mp3.read_bytes()
    real = moved_away(job, tmp_path)
    nothing_served(client, job, real)
    for path in copy.iterdir():  # the web record's folder is never tried
        assert client.get(f"{base}/{path.name}").status_code == 404, path.name
    answer = client.get(f"/api/v1/documents/{job.document}/audiobook/{mp3.name}")
    assert answer.status_code == 200  # while the web document still plays its copy
    assert answer.content == (copy / mp3.name).read_bytes()


def test_the_cache_folder_shared_with_the_interface_offers_a_position_for_its_audiobook(
    tmp_path: Path,
) -> None:
    """#381 (b): a position saved through the `cli-` key lands in the shared folder; the
    web document's Listen page offers it only while it locates the same read-along file
    (the same bytes), and a save stamped for another audiobook is refused."""
    job, client, _config, copy = shared_job(tmp_path)
    data = player_data(client.get(f"/documents/{job.id}/listen").text)
    start, _end, chapter, _element = data["chunks"][-1]  # past the first sentence
    body = {"chapter": chapter, "time": start + 0.01, "audiobook": data["audiobook"]}
    answer = client.post(f"/api/v1/documents/{job.id}/position", json=body)
    assert answer.status_code == 204, answer.text
    assert (job.work / web_player.POSITION).is_file()
    web = client.get(f"/documents/{job.document}/listen").text
    assert player_data(web)["audiobook"] == data["audiobook"]  # the same read-along file
    assert 'id="resume-continue"' in web
    assert 'id="resume-continue"' in client.get(f"/documents/{job.id}/listen").text
    other = {**body, "audiobook": "0" * 16}
    assert client.post(f"/api/v1/documents/{job.id}/position", json=other).status_code == 409
    # the copy's read-along file says the same in other bytes: another audiobook to the web
    readalong = readalong_of(copy)
    readalong.write_text(
        json.dumps(json.loads(readalong.read_text(encoding="utf-8")), indent=1), encoding="utf-8"
    )
    web = client.get(f"/documents/{job.document}/listen").text
    assert player_data(web)["audiobook"] != data["audiobook"]
    assert 'id="resume-continue"' not in web
    assert 'id="resume-continue"' in client.get(f"/documents/{job.id}/listen").text


def test_the_cache_folder_shared_with_the_interface_forgets_the_position_with_the_web(
    tmp_path: Path,
) -> None:
    """#381 (c): a web audio job clears the position of the shared folder
    (`remove_position`), so the `cli-` Listen page offers no resume after it."""
    job, client, _config, _copy = shared_job(tmp_path)
    data = player_data(client.get(f"/documents/{job.id}/listen").text)
    start, _end, chapter, _element = data["chunks"][-1]
    body = {"chapter": chapter, "time": start + 0.01, "audiobook": data["audiobook"]}
    assert client.post(f"/api/v1/documents/{job.id}/position", json=body).status_code == 204
    assert 'id="resume-continue"' in client.get(f"/documents/{job.id}/listen").text
    web_player.remove_position(job.work)
    assert 'id="resume-continue"' not in client.get(f"/documents/{job.id}/listen").text
    assert 'id="resume-continue"' not in client.get(f"/documents/{job.document}/listen").text
