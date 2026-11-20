"""The Listen page of the Working Reader (#392, #393; D-665 conflicts 2 and 3, D-704b): the
audiobook's own edits drawn on the text, the guard that draws them only for an audiobook of
this version of sci2audio, the Changes and Chapters panel, the dock's ticks and clock, and
the sentence announcements the person can switch on.

Part one builds views from hand-made documents and steps; part two reads the page after a
real audio job with the fake voice (as `test_web_player` does).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from long_book import CHAPTERS, PAGES, PARAGRAPHS, long_book
from test_web_player import _Mover, make, readalong, record, server, work_of
from web_helpers import (
    events,
    offline,  # noqa: F401 - fixture
)

from sci2audio import __version__
from sci2audio.core import Document, Edit, EditKind, Section, Span
from sci2audio.testing.documents import make_document
from sci2audio.textprep import BUILT_IN_STEPS, Category, Stage, StepContext, TextStep
from sci2audio.web.player import ChangeView, Part, PlayerView, _shown, build_view, shown

THIS = __version__


class _Edits(TextStep):
    """Proposes the given edits, in the given category, in every block holding TEXT."""

    languages = ("*",)
    stage = Stage.INLINE

    def __init__(self, category: Category, *edits: tuple[int, int, EditKind, str]) -> None:
        self.id = f"test-{category}"
        self.category = category
        self.edits = edits

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [
            Edit(Span(block, start, end), kind, "a test edit", self.id, replacement=said)
            for block, found in enumerate(document.blocks)
            if found.text == TEXT
            for start, end, kind, said in self.edits
        ]


def steps_with(*extra: TextStep) -> list[TextStep]:
    """The built-in steps with `extra` in their place: block steps first, moves last."""
    return [
        step
        for stage in (Stage.BLOCK, Stage.INLINE, Stage.MOVE)
        for step in (*BUILT_IN_STEPS, *extra)
        if step.stage is stage
    ]


TEXT = "It fell by 12 ms (Okafor, 2021) on early shifts. Naps were not counted."
CITATION = (TEXT.index(" (Okafor"), TEXT.index(" on early"))
UNIT = (TEXT.index("ms"), TEXT.index("ms") + 2)
FIRST = (0, TEXT.index("Naps") - 1)
SECOND = (TEXT.index("Naps"), len(TEXT))


def paper() -> Document:
    return make_document([("heading", "1 Results"), ("paragraph", TEXT)])


def listen(
    *steps: TextStep, made_with: str = THIS, switched_off: frozenset[str] = frozenset()
) -> PlayerView:
    data = readalong([(0, 0, 9), (1, *FIRST), (1, *SECOND)])
    return build_view(
        paper(),
        record(chunks=3, made_with=made_with, switched_off=switched_off),
        data,
        steps_with(*steps),
    )


def citation_and_unit() -> list[TextStep]:
    return [
        _Edits(Category.CITATIONS, (*CITATION, EditKind.REMOVE, "")),
        # the built-in unit step reads "ms" the same way, in the same category
        _Edits(Category.NUMBERS_AND_UNITS, (*UNIT, EditKind.REPLACE, "milliseconds")),
    ]


def sentence(view: PlayerView, element: str) -> Any:
    for chapter in view.chapters:
        for block in chapter.blocks:
            for piece in block.pieces:
                if piece.element == element:
                    return piece
    raise AssertionError(element)


# ---- the marks (#392, D-665 conflict 2) ------------------------------------------------


def test_a_cut_and_a_reading_show_inside_their_sentence_which_keeps_its_span() -> None:
    view = listen(*citation_and_unit())
    assert view.marked
    first = sentence(view, "s1")
    assert first.text == shown(TEXT, *FIRST)  # the element still holds exactly its span
    assert "".join(part.text for part in first.parts) == first.text
    assert first.parts == (
        Part("It fell by 12 "),
        Part("ms", "said", "milliseconds"),
        Part(" (Okafor, 2021)", "cut"),
        Part(" on early shifts."),
    )
    assert sentence(view, "s2").parts == ()  # nothing changed in it: plain text


def test_a_mark_across_the_cut_of_a_cut_sentence_is_drawn_in_the_joined_sentence() -> None:
    """#480 (plans/480-c2-tests.md item 5): the voice's cut falls inside the citation, so the
    cut mark lies across the join; the joined sentence draws it whole, and its parts still
    join up to the sentence's text."""
    middle = TEXT.index("2021")
    data = readalong([(0, 0, 9), (1, 0, middle), (1, middle, FIRST[1]), (1, *SECOND)], joins=(2,))
    view = build_view(
        paper(), record(chunks=4, made_with=THIS), data, steps_with(*citation_and_unit())
    )
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s1", "s3"]
    first = sentence(view, "s1")
    assert first.text == shown(TEXT, *FIRST)
    assert "".join(part.text for part in first.parts) == first.text
    assert first.parts == (
        Part("It fell by 12 "),
        Part("ms", "said", "milliseconds"),
        Part(" (Okafor, 2021)", "cut"),
        Part(" on early shifts."),
    )


def test_a_category_switched_off_for_the_audiobook_is_not_marked() -> None:
    # the job's own settings (audio.json) decide, never today's switches (D-665)
    view = listen(*citation_and_unit(), switched_off=frozenset({"citations"}))
    assert sentence(view, "s1").parts == (
        Part("It fell by 12 "),
        Part("ms", "said", "milliseconds"),
        Part(" (Okafor, 2021) on early shifts."),
    )


def test_an_audiobook_of_another_version_shows_no_marks() -> None:
    """D-704b: the steps that rebuild the run are the audiobook's only when the same version
    of sci2audio made it; a wrong mark is worse than none."""
    for other in ("0.9.0", ""):
        view = listen(*citation_and_unit(), made_with=other)
        assert not view.marked
        assert view.made_with == other
        assert all(piece.parts == () for piece in view.chapters[0].blocks[0].pieces)
        assert {change.count for change in view.changes} == {None}


def test_a_reading_that_looks_like_the_print_and_a_whole_block_are_not_marked() -> None:
    ligature = "ﬁ"  # the Unicode step reads it as "fi": it looks the same
    text = f"A {ligature}ne result. The end."
    document = make_document([("heading", "1 One"), ("paragraph", text), ("paragraph", "Gone.")])
    same = _Edits(Category.CHARACTERS, (2, 3, EditKind.REPLACE, "fi"))

    class _Whole(TextStep):
        id = "whole"
        languages = ("*",)
        category = Category.REFERENCES
        stage = Stage.BLOCK

        def find(self, document: Document, context: StepContext) -> list[Edit]:
            return [Edit(Span(2, 0, 5), EditKind.REMOVE, "a whole block", self.id)]

    data = readalong([(0, 0, 5), (1, 0, 13), (1, 14, len(text))])
    view = build_view(
        document,
        record(chunks=3, made_with=THIS),
        data,
        steps_with(same, _Whole()),
    )
    blocks = view.chapters[0].blocks
    assert all(piece.parts == () for block in blocks for piece in block.pieces)
    assert not blocks[1].read  # the whole block says "Not read" instead
    # the panel counts what the page shows: the cut block, not the look-alike (#462)
    counts = {c.category: c.count for c in view.changes}
    assert counts["characters"] == 0
    assert counts["references"] == 1


def test_a_joined_word_and_a_placeholders_notice_are_not_marked() -> None:
    """The hyphen step's join shows as the joined word (#286); a placeholder's notice box
    already says what was read in its place."""
    text = "A re-\nsult was seen. The end."
    blocks = [("heading", "1 One"), ("paragraph", text), ("table", "a b\n1 2")]
    document = make_document(blocks)
    data = readalong([(0, 0, 5), (1, 0, 20), (1, 21, len(text)), (2, 0, 7)])
    view = build_view(document, record(chunks=4, made_with=THIS), data, steps_with())
    paragraph, table = view.chapters[0].blocks
    assert paragraph.pieces[0].text == "A result was seen."  # joined, as the voice read it
    assert table.notice
    assert all(piece.parts == () for block in (paragraph, table) for piece in block.pieces)
    # the panel counts what the page shows: the notice box, not the join (#462)
    counts = {c.category: c.count for c in view.changes}
    assert counts["characters"] == 0
    assert counts["tables-and-figures"] == 1


def test_page_furniture_is_never_shown_but_its_removal_is_counted() -> None:
    """Review #489 S1: the sheet is the text without its furniture, as it is heard, so the
    furniture step's removal counts although no block of it is drawn."""
    document = make_document(
        [("heading", "1 One"), ("furniture", "Journal of Things 12"), ("paragraph", TEXT)]
    )
    data = readalong([(0, 0, 5), (2, *FIRST), (2, *SECOND)])
    view = build_view(document, record(chunks=3, made_with=THIS), data, steps_with())
    chapter = view.chapters[0]
    assert chapter.title_block is not None
    assert [chapter.title_block.index, *(b.index for b in chapter.blocks)] == [0, 2]
    assert {c.category: c.count for c in view.changes}["page-furniture"] == 1


def test_a_notice_box_counts_once_and_the_edits_inside_its_text_do_not() -> None:
    """Review #489 S3 (M1, M2): a placeholder read as its notice draws the box, not its
    text. Today's run sets aside every other edit in a placeholder's text (searched: each
    stage, REMOVE, PAUSE and an insert, at its start, inside and at its end), so the guard
    is pinned on `_shown` itself with the edit the run would have to accept."""
    table = "a b\n1 2"

    class _InTable(TextStep):
        id = "test-in-table"
        languages = ("*",)
        category = Category.CITATIONS
        stage = Stage.INLINE

        def find(self, document: Document, context: StepContext) -> list[Edit]:
            return [
                Edit(Span(n, 0, 3), EditKind.REMOVE, "a test edit", self.id)
                for n, block in enumerate(document.blocks)
                if block.text == table
            ]

    document = make_document([("heading", "1 One"), ("table", table)])
    data = readalong([(0, 0, 5), (1, 0, 7)])
    view = build_view(document, record(chunks=2, made_with=THIS), data, steps_with(_InTable()))
    assert view.chapters[0].blocks[0].notice
    counts = {c.category: c.count for c in view.changes}
    assert counts["tables-and-figures"] == 1
    assert counts["citations"] == 0
    inside = _InTable().find(document, StepContext("en"))[0]
    assert not _shown(document, inside, {1}, ())
    notice = Edit(Span(1, 0, 7), EditKind.REPLACE, "a notice", "table-figure-notices", "A table.")
    assert _shown(document, notice, {1}, ())
    assert _shown(document, inside, (), ())  # read as printed: the cut is drawn


def test_only_the_removal_of_page_furniture_counts() -> None:
    """Review #489 S1: the furniture rule is its own, not a side effect of the whole-block
    rule: no other edit in a furniture block is counted, whole or not."""
    document = make_document([("paragraph", "Text."), ("furniture", "Journal of Things 12")])
    cut = Edit(Span(1, 0, 7), EditKind.REMOVE, "a part", "test")
    said = Edit(Span(1, 0, 7), EditKind.REPLACE, "a reading", "test", "Paper")
    assert _shown(document, cut, (), ())
    assert not _shown(document, said, (), ())


def test_a_moved_note_counts_only_when_the_audiobook_read_it_at_its_mark() -> None:
    """Review #489 S3 (M3, M4): a footnote move counts when the read-along reads the note
    at its mark (#213); an audiobook that read it where printed shows it there, unmoved."""
    document = make_document(
        [
            ("heading", "1 One"),
            ("paragraph", "It works.1 It holds."),
            ("heading", "2 Two"),
            ("footnote", "1 A note."),
            ("paragraph", "More."),
        ],
        sections=[Section("1 One", 1, 0, 2), Section("2 Two", 1, 2, 5)],
    )
    chapters = (("One", 0), ("Two", 4))
    at_mark = [(0, 0, 5), (1, 0, 9), (3, 0, 9), (1, 11, 20), (2, 0, 5), (4, 0, 5)]
    printed = [(0, 0, 5), (1, 0, 9), (1, 11, 20), (2, 0, 5), (3, 0, 9), (4, 0, 5)]
    counts = {}
    for name, spans, owners in (
        ("at mark", at_mark, [0, 0, 0, 0, 1, 1]),
        ("printed", printed, [0, 0, 0, 1, 1, 1]),
    ):
        data = readalong(spans, chapters if name == "at mark" else (("One", 0), ("Two", 3)), owners)
        view = build_view(
            document, record(chunks=6, made_with=THIS), data, [*BUILT_IN_STEPS, _Mover()]
        )
        counts[name] = {c.category: c.count for c in view.changes}["footnotes"]
    assert counts == {"at mark": 1, "printed": 0}


def test_a_cut_between_sentences_is_struck_where_it_stands() -> None:
    view = listen(_Edits(Category.CITATIONS, (FIRST[1], SECOND[0], EditKind.REMOVE, "")))
    gap = view.chapters[0].blocks[0].pieces[1]
    assert gap.element is None
    assert gap.parts == (Part(" ", "cut"),)


# ---- the panel's Changes (#393, D-665 conflict 3) --------------------------------------


def test_changes_say_each_category_as_the_audiobook_was_made_and_count_its_edits() -> None:
    view = listen(*citation_and_unit(), switched_off=frozenset({"footnote-texts"}))
    changes = {change.category: change for change in view.changes}
    assert list(changes) == [str(category) for category in Category]
    assert changes["citations"] == ChangeView("citations", True, 1)
    assert changes["numbers-and-units"] == ChangeView("numbers-and-units", True, 1)
    assert changes["abbreviations"] == ChangeView("abbreviations", True, 0)
    assert not changes["footnote-texts"].on
    assert changes["links"].count == 0


def test_an_edit_in_a_chapter_left_out_is_not_counted() -> None:
    document = make_document(
        [("heading", "Results"), ("paragraph", TEXT), ("heading", "Left out"), ("paragraph", TEXT)],
        sections=(Section("Results", 1, 0, 2), Section("Left out", 1, 2, 4)),
    )
    data = readalong([(0, 0, 7), (1, *FIRST)])
    view = build_view(
        document,
        record(chunks=2, made_with=THIS),
        data,
        steps_with(_Edits(Category.CITATIONS, (*CITATION, EditKind.REMOVE, ""))),
    )
    assert len(view.chapters) == 1  # the chapter left out is not shown (#472)
    assert {c.category: c.count for c in view.changes}["citations"] == 1  # not 2
    assert view.duration == data.duration


@pytest.mark.benchmark
def test_benchmark_the_view_of_a_thousand_page_book(benchmark) -> None:  # type: ignore[no-untyped-def]
    """`build_view` of the 1,000-page book with its marks (docs/baseline.md)."""
    document, data = long_book()
    played = record(chunks=len(data.chunks), made_with=THIS, switched_off=frozenset())
    view = benchmark.pedantic(
        build_view, (document, played, data, list(BUILT_IN_STEPS)), rounds=3, iterations=1
    )
    assert view.marked
    assert len(view.chapters) == CHAPTERS  # each heading is its chapter's title
    assert sum(len(chapter.blocks) for chapter in view.chapters) == PAGES * PARAGRAPHS


# ---- the page, after a real audio job ----------------------------------------------------

pytestmark = pytest.mark.usefixtures("offline")


def page_of(client: Any, doc: str, **cookies: str) -> str:
    for name, value in cookies.items():
        client.cookies.set(f"sci2audio-{name}", value)
    response = client.get(f"/documents/{doc}/listen")
    assert response.status_code == 200
    return str(response.text)


def made_with(config: Any, doc: str, version: str) -> None:
    path = work_of(config, doc) / "audio.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sci2audio"] = version
    path.write_text(json.dumps(data), encoding="utf-8")


def test_the_page_draws_the_audiobooks_marks_and_ignores_todays_switches(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    with client:
        doc = make(client)["doc"]["id"]
        cut = '<s class="cut"> (Smith, 2020)</s>'
        assert cut in page_of(client, doc)
        assert 'id="marks-note"' not in page_of(client, doc)
        # the switch moves for the next audiobook: this one keeps its marks (D-665)
        saved = client.put("/api/v1/settings", json={"switched_off": ["citations"]})
        assert saved.status_code == 200, saved.text
        assert cut in page_of(client, doc)


def test_another_versions_audiobook_says_why_it_is_not_marked(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    with client:
        doc = make(client)["doc"]["id"]
        made_with(config, doc, "0.9.0")
        page = page_of(client, doc)
        assert 'class="cut"' not in page
        assert "Things happen (Smith, 2020) and more." in page
        note = re.search(r'<p class="marks-note" id="marks-note">(.*?)</p>', page, re.S)
        assert note is not None
        assert "Made with sci2audio 0.9.0: the changes are not marked" in note[1]
        assert f'<a href="/documents/{doc}">Make the audiobook again to see them.</a>' in note[1]
        assert 'class="chg-count"' not in page  # no counts without the marks
        german = page_of(client, doc, language="de")
        assert "Erstellt mit sci2audio 0.9.0: Die Änderungen sind hier nicht" in german
        assert "Erstellen Sie das Hörbuch neu, um sie zu sehen." in german


def test_the_panel_the_dock_and_the_outline(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    with client:
        doc = make(client)["doc"]["id"]
        page = page_of(client, doc)
        data = re.search(r'<script id="player-data" type="application/json">(.*?)</script>', page)
        assert data is not None
        chapters = json.loads(data[1])["chapters"]
        duration = float(re.findall(r'id="timeline" min="0" max="([0-9.]+)"', page)[0])
        # one tick per chapter start after the first, at its share of the book
        ticks = re.findall(r'<line x1="([0-9.]+)%" x2="\1%"', page)
        assert [float(t) for t in ticks] == pytest.approx(
            [c["start"] / duration * 100 for c in chapters[1:]], abs=0.001
        )
        assert re.search(r'id="clock" class="clock">0:00 of 0:\d\d</span>', page)
        outline = re.findall(
            r'<span class="ot">([^<]*)</span><span class="oc">([^<]*)</span>', page
        )
        assert [title for title, _ in outline] == ["Introduction", "Methods"]
        assert outline[0][1] == "0:00"
        # Changes: read-only, each category's state and count, and the way to Prepare
        assert 'role="switch"' not in page.split('id="panel-changes"')[1].split("</div>")[0]
        assert re.search(r'<span class="chg-name">Citations[^<]*</span>', page)
        assert '<span class="chg-count">1 change</span>' in page
        assert f'<a href="/documents/{doc}">Open Prepare</a>' in page
        # every button player.js wires is drawn disabled (#350, #427)
        for button in re.findall(r"<button[^>]*>", page.split('id="dock"')[1]):
            if "back-to-reading" not in button:
                assert " disabled" in button, button


def test_focus_listening_is_drawn_hidden_with_its_buttons_disabled(tmp_path: Path) -> None:
    """#394: Focus is a mode of the page, drawn hidden; its stage is filled by player.js."""
    client, _config = server(tmp_path)
    with client:
        doc = make(client)["doc"]["id"]
        page = page_of(client, doc)
        assert re.search(
            r'<button type="button" class="sm" id="focus-on" aria-keyshortcuts="F" disabled>',
            page,
        )
        assert 'aria-keyshortcuts="P"' in page.split('id="panel-toggle"')[1].split(">")[0]
        view = page.split('<section class="focus-view" id="focus-view"')[1].split("</section>")[0]
        assert view.startswith(' aria-label="Focus listening" tabindex="-1" hidden>')
        assert re.search(r'id="focus-off" aria-keyshortcuts="Escape" disabled>', view)
        assert '<span id="focus-chapter" lang="en">Introduction</span>' in view
        assert '<div class="focus-stage" lang="en">' in view
        for empty in (
            'id="focus-prev"></p>',
            '<span id="focus-now"></span>',
            'id="focus-next"></p>',
        ):
            assert empty in view
        # the view comes after the sheet, so the sheet's status line stays above it
        assert page.index('id="message"') < page.index('id="focus-view"')


def test_the_sentence_is_announced_only_when_switched_on(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    with client:
        doc = make(client)["doc"]["id"]
        page = page_of(client, doc)
        assert 'aria-live="polite"' not in page.split('id="text"')[0].split('id="message"')[1]
        assert 'id="reading"' not in page
        assert 'data-announce="on"' not in page
        on = page_of(client, doc, announce="on")
        assert '<p id="reading" class="visually-hidden" aria-live="polite"></p>' in on
        assert 'data-announce="on"' in on


def test_the_marks_stay_in_the_audiobooks_language_after_a_new_analysis(tmp_path: Path) -> None:
    """#444: the run behind the marks is rebuilt from `document.json`, which
    only the audio job writes, beside `audio.json` and from the same document. An analysis
    in another language afterwards changes neither, so the marks stay those of the audio."""
    from test_layout_language import german_pdf

    client, config = server(tmp_path)
    with client:
        doc = make(client, german_pdf(), "studie.pdf", language="en")["doc"]["id"]
        work = work_of(config, doc)
        before = {name: (work / name).read_bytes() for name in ("audio.json", "document.json")}
        assert json.loads(before["document.json"])["language"] == "en"
        page = page_of(client, doc)
        body = {"kind": "script", "document": doc, "settings": {"language": ""}}
        job = client.post("/api/v1/jobs", json=body).json()
        final = json.loads(events(client, job["id"])[-1][1])
        assert final["state"] == "done", final
        report = client.get(f"/api/v1/documents/{doc}/report").json()
        assert report["language"].startswith("de")  # the analysis is German now
        after = {name: (work / name).read_bytes() for name in before}
        assert after == before
        # the text, its marks and the Changes panel are those of the English audio (Focus
        # listening's top line names the document as the dock does, from today's analysis)
        again = page_of(client, doc)
        for start, end in (('id="text"', "</article>"), ('id="context"', "</main>")):
            assert again.split(start)[1].split(end)[0] == page.split(start)[1].split(end)[0]
        assert 'id="marks-note"' not in again
