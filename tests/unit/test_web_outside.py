"""An audiobook the command line made, opened in the player (#154): the server serves it
read-only and only from the two folders the person named (D-295's checks): the working
folder's records and the output folder's audio. No path is taken from a file."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from cli_helpers import Cli, small_pdf
from test_web_player import player_data
from web_helpers import make_config, program
from web_helpers import offline as offline

from sci2audio.web import OutsideJob, create_app

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
    page = client.get(f"/documents/{job.document}/listen")
    assert page.status_code == 200
    assert "Listen: note.pdf" in page.text
    data = player_data(page.text)
    assert data["document"] == job.document
    assert data["chunks"]
    for _start, _end, _chapter, element in data["chunks"]:
        assert f'id="{element}"' in page.text
    # read-only: no links to a document page the web does not have
    assert f'href="/documents/{job.document}"' not in page.text
    assert f'href="/documents/{job.document}#step-make"' not in page.text
    home = client.get("/").text
    assert f'href="/documents/{job.document}/listen"' in home
    assert client.get(f"/documents/{job.document}").status_code == 404


def test_only_the_jobs_own_files_are_served(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    base = f"/api/v1/documents/{job.document}/audiobook"
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
    answer = client.get(f"/api/v1/documents/{job.document}/audiobook/{mp3.name}")
    assert answer.status_code == 404


def test_a_renamed_file_is_not_served_and_the_page_says_why(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    mp3 = next(p for p in job.folder.iterdir() if p.suffix == ".mp3")
    mp3.rename(job.folder / "renamed.mp3")
    for name in (mp3.name, "renamed.mp3"):
        assert client.get(f"/api/v1/documents/{job.document}/audiobook/{name}").status_code == 404
    page = client.get(f"/documents/{job.document}/listen").text
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
    page = client.get(f"/documents/{job.document}/listen").text
    assert "player-data" not in page
    name = next(p.name for p in config.output_folder.iterdir())
    assert client.get(f"/api/v1/documents/{job.document}/audiobook/{name}").status_code == 404


def test_an_outside_job_cannot_be_changed(tmp_path: Path) -> None:
    job, client, _config = outside_job(tmp_path)
    assert client.delete(f"/api/v1/documents/{job.document}").status_code == 404
    assert client.delete(f"/api/v1/documents/{job.document}/chunks").status_code == 404
    body = {"kind": "audio", "document": job.document}
    assert client.post("/api/v1/jobs", json=body).status_code == 404
    assert job.work.is_dir()
    assert any(p.suffix == ".mp3" for p in job.folder.iterdir())


def test_an_outside_job_keeps_its_position_in_its_own_working_folder(tmp_path: Path) -> None:
    """#153 for a `listen` job: the position goes to the job's working folder, and the
    next run of `listen` offers to continue there."""
    job, client, config = outside_job(tmp_path)
    data = player_data(client.get(f"/documents/{job.document}/listen").text)
    start, _end, chapter, _element = data["chunks"][-1]  # past the first sentence
    body = {"chapter": chapter, "time": start + 0.01, "audiobook": data["audiobook"]}
    answer = client.post(f"/api/v1/documents/{job.document}/position", json=body)
    assert answer.status_code == 204, answer.text
    assert (job.work / "position.json").is_file()
    assert not (config.work_root / job.document).exists()
    again = program(create_app(config), config)
    assert 'id="resume-continue"' in again.get(f"/documents/{job.document}/listen").text
    other = {**body, "audiobook": "0" * 16}
    assert client.post(f"/api/v1/documents/{job.document}/position", json=other).status_code == 409
    unknown = "/api/v1/documents/0123456789abcdef/position"
    assert client.post(unknown, json=body).status_code == 404
