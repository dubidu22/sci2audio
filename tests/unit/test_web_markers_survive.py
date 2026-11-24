"""The v1.3 markers file (#474, D-728) through everything else that touches the working
folder: a new analysis or audiobook, the command line, freeing the speech cache, a replaced
upload, and the removal of the document, whose box counts them (#120). The server no
longer writes it (#887): the file here is the one v1.3 left, which the carry-over (#475)
only reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from cli_helpers import Cli, small_pdf
from test_web_player import make, player_data, work_of
from web_helpers import (
    browser,
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    program,
    set_capture,
    upload,
)

from sci2audio.app.captures import CAPTURES, load_captures, write_captures
from sci2audio.core import Anchor, Capture, CaptureFile, CaptureType
from sci2audio.web import create_app
from sci2audio.web.markers import MARKERS, Marker, markers_text, read_markers
from sci2audio.web.markers import Anchor as MarkerAnchor

pytestmark = pytest.mark.usefixtures("offline")


def server(tmp_path: Path) -> tuple[Any, Any, Any]:
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    return app, program(app, config), config


def page_data(client: Any, doc: str) -> dict[str, Any]:
    return player_data(client.get(f"/documents/{doc}/listen").text)


def sentences(data: dict[str, Any]) -> list[int]:
    """The chunks that read text, in order."""
    return [n for n, chunk in enumerate(data["chunks"]) if chunk[3]]


def again(client: Any, doc: str, **settings: Any) -> None:
    """Make the audiobook again (the web's rerun path, which forgets the position)."""
    body = {"kind": "audio", "document": doc, "overwrite": True, "settings": settings}
    job = client.post("/api/v1/jobs", json=body)
    assert job.status_code in (201, 202), job.text
    final = json.loads(events(client, job.json()["id"])[-1][1])
    assert final["state"] == "done", final


def as_v13(work: Path, doc: str, notes: list[str]) -> bytes:
    """The document's marks in captures.json as the v1.3 markers.json, with these notes,
    and no captures.json: the folder as v1.3 left it."""
    stored = json.loads((work / CAPTURES).read_text(encoding="utf-8"))["captures"]
    markers = []
    for capture, note in zip(stored, notes, strict=True):
        a = capture["anchor"]
        anchor = MarkerAnchor(a["block"], a["start"], a["end"], a["text"])
        markers.append(Marker(capture["id"], capture["created"], capture["changed"], anchor, note))
    raw = markers_text(doc, markers).encode("utf-8")
    (work / CAPTURES).unlink()
    (work / MARKERS).write_bytes(raw)
    return raw


@pytest.fixture
def marked(tmp_path: Path) -> dict[str, Any]:
    """An audiobook with two v1.3 markers on its sentences, the second one with a note."""
    app, client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    data = page_data(client, doc)
    first, second = sentences(data)[1:3]
    one = set_capture(client, doc, "mark", first, data["audiobook"])
    two = set_capture(client, doc, "mark", second, data["audiobook"])
    work = work_of(config, doc)
    raw = as_v13(work, doc, ["", "Ask Sam."])
    return {
        "app": app,
        "client": client,
        "config": config,
        "doc": doc,
        "data": data,
        "chunks": (first, second),
        "ids": (one["id"], two["id"]),
        "work": work,
        "bytes": raw,
    }


# ---- nothing else touches the file (plan section 3) ------------------------------------------


def test_a_new_analysis_and_audiobook_keep_the_file(
    marked: dict[str, Any],
) -> None:
    client, doc, work = marked["client"], marked["doc"], marked["work"]
    script = client.post("/api/v1/jobs", json={"kind": "script", "document": doc})
    assert json.loads(events(client, script.json()["id"])[-1][1])["state"] == "done"
    again(client, doc, speed=1.5)
    assert (work / MARKERS).read_bytes() == marked["bytes"]
    data = page_data(client, doc)
    assert data["audiobook"] != marked["data"]["audiobook"]
    # the page carried them over, and still left the file as it was (#475)
    assert [c["id"] for c in data["captures"]] == list(marked["ids"])
    assert (work / MARKERS).read_bytes() == marked["bytes"]


def test_freeing_the_speech_cache_and_a_replaced_upload_keep_the_file(
    marked: dict[str, Any],
) -> None:
    client, doc, work = marked["client"], marked["doc"], marked["work"]
    assert client.delete(f"/api/v1/documents/{doc}/chunks").status_code == 204
    source = next((work / "source").iterdir())
    assert upload(client, source.read_bytes(), "renamed.pdf")["id"] == doc  # same file
    assert (work / MARKERS).read_bytes() == marked["bytes"]


def test_the_command_line_never_touches_the_file(tmp_path: Path) -> None:
    cli = Cli(tmp_path)
    source = small_pdf(tmp_path / "in", ("The first sentence is here.", "A second one."))
    out = tmp_path / "book"
    assert cli("convert", source, "-o", out, "-q").code == 0
    work = cli.work(source)
    kept = '{"format": "sci2audio-web-markers", "a person\'s": "words"}\n'
    (work / MARKERS).write_text(kept, encoding="utf-8")
    result = cli("convert", source, "-o", out, "-q", "--overwrite")
    assert result.code == 0, result.err
    assert (work / MARKERS).read_text(encoding="utf-8") == kept


# ---- the removal box counts them, and the removal takes them (#120, D-728 ruling 3, #396) ------


def test_the_removal_box_counts_the_markers_as_it_is_drawn_and_removal_takes_them(
    marked: dict[str, Any],
) -> None:
    """Before the carry-over (#475) the v1.3 markers are counted as the captures they will
    become (ADR-008 2.1 item 5): a marker without a note as a mark, one with a note as a
    note. Counting never carries them over (#418)."""
    app, config, client, doc, work = (
        marked["app"],
        marked["config"],
        marked["client"],
        marked["doc"],
        marked["work"],
    )
    page = browser(app, config)
    for address in ("/", f"/documents/{doc}"):
        assert "Your note goes too. Your mark goes too." in page.get(address).text
    plain, noted = read_markers(work, doc)
    third = Marker("0" * 16, "t", "t", MarkerAnchor(0, 0, 4, "Some"))
    (work / MARKERS).write_text(markers_text(doc, [plain, noted, third]), encoding="utf-8")
    assert "Your note goes too. Your 2 marks go too." in page.get("/").text
    (work / MARKERS).write_text(markers_text(doc, [noted]), encoding="utf-8")
    assert "Your note goes too.</p>" in page.get(f"/documents/{doc}").text
    german = page.get("/", headers={"Accept-Language": "de"}).text
    assert "Ihre Notiz wird ebenfalls entfernt." in german
    (work / MARKERS).write_text("{broken", encoding="utf-8")
    assert "Your markers file goes too." in page.get("/").text
    (work / MARKERS).unlink()
    assert "remove-captures" not in page.get("/").text
    (work / MARKERS).write_bytes(marked["bytes"])
    assert not (work / CAPTURES).exists()
    assert client.delete(f"/api/v1/documents/{doc}?keep_audiobook=false").status_code == 200
    assert not work.exists()


def test_the_removal_box_counts_the_captures_by_type_and_not_the_markers_beside_them(
    marked: dict[str, Any],
) -> None:
    """ADR-008 2.1 item 4: with `captures.json` there, it alone is counted; `markers.json`
    beside it is not read (item 5)."""
    app, config, doc, work = marked["app"], marked["config"], marked["doc"], marked["work"]
    page = browser(app, config)
    anchor = Anchor(1, 0, 4, "Some")
    stamp = "2026-11-20T19:04:00Z"
    captures = (
        Capture("00000000000000a1", CaptureType.NOTE, stamp, stamp, anchor, "Ask Sam."),
        Capture("00000000000000a2", CaptureType.NOTE, stamp, stamp, anchor),
        Capture("00000000000000a3", CaptureType.QUOTE, stamp, stamp, anchor),
    )
    load_captures(work, doc)  # the markers carried over first, as the server does (#875)
    write_captures(work, CaptureFile(doc, captures))
    english = page.get("/").text
    assert "Your 2 notes go too. Your quote goes too.</p>" in english
    assert "mark" not in english.split("remove-captures", 1)[1].split("</p>", 1)[0]
    german = page.get(f"/documents/{doc}", headers={"Accept-Language": "de"}).text
    assert "Ihre 2 Notizen werden ebenfalls entfernt. Ihr Zitat wird ebenfalls entfernt." in german
    write_captures(work, CaptureFile(doc, ()))  # the file stays, with no capture in it
    assert "remove-captures" not in page.get("/").text
    (work / CAPTURES).write_text("{broken", encoding="utf-8")
    for address in ("/", f"/documents/{doc}"):
        assert "Your file of marks, notes and quotes goes too." in page.get(address).text
    german = page.get("/", headers={"Accept-Language": "de"}).text
    assert "Ihre Datei mit Markierungen, Notizen und Zitaten wird ebenfalls entfernt." in german
    assert (work / CAPTURES).read_text(encoding="utf-8") == "{broken"
    assert (work / MARKERS).read_bytes() == marked["bytes"]
