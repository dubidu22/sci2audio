"""The Captures page (#398, ADR-008 2.1): every document's captures as ruled rows by document
and type, filtered by type and document, each placed in the document's current audiobook,
"Not read in this audiobook" and "Not found" listed and never dropped, and removal with Undo
also for a document whose audiobook is gone."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from test_web_captures_api import (
    capture,
    file_of,
    full_disk_while_carrying_over,
    page_data,
    sentences,
)
from test_web_player import make, work_of
from web_helpers import (
    FakeClock,
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    program,
)

from sci2audio.app.captures import CAPTURES
from sci2audio.web import create_app
from sci2audio.web.markers import MARKERS, markers_text
from sci2audio.web.player import AUDIO_RECORD, DOCUMENT_RECORD

pytestmark = pytest.mark.usefixtures("offline")

VOID = {"area", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}


class Node:
    def __init__(self, tag: str, attrs: dict[str, str | None], parent: Node | None) -> None:
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: list[Node] = []
        self.words: list[str] = []

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.words + [c.text for c in self.children]).split())

    @property
    def hidden(self) -> bool:
        """Hidden itself or inside something hidden."""
        node: Node | None = self
        while node is not None:
            if "hidden" in node.attrs:
                return True
            node = node.parent
        return False

    def all(self, cls: str = "", tag: str = "") -> list[Node]:
        found = []
        for child in self.children:
            if (not cls or cls in child.classes) and (not tag or child.tag == tag):
                found.append(child)
            found += child.all(cls, tag)
        return found

    def one(self, cls: str = "", tag: str = "") -> Node:
        (found,) = self.all(cls, tag)
        return found

    def by_id(self, wanted: str) -> Node | None:
        for node in [self, *self.all()]:
            if node.attrs.get("id") == wanted:
                return node
        return None


class Tree(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.root = Node("root", {}, None)
        self.at = self.root
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, dict(attrs), self.at)
        self.at.children.append(node)
        if tag not in VOID:
            self.at = node

    def handle_endtag(self, tag: str) -> None:
        node: Node | None = self.at
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.at = node.parent

    def handle_data(self, data: str) -> None:
        self.at.words.append(data)


def page(client: Any, **query: str) -> Node:
    answer = client.get("/captures", params=query)
    assert answer.status_code == 200, answer.text
    return Tree(answer.text).root


def rows(root: Node, shown: bool = True) -> list[dict[str, Any]]:
    """The rows in the page's order: those shown, or every one."""
    found = []
    for row in root.all("capture-row"):
        if shown and row.hidden:
            continue
        at = row.all("cp-at")
        state = row.all("cp-state")
        found.append(
            {
                "id": row.attrs.get("data-capture"),
                "kind": row.attrs.get("data-kind"),
                "document": row.attrs.get("data-document"),
                "label": row.one("cp-kind").text,
                "sentence": row.one("cp-text").text,
                "note": " ".join(n.text for n in row.all("cp-note")),
                "at": at[0].text if at else "",
                "state": state[0].text if state else "",
                "listen": [a.attrs.get("href") for a in row.all(tag="a")],
                "remove": [b.text for b in row.all(tag="button")],
            }
        )
    return found


def counts(root: Node) -> dict[str, str]:
    group = root.one("cap-kinds")
    return {b.attrs["data-kind"] or "": b.one("num").text for b in group.all(tag="button")}


@pytest.fixture
def studied(tmp_path: Path) -> dict[str, Any]:
    """Two documents: the first with a mark and a note on one sentence and a quote on the
    next, the second with a quote."""
    clock = FakeClock()
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source(), clock=clock)
    client = program(app, config)
    doc = make(client)["doc"]["id"]
    data = page_data(client, doc)
    first, second = sentences(data)[1:3]
    ids = {
        "mark": capture(client, doc, "mark", first, data["audiobook"])["id"],
        "note": capture(client, doc, "note", first, data["audiobook"], "Ask Sam.")["id"],
        "quote": capture(client, doc, "quote", second, data["audiobook"])["id"],
    }
    other = make(client, pdf_bytes("Sleep came late. Work came early."), "other.pdf")["doc"]["id"]
    other_data = page_data(client, other)
    other_quote = capture(
        client, other, "quote", sentences(other_data)[1], other_data["audiobook"]
    )["id"]
    return {
        "client": client,
        "config": config,
        "doc": doc,
        "other": other,
        "data": data,
        "ids": ids,
        "other_quote": other_quote,
        "work": work_of(config, doc),
        "clock": clock,
    }


def test_the_page_lists_every_capture_by_document_in_reading_order(
    studied: dict[str, Any],
) -> None:
    client, doc, other, ids = (studied[k] for k in ("client", "doc", "other", "ids"))
    root = page(client)
    shown = rows(root)
    # by document, each its own group; in each, by sentence, and on one sentence in the
    # dock's order (note, quote, mark)
    groups = [g for g in root.all("capture-group") if not g.hidden]
    assert sorted(g.attrs["data-document"] or "" for g in groups) == sorted([doc, other])
    for group in groups:
        mine = [r["document"] for r in rows(group)]
        assert mine == [group.attrs["data-document"]] * len(mine)
        assert group.one(tag="h2").text == ("paper.pdf" if mine[0] == doc else "other.pdf")
    assert [r["id"] for r in shown if r["document"] == doc] == [
        ids["note"],
        ids["mark"],
        ids["quote"],
    ]
    by_id = {r["id"]: r for r in shown}
    note, mark, quote = by_id[ids["note"]], by_id[ids["mark"]], by_id[ids["quote"]]
    assert (note["label"], note["note"]) == ("Note", "Ask Sam.")
    assert (quote["label"], mark["label"], mark["note"]) == ("Quote to cite", "Mark", "")
    printed = file_of(studied["work"])["captures"][0]["anchor"]["text"]
    assert note["sentence"] == mark["sentence"] == f"“{printed}”"
    for row in (note, mark, quote):
        assert row["at"].startswith("Chapter "), row
        assert row["state"] == ""
        assert row["listen"] == [f"/documents/{doc}/listen#capture-{row['id']}"]
        assert row["remove"] == ["Remove"]
    summary = root.by_id("captures-summary")
    assert summary is not None
    assert summary.text == "4 captures from 2 documents"
    assert counts(root) == {"all": "4", "note": "1", "quote": "2", "mark": "1"}
    # the rail names the page, and marks it as the one shown
    link = root.by_id("nav-captures")
    assert link is not None
    assert (link.attrs["href"], link.attrs.get("aria-current")) == ("/captures", "page")
    assert link.text == "Captures"


def test_the_filters_show_one_type_and_one_document(studied: dict[str, Any]) -> None:
    client, doc, other, ids = (studied[k] for k in ("client", "doc", "other", "ids"))
    quotes = page(client, type="quote")
    assert sorted(r["id"] for r in rows(quotes)) == sorted([ids["quote"], studied["other_quote"]])
    assert len(rows(quotes, shown=False)) == 4  # the others are there, for the script
    pressed = [
        b.attrs["data-kind"]
        for b in quotes.one("cap-kinds").all(tag="button")
        if b.attrs.get("aria-pressed") == "true"
    ]
    assert pressed == ["quote"]
    mine = page(client, **{"from": doc})
    assert [r["id"] for r in rows(mine)] == [ids["note"], ids["mark"], ids["quote"]]
    assert counts(mine) == {"all": "3", "note": "1", "quote": "1", "mark": "1"}
    chosen = [o.attrs.get("value") for o in mine.all(tag="option") if "selected" in o.attrs]
    assert chosen == [doc]
    both = page(client, type="mark", **{"from": other})
    assert rows(both) == []
    none = both.by_id("captures-none")
    assert none is not None
    assert not none.hidden
    assert none.text == "No captures of this kind yet."
    # anything else is the whole list
    assert len(rows(page(client, type="card", **{"from": "f" * 16}))) == 4


def test_a_capture_the_audiobook_does_not_read_is_listed_as_not_read(
    studied: dict[str, Any],
) -> None:
    """ADR-008 2.1 item 3: only the second chapter is read now; the captures of the first
    are listed, and their stored anchors stay as they are."""
    client, doc, ids, work = (studied[k] for k in ("client", "doc", "ids", "work"))
    before = (work / CAPTURES).read_bytes()
    body = {"kind": "audio", "document": doc, "overwrite": True, "settings": {"chapters": [1]}}
    job = client.post("/api/v1/jobs", json=body)
    assert json.loads(events(client, job.json()["id"])[-1][1])["state"] == "done"
    shown = {r["id"]: r for r in rows(page(client, **{"from": doc}))}
    assert set(shown) == set(ids.values())
    for kind in ("mark", "note"):
        row = shown[ids[kind]]
        assert row["state"].startswith("Not read in this audiobook"), row
        assert (row["at"], row["listen"]) == ("", [])  # nowhere to play it from
        assert row["remove"] == ["Remove"]
    assert shown[ids["note"]]["note"] == "Ask Sam."
    assert shown[ids["quote"]]["state"] == ""
    assert (work / CAPTURES).read_bytes() == before


def test_a_capture_whose_sentence_is_not_found_is_listed_as_not_found(
    studied: dict[str, Any],
) -> None:
    client, doc, work = studied["client"], studied["doc"], studied["work"]
    data = file_of(work)
    lost = dict(data["captures"][0])
    lost.update(id="f" * 16, type="note", text="Still mine.")
    lost["anchor"] = {"block": 0, "start": 0, "end": 12, "text": "Not in here."}
    data["captures"].append(lost)
    (work / CAPTURES).write_text(json.dumps(data), encoding="utf-8")
    before = (work / CAPTURES).read_bytes()
    shown = rows(page(client, **{"from": doc}))
    assert shown[-1]["id"] == "f" * 16  # after those found
    assert shown[-1]["state"].startswith("Not found in this audiobook")
    assert (shown[-1]["sentence"], shown[-1]["note"]) == ("“Not in here.”", "Still mine.")
    assert shown[-1]["listen"] == []
    assert (work / CAPTURES).read_bytes() == before


def test_without_an_audiobook_the_captures_stay_listed_and_can_be_removed_and_put_back(
    studied: dict[str, Any],
) -> None:
    client, doc, ids, work = (studied[k] for k in ("client", "doc", "ids", "work"))
    (work / AUDIO_RECORD).unlink()
    shown = {r["id"]: r for r in rows(page(client, **{"from": doc}))}
    assert set(shown) == set(ids.values())
    for row in shown.values():
        assert row["state"].startswith("This document has no audiobook now"), row
        assert row["listen"] == []
    url = f"/api/v1/documents/{doc}/captures/{ids['quote']}"
    removed = client.delete(url)
    assert removed.status_code == 200, removed.text
    assert (removed.json()["state"], removed.json()["chunk"]) == ("no-audiobook", None)
    assert ids["quote"] not in (work / CAPTURES).read_text(encoding="utf-8")
    assert ids["quote"] not in {r["id"] for r in rows(page(client), shown=False)}
    back = client.post(f"{url}/restore")
    assert (back.status_code, back.json()) == (201, removed.json())
    assert ids["quote"] in {r["id"] for r in rows(page(client))}


@pytest.mark.parametrize("shift", [(0, 0), (1, 0), (0, -1), (2, -2)])
def test_without_an_audiobook_undo_is_refused_when_the_sentence_has_its_type_again(
    studied: dict[str, Any], shift: tuple[int, int]
) -> None:
    """One capture of a type per sentence, whatever anchor the new one holds (#934)."""
    client, doc, ids, work = (studied[k] for k in ("client", "doc", "ids", "work"))
    quote = next(c for c in file_of(work)["captures"] if c["id"] == ids["quote"])
    url = f"/api/v1/documents/{doc}/captures/{ids['quote']}"
    assert client.delete(url).status_code == 200
    (work / AUDIO_RECORD).unlink()
    data = file_of(work)
    again = json.loads(json.dumps(quote))
    again["id"] = "e" * 16
    block_text = again["anchor"]["text"]
    start, end = again["anchor"]["start"] + shift[0], again["anchor"]["end"] + shift[1]
    again["anchor"].update(
        start=start,
        end=end,
        text=block_text[shift[0] : len(block_text) + shift[1]],
    )
    data["captures"].append(again)
    (work / CAPTURES).write_text(json.dumps(data), encoding="utf-8")
    before = (work / CAPTURES).read_bytes()
    refused = client.post(f"{url}/restore")
    assert (refused.status_code, refused.json()["error"]) == (409, "captured-again")
    assert (work / CAPTURES).read_bytes() == before


def test_without_an_audiobook_undo_puts_back_a_capture_beside_another_sentences(
    studied: dict[str, Any],
) -> None:
    """A capture of the type on the next sentence is no clash."""
    client, doc, ids, work = (studied[k] for k in ("client", "doc", "ids", "work"))
    url = f"/api/v1/documents/{doc}/captures/{ids['mark']}"
    assert client.delete(url).status_code == 200
    (work / AUDIO_RECORD).unlink()
    data = file_of(work)
    quote = next(c for c in data["captures"] if c["id"] == ids["quote"])
    beside = json.loads(json.dumps(quote))
    beside.update(id="e" * 16, type="mark")
    data["captures"].append(beside)
    (work / CAPTURES).write_text(json.dumps(data), encoding="utf-8")
    back = client.post(f"{url}/restore")
    assert back.status_code == 201, back.text


def stored_beside(work: Path, quote: dict[str, Any], **anchor: Any) -> bytes:
    """A second quote stored with the removed one's anchor changed by `anchor`; the file's
    bytes after."""
    data = file_of(work)
    other = json.loads(json.dumps(quote))
    other["id"] = "e" * 16
    other["anchor"].update(anchor)
    data["captures"].append(other)
    (work / CAPTURES).write_text(json.dumps(data), encoding="utf-8")
    return (work / CAPTURES).read_bytes()


def removed_without_audiobook(studied: dict[str, Any], kind: str) -> tuple[str, dict[str, Any]]:
    client, doc, ids, work = (studied[k] for k in ("client", "doc", "ids", "work"))
    capture = next(c for c in file_of(work)["captures"] if c["id"] == ids[kind])
    url = f"/api/v1/documents/{doc}/captures/{ids[kind]}"
    assert client.delete(url).status_code == 200
    (work / AUDIO_RECORD).unlink()
    return url, capture


def test_without_an_audiobook_undo_finds_a_quote_whose_text_moved_on_its_sentence(
    studied: dict[str, Any],
) -> None:
    """#955: the other quote names a block that is gone, but its text is the removed
    quote's sentence, where the document finds it: a clash its own place would miss."""
    client, work = studied["client"], studied["work"]
    url, quote = removed_without_audiobook(studied, "quote")
    before = stored_beside(work, quote, block=quote["anchor"]["block"] + 1000)
    refused = client.post(f"{url}/restore")
    assert (refused.status_code, refused.json()["error"]) == (409, "captured-again")
    assert (work / CAPTURES).read_bytes() == before


def test_without_an_audiobook_undo_puts_back_a_quote_where_another_moved_away(
    studied: dict[str, Any],
) -> None:
    """#955: the other quote holds the removed one's place but another sentence's text,
    which the document finds elsewhere: no clash, though the two places are one."""
    client, work = studied["client"], studied["work"]
    url, quote = removed_without_audiobook(studied, "quote")
    mark = next(c for c in file_of(work)["captures"] if c["id"] == studied["ids"]["mark"])
    assert mark["anchor"]["text"] != quote["anchor"]["text"]
    stored_beside(work, quote, text=mark["anchor"]["text"])
    back = client.post(f"{url}/restore")
    assert back.status_code == 201, back.text


@pytest.mark.parametrize(
    ("moved", "answer"),
    [("place", 409), ("text", 201)],
    ids=["same-place-other-text", "same-text-other-place"],
)
def test_without_an_audiobook_or_a_readable_document_undo_compares_the_stored_places(
    studied: dict[str, Any], moved: str, answer: int
) -> None:
    """#955: with the document record unreadable nothing can be found, so the stored
    places decide: the same place is a clash whatever its text, another place none."""
    client, work = studied["client"], studied["work"]
    url, quote = removed_without_audiobook(studied, "quote")
    mark = next(c for c in file_of(work)["captures"] if c["id"] == studied["ids"]["mark"])
    if moved == "place":
        before = stored_beside(work, quote, text=mark["anchor"]["text"])
    else:
        before = stored_beside(work, quote, block=quote["anchor"]["block"] + 1000)
    (work / DOCUMENT_RECORD).write_text("{broken", encoding="utf-8")
    back = client.post(f"{url}/restore")
    assert back.status_code == answer, back.text
    if answer == 409:
        assert back.json()["error"] == "captured-again"
        assert (work / CAPTURES).read_bytes() == before
    else:
        assert studied["ids"]["quote"] in (work / CAPTURES).read_text(encoding="utf-8")


def test_an_unreadable_file_is_named_in_its_group_and_never_written(
    studied: dict[str, Any],
) -> None:
    client, doc, work = studied["client"], studied["doc"], studied["work"]
    (work / CAPTURES).write_text("{broken", encoding="utf-8")
    root = page(client)
    group = root.by_id(f"group-{doc}")
    assert group is not None
    assert not group.hidden
    assert str(work / CAPTURES) in group.one("note").text
    assert [r["document"] for r in rows(root)] == [studied["other"]]
    assert (work / CAPTURES).read_text(encoding="utf-8") == "{broken"


def test_markers_not_carried_over_are_named_and_left_as_they_are(tmp_path: Path) -> None:
    voice = FakeVoice()
    config = make_config(tmp_path)
    client = program(create_app(config, voice=lambda models_dir: voice.source()), config)
    doc = make(client)["doc"]["id"]
    work = work_of(config, doc)
    (work / MARKERS).write_text('{"a person\'s": "markers"}', encoding="utf-8")
    root = page(client)
    group = root.by_id(f"group-{doc}")
    assert group is not None
    assert str(work / MARKERS) in group.one("note").text
    assert not (work / CAPTURES).exists()


def test_markers_whose_carry_over_cannot_be_written_are_named_and_left_as_they_are(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#910: a full disk during the carry-over: the group says so and names markers.json."""
    voice = FakeVoice()
    config = make_config(tmp_path)
    client = program(create_app(config, voice=lambda models_dir: voice.source()), config)
    doc = make(client)["doc"]["id"]
    work = work_of(config, doc)
    raw = markers_text(doc, []).encode("utf-8")
    (work / MARKERS).write_bytes(raw)
    full_disk_while_carrying_over(monkeypatch)
    root = page(client)
    group = root.by_id(f"group-{doc}")
    assert group is not None
    note = group.one("note").text
    assert "could not be saved as captures" in note
    assert str(work / MARKERS) in note
    assert (work / MARKERS).read_bytes() == raw
    assert not (work / CAPTURES).exists()


def test_with_nothing_captured_the_page_says_how_to_capture(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    client = program(create_app(config), config)
    root = page(client)
    assert rows(root, shown=False) == []
    empty = root.by_id("captures-empty")
    assert empty is not None
    assert "N, Q or M" in empty.text
    assert root.by_id("capture-filters") is None


def test_the_page_in_german(studied: dict[str, Any]) -> None:
    client = studied["client"]
    client.cookies.set("sci2audio-language", "de")
    root = page(client)
    assert root.one(tag="h1").text == "Fundstücke"
    summary = root.by_id("captures-summary")
    assert summary is not None
    assert summary.text == "4 Fundstücke aus 2 Dokumenten"
    labels = {r["label"] for r in rows(root)}
    assert labels == {"Notiz", "Zitat zum Belegen", "Marke"}
    assert {b for r in rows(root) for b in r["remove"]} == {"Entfernen"}
    nav = root.by_id("nav-captures")
    assert nav is not None
    assert nav.text == "Fundstücke"
