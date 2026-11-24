"""Captures through the API and the Listen page (#397, ADR-008): N, Q and M at the page's
sentence, one of each type per sentence, a note's text, removal with Undo, the refusals
that leave `captures.json` as it is, and the Settings page's sounds switch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from test_web_player import make, player_data, work_of
from web_helpers import (
    FakeClock,
    browser,
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    program,
)

from sci2audio.app.captures import CAPTURES
from sci2audio.web import create_app
from sci2audio.web.captures import UNDO_SECONDS
from sci2audio.web.markers import MARKERS

pytestmark = pytest.mark.usefixtures("offline")


def page_data(client: Any, doc: str) -> dict[str, Any]:
    return player_data(client.get(f"/documents/{doc}/listen").text)


def sentences(data: dict[str, Any]) -> list[int]:
    return [n for n, chunk in enumerate(data["chunks"]) if chunk[3]]


def capture(
    client: Any, doc: str, kind: str, chunk: int, stamp: str, text: str = "", status: int = 201
) -> Any:
    body = {"type": kind, "chunk": chunk, "audiobook": stamp, "text": text}
    answer = client.post(f"/api/v1/documents/{doc}/captures", json=body)
    assert answer.status_code == status, answer.text
    return answer.json()


def file_of(work: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((work / CAPTURES).read_text(encoding="utf-8"))
    return data


@pytest.fixture
def listening(tmp_path: Path) -> dict[str, Any]:
    """An audiobook with a mark and a note on its second sentence and a quote on its third."""
    clock = FakeClock()
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source(), clock=clock)
    client = program(app, config)
    doc = make(client)["doc"]["id"]
    data = page_data(client, doc)
    first, second = sentences(data)[1:3]
    mark = capture(client, doc, "mark", first, data["audiobook"])
    note = capture(client, doc, "note", first, data["audiobook"], "Ask Sam.")
    quote = capture(client, doc, "quote", second, data["audiobook"])
    work = work_of(config, doc)
    return {
        "app": app,
        "client": client,
        "config": config,
        "doc": doc,
        "data": data,
        "chunks": (first, second),
        "ids": {"mark": mark["id"], "note": note["id"], "quote": quote["id"]},
        "work": work,
        "clock": clock,
        "bytes": (work / CAPTURES).read_bytes(),
    }


def test_captures_are_kept_and_shown_on_the_page_by_their_sentence(
    listening: dict[str, Any],
) -> None:
    client, doc, ids = listening["client"], listening["doc"], listening["ids"]
    first, second = listening["chunks"]
    data = page_data(client, doc)
    assert data["captures_off"] == ""
    assert [(c["id"], c["type"], c["chunk"], c["state"], c["text"]) for c in data["captures"]] == [
        (ids["mark"], "mark", first, "found", ""),  # the page puts them in the dock's order
        (ids["note"], "note", first, "found", "Ask Sam."),
        (ids["quote"], "quote", second, "found", ""),
    ]
    saved = file_of(listening["work"])
    assert [c["type"] for c in saved["captures"]] == ["mark", "note", "quote"]
    assert saved["captures"][0]["anchor"]["text"] == data["captures"][0]["sentence"]
    assert not (listening["work"] / MARKERS).exists()
    page = client.get(f"/documents/{doc}/listen").text
    assert "Captures (3)" in page
    for kind, letter in (("note", "N"), ("quote", "Q"), ("mark", "M")):
        assert f'id="capture-{kind}" data-kind="{kind}"' in page
        assert f'aria-keyshortcuts="{letter}"' in page
    assert 'aria-keyshortcuts="C"' not in page


def test_one_capture_of_each_type_per_sentence(listening: dict[str, Any]) -> None:
    client, doc, data = listening["client"], listening["doc"], listening["data"]
    first = listening["chunks"][0]
    same = capture(client, doc, "mark", first, data["audiobook"], status=200)
    assert same["id"] == listening["ids"]["mark"]
    note = capture(client, doc, "note", first, data["audiobook"], "Other.", status=200)
    assert (note["id"], note["text"]) == (listening["ids"]["note"], "Ask Sam.")  # unchanged
    assert (listening["work"] / CAPTURES).read_bytes() == listening["bytes"]


def test_wrong_requests_are_refused_and_the_file_kept(listening: dict[str, Any]) -> None:
    client, doc, data = listening["client"], listening["doc"], listening["data"]
    url = f"/api/v1/documents/{doc}/captures"
    stamp = data["audiobook"]
    other = client.post(url, json={"type": "mark", "chunk": 1, "audiobook": "0" * 16})
    assert (other.status_code, other.json()["error"]) == (409, "other-audiobook")
    beyond = client.post(
        url, json={"type": "mark", "chunk": len(data["chunks"]), "audiobook": stamp}
    )
    assert (beyond.status_code, beyond.json()["error"]) == (422, "no-such-sentence")
    chunk = sentences(data)[3]
    for body in (
        {"type": "card", "chunk": chunk, "audiobook": stamp},  # no card in v1.5 (ADR-008)
        {"type": "mark", "chunk": chunk, "audiobook": stamp, "text": "x"},
        {"type": "note", "chunk": chunk, "audiobook": stamp},
        {"type": "note", "chunk": chunk, "audiobook": stamp, "text": "a\x00b"},
        {"type": "note", "chunk": chunk, "audiobook": stamp, "text": "x" * 4001},
    ):
        assert client.post(url, json=body).status_code == 422, body
    assert (listening["work"] / CAPTURES).read_bytes() == listening["bytes"]


def test_a_notes_text_changes_and_a_mark_takes_none(listening: dict[str, Any]) -> None:
    client, doc, ids = listening["client"], listening["doc"], listening["ids"]
    url = f"/api/v1/documents/{doc}/captures"
    changed = client.patch(f"{url}/{ids['note']}", json={"text": "Ask Kim."})
    assert (changed.status_code, changed.json()["text"]) == (200, "Ask Kim.")
    mark = client.patch(f"{url}/{ids['mark']}", json={"text": "x"})
    assert (mark.status_code, mark.json()["error"]) == (422, "invalid")
    for body in ({"text": ""}, {"text": "x" * 4001}, {"text": "a\x00b"}):
        assert client.patch(f"{url}/{ids['note']}", json=body).status_code == 422
    missing = client.patch(f"{url}/{'f' * 16}", json={"text": "x"})
    assert (missing.status_code, missing.json()["error"]) == (404, "not-found")


def test_remove_and_undo_within_ten_minutes_then_never(listening: dict[str, Any]) -> None:
    client, doc, clock = listening["client"], listening["doc"], listening["clock"]
    quote = listening["ids"]["quote"]
    url = f"/api/v1/documents/{doc}/captures/{quote}"
    removed = client.delete(url)
    assert (removed.status_code, removed.json()["type"]) == (200, "quote")
    assert quote not in (listening["work"] / CAPTURES).read_text(encoding="utf-8")
    clock.advance(UNDO_SECONDS - 1)
    back = client.post(f"{url}/restore")
    assert (back.status_code, back.json()) == (201, removed.json())
    assert (listening["work"] / CAPTURES).read_bytes() == listening["bytes"]
    client.delete(url)
    clock.advance(UNDO_SECONDS + 1)
    late = client.post(f"{url}/restore")
    assert (late.status_code, late.json()["error"]) == (410, "undo-expired")


def test_undo_after_the_sentence_got_that_type_again_is_refused(
    listening: dict[str, Any],
) -> None:
    client, doc, data = listening["client"], listening["doc"], listening["data"]
    mark = listening["ids"]["mark"]
    client.delete(f"/api/v1/documents/{doc}/captures/{mark}")
    capture(client, doc, "mark", listening["chunks"][0], data["audiobook"])
    clash = client.post(f"/api/v1/documents/{doc}/captures/{mark}/restore")
    assert (clash.status_code, clash.json()["error"]) == (409, "captured-again")


def test_a_broken_captures_file_is_named_on_the_page_and_never_written(
    listening: dict[str, Any],
) -> None:
    client, doc, data, work = (listening[k] for k in ("client", "doc", "data", "work"))
    (work / CAPTURES).write_text("{broken", encoding="utf-8")
    shown = page_data(client, doc)
    assert (shown["captures"], shown["captures_off"]) == ([], "unreadable")
    assert shown["captures_file"] == str(work / CAPTURES)
    page = client.get(f"/documents/{doc}/listen").text
    assert 'id="captures-broken"' in page
    refused = client.post(
        f"/api/v1/documents/{doc}/captures",
        json={"type": "quote", "chunk": listening["chunks"][0], "audiobook": data["audiobook"]},
    )
    assert (refused.status_code, refused.json()["error"]) == (409, "captures-unreadable")
    assert (work / CAPTURES).read_text(encoding="utf-8") == "{broken"


def test_markers_not_carried_over_turn_capturing_off_and_stay(tmp_path: Path) -> None:
    """ADR-008 2.1 item 5: no captures.json is written beside a markers.json the carry-over
    (#475) has not read."""
    voice = FakeVoice()
    config = make_config(tmp_path)
    client = program(create_app(config, voice=lambda models_dir: voice.source()), config)
    doc = make(client)["doc"]["id"]
    work = work_of(config, doc)
    (work / MARKERS).write_text('{"a person\'s": "markers"}', encoding="utf-8")
    data = page_data(client, doc)
    assert (data["captures"], data["captures_off"]) == ([], "markers")
    refused = client.post(
        f"/api/v1/documents/{doc}/captures",
        json={"type": "mark", "chunk": sentences(data)[0], "audiobook": data["audiobook"]},
    )
    assert (refused.status_code, refused.json()["error"]) == (409, "markers-not-carried")
    assert not (work / CAPTURES).exists()


def test_a_capture_on_text_the_new_audiobook_does_not_read_is_kept_and_listed(
    listening: dict[str, Any],
) -> None:
    """Only the chosen chapters are read (#472): a capture in another one is listed as not
    read, never dropped (ADR-008 2.1 item 3)."""
    client, doc, ids = listening["client"], listening["doc"], listening["ids"]
    assert len(listening["data"]["chapters"]) >= 2
    body = {"kind": "audio", "document": doc, "overwrite": True, "settings": {"chapters": [1]}}
    job = client.post("/api/v1/jobs", json=body)
    assert json.loads(events(client, job.json()["id"])[-1][1])["state"] == "done"
    shown = page_data(client, doc)
    assert [(c["id"], c["state"]) for c in shown["captures"]] == [
        (ids["quote"], "found"),  # the second chapter's heading
        (ids["mark"], "not-read"),
        (ids["note"], "not-read"),
    ]
    assert (listening["work"] / CAPTURES).read_bytes() == listening["bytes"]


def test_the_capture_routes_need_the_token_and_the_origin(listening: dict[str, Any]) -> None:
    from fastapi.testclient import TestClient
    from web_helpers import ORIGIN

    app, config, doc = listening["app"], listening["config"], listening["doc"]
    url = f"/api/v1/documents/{doc}/captures"
    body = {"type": "quote", "chunk": listening["chunks"][0], "audiobook": "0" * 16}
    assert TestClient(app, base_url=ORIGIN).post(url, json=body).status_code == 401
    foreign = browser(app, config).post(url, json=body, headers={"Origin": "http://evil.test"})
    assert foreign.status_code == 403
    assert (listening["work"] / CAPTURES).read_bytes() == listening["bytes"]


def test_the_sounds_switch_is_on_until_switched_off(listening: dict[str, Any]) -> None:
    client, doc = listening["client"], listening["doc"]
    assert 'data-sounds="on"' in client.get(f"/documents/{doc}/listen").text
    settings = client.get("/settings").text
    assert 'id="settings-sounds" name="sounds" value="on"' in settings
    assert "checked" in settings.split('id="settings-sounds"')[1].split(">")[0]
    off = client.get("/appearance", params={"sounds": "off", "back": "/settings"})
    assert off.status_code == 200  # followed back to Settings
    assert client.cookies.get("sci2audio-sounds") == "off"
    assert 'data-sounds="on"' not in client.get(f"/documents/{doc}/listen").text
    client.get("/appearance", params={"sounds": "loud", "back": "/settings"})
    assert client.cookies.get("sci2audio-sounds") == "off"  # anything else is not kept
