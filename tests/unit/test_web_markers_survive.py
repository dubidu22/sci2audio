"""Markers through the API and through everything else that touches the working folder
(#474, D-728): a new analysis or audiobook, the command line, freeing the speech cache, a
replaced upload, and the removal of the document, whose box counts them (#120)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from cli_helpers import Cli, small_pdf
from test_web_player import make, player_data, work_of
from web_helpers import (
    FakeClock,
    book_folder,
    browser,
    events,
    make_config,
    markers_of,
    offline,  # noqa: F401 - fixture
    program,
    set_marker,
    upload,
)

from sci2audio.web import create_app
from sci2audio.web.markers import MARKERS, UNDO_SECONDS
from sci2audio.web.player import audiobook_stamp

pytestmark = pytest.mark.usefixtures("offline")


def server(tmp_path: Path, clock: FakeClock | None = None) -> tuple[Any, Any, Any]:
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source(), clock=clock)
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


@pytest.fixture
def marked(tmp_path: Path) -> dict[str, Any]:
    """An audiobook with two markers, one with a note."""
    clock = FakeClock()
    app, client, config = server(tmp_path, clock)
    doc = make(client)["doc"]["id"]
    data = page_data(client, doc)
    first, second = sentences(data)[1:3]
    one = set_marker(client, doc, first, data["audiobook"])
    two = set_marker(client, doc, second, data["audiobook"])
    noted = client.patch(f"/api/v1/documents/{doc}/markers/{two['id']}", json={"note": "Ask Sam."})
    assert noted.status_code == 200, noted.text
    work = work_of(config, doc)
    return {
        "app": app,
        "client": client,
        "config": config,
        "doc": doc,
        "data": data,
        "chunks": (first, second),
        "ids": (one["id"], two["id"]),
        "work": work,
        "clock": clock,
        "bytes": (work / MARKERS).read_bytes(),
    }


# ---- the API -----------------------------------------------------------------------------------


def test_a_marker_is_set_on_the_pages_sentence_and_shown_on_the_page(
    marked: dict[str, Any],
) -> None:
    client, doc = marked["client"], marked["doc"]
    first, second = marked["chunks"]
    data = page_data(client, doc)
    assert data["markers_file"] == ""
    assert [(m["id"], m["chunk"], m["state"], m["note"]) for m in data["markers"]] == [
        (marked["ids"][0], first, "found", ""),
        (marked["ids"][1], second, "found", "Ask Sam."),
    ]
    entry = markers_of(marked["work"])["markers"][0]
    assert entry["anchor"]["text"]  # the sentence as printed, from the server's own files
    assert data["markers"][0]["text"] == entry["anchor"]["text"]


def test_a_second_set_on_the_same_sentence_answers_its_marker(marked: dict[str, Any]) -> None:
    client, doc, data = marked["client"], marked["doc"], marked["data"]
    same = set_marker(client, doc, marked["chunks"][0], data["audiobook"], status=200)
    assert same["id"] == marked["ids"][0]
    assert (marked["work"] / MARKERS).read_bytes() == marked["bytes"]


def test_a_page_of_another_audiobook_and_a_chunk_that_is_no_sentence_are_refused(
    marked: dict[str, Any],
) -> None:
    client, doc, data = marked["client"], marked["doc"], marked["data"]
    url = f"/api/v1/documents/{doc}/markers"
    other = client.post(url, json={"chunk": 1, "audiobook": "0" * 16})
    assert (other.status_code, other.json()["error"]) == (409, "other-audiobook")
    beyond = client.post(url, json={"chunk": len(data["chunks"]), "audiobook": data["audiobook"]})
    assert (beyond.status_code, beyond.json()["error"]) == (422, "no-such-sentence")
    for body in ({"chunk": 1}, {"chunk": -1, "audiobook": data["audiobook"]}, {"chunk": "1"}):
        assert client.post(url, json=body).status_code == 422
    assert (marked["work"] / MARKERS).read_bytes() == marked["bytes"]


@pytest.mark.parametrize(
    ("case", "end"),
    [
        ("an empty span", lambda span: span["start_char"]),
        ("past the block's end", lambda _: 10_000),
    ],
    ids=["empty", "outside"],
)
def test_a_chunk_whose_span_is_empty_or_outside_the_document_is_no_sentence(
    marked: dict[str, Any], case: str, end: Any
) -> None:
    """Round 1 S2: the route refuses it itself (422), never through the file's read-back
    guard (503), and the file is unchanged."""
    client, doc, config = marked["client"], marked["doc"], marked["config"]
    [path] = book_folder(config.output_folder).glob("*.readalong.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    chunk = sentences(marked["data"])[0]  # a sentence without a marker
    assert chunk not in marked["chunks"]
    span = data["chunks"][chunk]
    span["end_char"] = end(span)
    path.write_text(json.dumps(data), encoding="utf-8")
    url = f"/api/v1/documents/{doc}/markers"
    answer = client.post(url, json={"chunk": chunk, "audiobook": audiobook_stamp(path)})
    assert (answer.status_code, answer.json()["error"]) == (422, "no-such-sentence"), case
    assert (marked["work"] / MARKERS).read_bytes() == marked["bytes"]


def test_a_note_too_long_or_with_nul_is_refused(marked: dict[str, Any]) -> None:
    client, doc = marked["client"], marked["doc"]
    url = f"/api/v1/documents/{doc}/markers/{marked['ids'][0]}"
    for note in ("x" * 4001, "a\x00b"):
        assert client.patch(url, json={"note": note}).status_code == 422
    assert client.patch(url, json={"note": "x" * 4000}).status_code == 200
    missing = client.patch(f"/api/v1/documents/{doc}/markers/{'f' * 16}", json={"note": ""})
    assert (missing.status_code, missing.json()["error"]) == (404, "not-found")
    assert (
        client.patch(f"/api/v1/documents/{doc}/markers/nothex", json={"note": ""}).status_code
        == 422
    )


def test_remove_and_undo_within_ten_minutes_then_never(marked: dict[str, Any]) -> None:
    client, doc, clock = marked["client"], marked["doc"], marked["clock"]
    marker_id = marked["ids"][1]
    removed = client.delete(f"/api/v1/documents/{doc}/markers/{marker_id}")
    assert removed.status_code == 200
    assert removed.json()["note"] == "Ask Sam."
    assert [m["id"] for m in markers_of(marked["work"])["markers"]] == [marked["ids"][0]]
    clock.advance(UNDO_SECONDS - 1)
    back = client.post(f"/api/v1/documents/{doc}/markers/{marker_id}/restore")
    assert back.status_code == 201
    assert back.json() == {**removed.json()}
    assert (marked["work"] / MARKERS).read_bytes() == marked["bytes"]
    client.delete(f"/api/v1/documents/{doc}/markers/{marker_id}")
    clock.advance(UNDO_SECONDS + 1)
    late = client.post(f"/api/v1/documents/{doc}/markers/{marker_id}/restore")
    assert (late.status_code, late.json()["error"]) == (410, "undo-expired")


def test_undo_after_the_sentence_was_marked_again_is_refused(marked: dict[str, Any]) -> None:
    client, doc, data = marked["client"], marked["doc"], marked["data"]
    marker_id = marked["ids"][0]
    client.delete(f"/api/v1/documents/{doc}/markers/{marker_id}")
    set_marker(client, doc, marked["chunks"][0], data["audiobook"])
    clash = client.post(f"/api/v1/documents/{doc}/markers/{marker_id}/restore")
    assert (clash.status_code, clash.json()["error"]) == (409, "marked-again")


def test_a_broken_markers_file_is_named_on_the_page_and_never_written(
    marked: dict[str, Any],
) -> None:
    client, doc, data, work = marked["client"], marked["doc"], marked["data"], marked["work"]
    (work / MARKERS).write_text("{broken", encoding="utf-8")
    shown = page_data(client, doc)
    assert shown["markers"] == []
    assert shown["markers_file"] == str(work / MARKERS)
    refused = client.post(
        f"/api/v1/documents/{doc}/markers",
        json={"chunk": marked["chunks"][0], "audiobook": data["audiobook"]},
    )
    assert (refused.status_code, refused.json()["error"]) == (409, "markers-unreadable")
    assert (work / MARKERS).read_text(encoding="utf-8") == "{broken"


def test_a_failed_save_answers_503_and_keeps_the_file(
    marked: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    from sci2audio.web import markers

    def full(texts: Any, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(markers, "write_texts", full)
    client, doc = marked["client"], marked["doc"]
    answer = client.patch(f"/api/v1/documents/{doc}/markers/{marked['ids'][0]}", json={"note": "x"})
    assert (answer.status_code, answer.json()["error"]) == (503, "markers-not-saved")
    assert (marked["work"] / MARKERS).read_bytes() == marked["bytes"]


def test_the_marker_routes_need_the_token_and_the_origin(marked: dict[str, Any]) -> None:
    from fastapi.testclient import TestClient
    from web_helpers import ORIGIN

    app, config, doc = marked["app"], marked["config"], marked["doc"]
    url = f"/api/v1/documents/{doc}/markers"
    body = {"chunk": marked["chunks"][0], "audiobook": marked["data"]["audiobook"]}
    assert TestClient(app, base_url=ORIGIN).post(url, json=body).status_code == 401
    page = browser(app, config)
    foreign = page.post(url, json=body, headers={"Origin": "http://evil.test"})
    assert foreign.status_code == 403
    assert (marked["work"] / MARKERS).read_bytes() == marked["bytes"]


# ---- nothing else touches the file (plan section 3) ------------------------------------------


def test_a_new_analysis_and_audiobook_keep_the_file_and_find_the_markers(
    marked: dict[str, Any],
) -> None:
    client, doc, work = marked["client"], marked["doc"], marked["work"]
    script = client.post("/api/v1/jobs", json={"kind": "script", "document": doc})
    assert json.loads(events(client, script.json()["id"])[-1][1])["state"] == "done"
    again(client, doc, speed=1.5)
    assert (work / MARKERS).read_bytes() == marked["bytes"]
    data = page_data(client, doc)
    assert data["audiobook"] != marked["data"]["audiobook"]
    assert [(m["id"], m["state"]) for m in data["markers"]] == [
        (marked["ids"][0], "found"),
        (marked["ids"][1], "found"),
    ]


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


# ---- the removal box counts them, and the removal takes them (#120, D-728 ruling 3) ------------


def test_the_removal_box_counts_the_markers_as_it_is_drawn_and_removal_takes_them(
    marked: dict[str, Any],
) -> None:
    app, config, client, doc, work = (
        marked["app"],
        marked["config"],
        marked["client"],
        marked["doc"],
        marked["work"],
    )
    page = browser(app, config)
    for address in ("/", f"/documents/{doc}"):
        assert "Your 2 markers and their notes go too." in page.get(address).text
    client.delete(f"/api/v1/documents/{doc}/markers/{marked['ids'][0]}")
    assert "Your marker and its note go too." in page.get(f"/documents/{doc}").text
    german = page.get("/", headers={"Accept-Language": "de"}).text
    assert "Ihre Markierung und ihre Notiz werden ebenfalls entfernt." in german
    (work / MARKERS).write_text("{broken", encoding="utf-8")
    assert "Your markers file goes too." in page.get("/").text
    (work / MARKERS).unlink()
    assert "remove-markers" not in page.get("/").text
    (work / MARKERS).write_bytes(marked["bytes"])
    assert client.delete(f"/api/v1/documents/{doc}?keep_audiobook=false").status_code == 200
    assert not work.exists()


# ---- a new audiobook that reads less ------------------------------------------------------


def test_a_marker_on_text_the_new_audiobook_does_not_read_is_kept_and_listed(
    marked: dict[str, Any],
) -> None:
    """Only the chosen chapters are read (#472): a marker in another one is listed as not
    read, never dropped (D-728 ruling 1)."""
    client, doc, work = marked["client"], marked["doc"], marked["work"]
    data = page_data(client, doc)
    assert len(data["chapters"]) >= 2
    again(client, doc, chapters=[1])
    shown = page_data(client, doc)
    assert [(m["id"], m["state"]) for m in shown["markers"]] == [
        (marked["ids"][1], "found"),  # the second chapter's heading
        (marked["ids"][0], "not-read"),  # the first chapter is not in this audiobook
    ]
    assert (work / MARKERS).read_bytes() == marked["bytes"]
