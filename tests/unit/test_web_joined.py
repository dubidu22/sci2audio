"""The pieces of a cut sentence on the Listen page and for the markers (#480, D-730, the
additions of plans/480-c2-tests.md): one element per sentence, and a marker belongs to the
whole sentence, whichever of its pieces it was set on."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from test_web_player import make, player_data, server, work_of
from web_helpers import book_folder, markers_of, offline, set_marker  # noqa: F401 - fixture

from sci2audio.core import Span
from sci2audio.web.markers import MarkerBook, anchor_of, place
from sci2audio.web.player import load_document, locate, read_audio_record

pytestmark = pytest.mark.usefixtures("offline")

# over the 400-character cut limit (#494): cut once, its later piece the longest
LONG = (
    "In the second survey the share of teachers who use the new material in every lesson has "
    "almost doubled since the start of the programme, while the share of those who never use "
    "it has fallen by half in the same time, in the same schools, with the same questionnaire "
    "and with the same people asking the questions, in every kind of school, from the small "
    "village schools with one class for all ages to the large city schools with several "
    "classes in each year."
)
TEXT = f"A short sentence first.\n\n{LONG}\n\nA short sentence last.\n"


@pytest.fixture
def book(tmp_path: Path) -> dict[str, Any]:
    client, config = server(tmp_path)
    doc = make(client, TEXT.encode(), "note.txt")["doc"]["id"]
    page = client.get(f"/documents/{doc}/listen").text
    data = player_data(page)
    elements = [chunk[3] for chunk in data["chunks"]]
    cut = [n for n, e in enumerate(elements) if elements.count(e) > 1 and e]
    assert len(cut) >= 2, f"the long sentence was not cut: {elements}"
    return {
        "client": client,
        "doc": doc,
        "page": page,
        "data": data,
        "elements": elements,
        "pieces": cut,
        "work": work_of(config, doc),
        "out": book_folder(config.output_folder, "note.txt"),
    }


def test_the_cut_sentence_is_one_element_with_its_whole_text(book: dict[str, Any]) -> None:
    first = book["pieces"][0]
    element = book["elements"][first]
    assert element == f"s{first}"
    assert all(book["elements"][n] == element for n in book["pieces"])
    found = re.search(rf'<span[^>]*id="{element}"[^>]*>(.*?)</span>', book["page"], re.S)
    assert found is not None
    opening = found[0][: found[0].index(">") + 1]
    assert f'data-chunk="{first}"' in opening
    words = re.sub(r"<[^>]+>", "", found[1])
    assert " ".join(words.split()) == LONG
    # the sentences around it are their own
    assert len(set(book["elements"])) == len(book["elements"]) - len(book["pieces"]) + 1


def test_a_new_marker_anchors_the_whole_sentence_from_any_piece(book: dict[str, Any]) -> None:
    client, doc, stamp = book["client"], book["doc"], book["data"]["audiobook"]
    first, *later = book["pieces"]
    marker = set_marker(client, doc, later[-1], stamp)  # a page that names a later piece
    (entry,) = markers_of(book["work"])["markers"]
    assert entry["anchor"]["text"] == LONG
    assert book["elements"][marker["chunk"]] == book["elements"][first]
    # M on the sentence again, by its first piece or any other: the same marker (toggle)
    for piece in book["pieces"]:
        again = set_marker(client, doc, piece, stamp, status=200)
        assert again["id"] == marker["id"]
    assert len(markers_of(book["work"])["markers"]) == 1


def test_a_marker_set_on_one_piece_before_480_is_the_sentences_marker(
    book: dict[str, Any],
) -> None:
    """An old marker anchored to the second piece only: the page shows it on the joined
    sentence, and M on that sentence finds it instead of setting a second one."""
    client, doc, stamp, work = book["client"], book["doc"], book["data"]["audiobook"], book["work"]
    first, second = book["pieces"][:2]
    document = load_document(work)
    old_span = _spans(book)[second]
    old, _ = MarkerBook().set(work, doc, anchor_of(document, old_span), lambda markers: None)
    shown = player_data(client.get(f"/documents/{doc}/listen").text)["markers"]
    # placed on the second piece, named by the sentence's first piece (#520)
    assert [(m["id"], m["chunk"], m["state"]) for m in shown] == [(old.id, first, "found")]
    assert book["elements"][second] == book["elements"][first]
    again = set_marker(client, doc, first, stamp, status=200)
    assert again["id"] == old.id
    assert len(markers_of(work)["markers"]) == 1


def test_the_api_and_the_page_name_a_marked_cut_sentence_by_its_first_piece(
    book: dict[str, Any],
) -> None:
    """#520 (web batch audit S1): a whole-sentence marker overlaps a later, longer piece most,
    yet the POST answer and the page's marker data name the sentence by its first piece, as
    `data-chunk`, the player's sentences and `MarkerIn.chunk` do."""
    client, doc, stamp = book["client"], book["doc"], book["data"]["audiobook"]
    first = book["pieces"][0]
    spans = _spans(book)
    longest = max(book["pieces"], key=lambda n: (spans[n].end - spans[n].start, -n))
    assert longest != first, "the first piece is the longest: this test proves nothing"
    for piece in (first, longest):  # set by any piece: the answer names the first
        marker = set_marker(client, doc, piece, stamp, status=201 if piece == first else 200)
        assert marker["chunk"] == first
    shown = player_data(client.get(f"/documents/{doc}/listen").text)["markers"]
    assert [(m["id"], m["chunk"], m["state"]) for m in shown] == [(marker["id"], first, "found")]


def _spans(book: dict[str, Any]) -> list[Any]:
    """The read-along's spans of the book's audiobook, as the server reads them."""
    record = read_audio_record(book["work"], book["doc"])
    return [chunk.span for chunk in locate(record, [book["out"]]).readalong.chunks]


def test_a_position_saved_in_a_later_piece_is_offered_to_continue(book: dict[str, Any]) -> None:
    """position.json names a time, never a piece: a stop in the middle of a cut sentence
    resolves as before (plans/480-c2-tests.md item 2)."""
    client, doc, data = book["client"], book["doc"], book["data"]
    start, end, chapter, _ = data["chunks"][book["pieces"][-1]]
    at = (start + end) / 2
    body = {"chapter": chapter, "time": at, "audiobook": data["audiobook"]}
    answer = client.post(f"/api/v1/documents/{doc}/position", json=body)
    assert answer.status_code == 204, answer.text
    page = client.get(f"/documents/{doc}/listen").text
    assert 'id="resume"' in page
    assert f'data-time="{at}"' in page


def test_a_whole_sentence_marker_on_an_audiobook_made_again_without_cuts(
    book: dict[str, Any],
) -> None:
    """The same text read as separate chunks (no joins, as before #480 or with a larger cut
    limit): a marker anchored to the whole sentence shows on the chunk it overlaps most
    (#490's rule, pinned for the new anchor, plans/480-c2-tests.md item 8)."""
    client, doc, stamp, work = book["client"], book["doc"], book["data"]["audiobook"], book["work"]
    first = book["pieces"][0]
    set_marker(client, doc, first, stamp)
    spans = _spans(book)
    document = load_document(work)
    whole = Span(spans[first].block, spans[first].start, spans[book["pieces"][-1]].end)
    # the marker the API set, as the markers file holds it
    marker, new = MarkerBook().set(work, doc, anchor_of(document, whole), lambda m: m[0])
    assert not new
    assert marker.anchor.text == LONG
    (placed,) = place([marker], document, spans)  # place() knows no joins: separate pieces
    longest = max(book["pieces"], key=lambda n: (spans[n].end - spans[n].start, -n))
    assert (placed.chunk, placed.state) == (longest, "found")
