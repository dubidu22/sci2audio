"""EPUB extraction on small made-up EPUBs and broken files (#73, the EPUB part of #5).

Each made-up EPUB is built here by `epub_maker` (D-316). Extraction records what the file
holds and decides nothing (D-63): one text line per block element with its markup as tags
(D-306, D-307), bold and italic from the HTML default rendering (D-308), pictures with their
place (`Page.order`, D-309) and path (`Picture.ref`, D-310), the table of contents as the
outline (D-311) and the package metadata (D-312). Broken files fail with a clear message,
never a traceback or a hang (D-315).
"""

from __future__ import annotations

import re
import time
import tracemalloc
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from epub_maker import XHTML_NS, Book, Item, make_epub, nav, pack, set_flag, set_method, xhtml
from hypothesis import given, settings
from hypothesis import strategies as st

from sci2audio.core import Content, OutlineEntry, Page, Picture, SourceFormat, TextLine
from sci2audio.extraction import ExtractionError, extract_epub, read_epub
from sci2audio.extraction import epub as epub_module
from sci2audio.extraction import markup as markup_module

pytestmark = pytest.mark.timeout(60)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
SAMPLE = CORPUS / "epub" / "wells-the-time-machine.epub"
PAPER = CORPUS / "papers" / "acl2023-hardt-ellipsis.pdf"


def read(data: bytes) -> Content:
    return read_epub(data, "book.epub")


def lines(page: Page) -> list[tuple[str, tuple[str, ...]]]:
    """Each line's text with the tags of its first run."""
    return [(line.text, line.runs[0].tags) for line in page.lines]


def texts(page: Page) -> list[str]:
    return [line.text for line in page.lines]


def run_of(content: Content, text: str) -> tuple[TextLine, int]:
    for page in content.pages:
        for line in page.lines:
            for index, run in enumerate(line.runs):
                if run.text == text:
                    return line, index
    raise AssertionError(f"no run {text!r}")


# ---- what is recorded --------------------------------------------------------------------


def test_each_spine_document_is_a_page_without_positions() -> None:
    content = read(make_epub("<p>One</p>", "<p>Two</p>"))
    assert content.source.format is SourceFormat.EPUB
    assert content.source.name == "book.epub"
    assert len(content.source.sha256) == 64
    assert [texts(page) for page in content.pages] == [["One"], ["Two"]]
    page = content.pages[0]
    assert (page.width, page.height, page.lines[0].box, page.lines[0].runs[0].box) == (
        None,
        None,
        None,
        None,
    )
    assert page.order == ("p1-l1",)


def test_one_line_per_block_element_with_its_tags() -> None:
    content = read(
        make_epub(
            '<section epub:type="chapter" id="ch1" role="doc-chapter"><h2>I</h2>'
            "<p>First paragraph.</p><ul><li>Item <em>one</em></li><li>Item two<ol><li>Inner"
            "</li></ol></li></ul><blockquote><p>Quoted.</p></blockquote>"
            "<table><caption>Table 1</caption><tr><th>Head</th><td>Cell</td></tr></table>"
            '<figure><figcaption>Figure 1</figcaption></figure><aside epub:type="footnote">'
            "Aside text</aside><div>Loose text<p>in a div</p>after</div></section>"
        )
    )
    chapter = ("section", "#ch1", "epub:chapter", "role:doc-chapter")
    assert lines(content.pages[0]) == [
        ("I", (*chapter, "h2")),
        ("First paragraph.", (*chapter, "p")),
        ("Item one", (*chapter, "ul", "li")),
        ("Item two", (*chapter, "ul", "li")),
        ("Inner", (*chapter, "ul", "li", "ol", "li")),
        ("Quoted.", (*chapter, "blockquote", "p")),
        ("Table 1", (*chapter, "table", "caption")),
        ("Head", (*chapter, "table", "tr", "th")),
        ("Cell", (*chapter, "table", "tr", "td")),
        ("Figure 1", (*chapter, "figure", "figcaption")),
        ("Aside text", (*chapter, "aside", "epub:footnote")),
        ("Loose text", (*chapter, "div")),
        ("in a div", (*chapter, "div", "p")),
        ("after", (*chapter, "div")),
    ]
    item = content.pages[0].lines[2]
    assert [(run.text, run.tags[-1], run.italic) for run in item.runs] == [
        ("Item ", "li", False),
        ("one", "em", True),
    ]


def test_white_space_is_folded_as_a_browser_shows_it() -> None:
    content = read(
        make_epub(
            "<p>\n\t  Two   words\n</p><p>a <b> bold </b> end</p>"
            "<p>keep\u00a0\u00a0no-break\ufeff\u2014joiner\u00adsoft</p><p>   </p>"
        )
    )
    page = content.pages[0]
    assert texts(page) == [
        "Two words",
        "a bold end",
        "keep\u00a0\u00a0no-break\ufeff\u2014joiner\u00adsoft",
    ]
    assert [run.text for run in page.lines[1].runs] == ["a ", "bold ", "end"]


def test_a_line_break_ends_the_line_and_the_next_one_continues_the_element() -> None:
    content = read(
        make_epub(
            "<p>Roses are red,<br/>violets are blue<br/><br/>and so on.</p><p><br/>Next</p>"
            "<pre>\nfor x in y:\n    print(x)\n\n</pre>"
        )
    )
    assert lines(content.pages[0]) == [
        ("Roses are red,", ("p",)),
        ("violets are blue", ("p", "br")),
        ("and so on.", ("p", "br")),
        ("Next", ("p",)),
        ("for x in y:", ("pre",)),
        ("    print(x)", ("pre", "br")),
    ]


def test_bold_and_italic_follow_the_html_default_rendering() -> None:
    content = read(
        make_epub(
            "<h1>Title</h1><p><strong>s</strong><b>b</b><i>i</i><em>e</em><cite>c</cite>"
            "<dfn>d</dfn><var>v</var><span>plain</span><b><i>both</i></b></p>"
            "<table><tr><th>th</th></tr></table><address>addr</address>"
        )
    )
    styles = [
        (run.text, run.bold, run.italic) for line in content.pages[0].lines for run in line.runs
    ]
    assert styles == [
        ("Title", True, False),
        ("s", True, False),
        ("b", True, False),
        *[(text, False, True) for text in "iecdv"],
        ("plain", False, False),
        ("both", True, True),
        ("th", True, False),
        ("addr", False, True),
    ]
    assert all(
        run.font == "" and run.size == 0 for line in content.pages[0].lines for run in line.runs
    )


def test_ids_types_roles_language_and_hidden_become_tags() -> None:
    content = read(
        make_epub(
            '<p id="p1" lang="fr" epub:type="z3998:roman bridgehead" role="doc-subtitle">'
            'Texte</p><p xml:lang="de" hidden="">Versteckt</p><p aria-hidden="true">Deco</p>'
            '<p class="fancy" style="color: red">No class</p>'
        )
    )
    assert lines(content.pages[0]) == [
        (
            "Texte",
            ("p", "#p1", "epub:z3998:roman", "epub:bridgehead", "role:doc-subtitle", "lang:fr"),
        ),
        ("Versteckt", ("p", "lang:de", "hidden")),
        ("Deco", ("p", "aria-hidden")),
        ("No class", ("p",)),
    ]


def test_links_name_the_item_they_point_at() -> None:
    content = read(
        make_epub(
            '<p>See note<a href="c2.xhtml#n1" id="ref1" epub:type="noteref">1</a>, the '
            '<a href="c2.xhtml">notes</a>, <a href="https://example.org/a b">the web</a>, '
            '<a href="c2.xhtml#missing">nothing</a>, <a href="#top">here</a>, '
            '<a href="../outside.xhtml">outside</a> and <a href="mailto:a@b.c">mail</a>.</p>'
            '<p id="top">Top</p>',
            '<h2>Notes</h2><ol><li id="n1"><p>The note. <a href="c1.xhtml#ref1">back</a></p></li>'
            '</ol><p id="end"></p><span id="last"></span>',
            '<p><a href="c2.xhtml#end">end</a> and <a href="c2.xhtml#last">last</a></p>',
        )
    )

    def link(text: str) -> str:
        line, index = run_of(content, text)
        return line.runs[index].tags[-1]

    assert link("1") == "link:p2-l2"
    assert link("notes") == "link:p2"
    assert link("the web") == "href:https://example.org/a b"
    assert link("nothing") == "href:c2.xhtml#missing"
    assert link("here") == "link:p1-l2"
    assert link("outside") == "href:../outside.xhtml"
    assert link("mail") == "href:mailto:a@b.c"
    assert link("back") == "link:p1-l1"
    # anchors after the page's last item point at the whole page
    assert link("end") == link("last") == "link:p2"
    line, index = run_of(content, "1")
    assert line.runs[index].tags == ("p", "a", "#ref1", "epub:noteref", "link:p2-l2")


def test_an_address_that_cannot_be_parsed_is_kept_as_stored() -> None:
    """`urlsplit` refuses "http://[x" (D-307: an href that does not resolve is kept)."""
    body = '<p><a href="http://[x">bad</a> <a href="c1.xhtml#ok">ok</a></p><img src="http://[y"/>'
    book = Book(
        items=[
            Item("c1", "c1.xhtml", content=xhtml(body)),
            Item("odd", "http://[z", "image/png", content=None, in_spine=False),
        ]
    )
    content = read(book.bytes())
    line, index = run_of(content, "bad")
    assert line.runs[index].tags[-1] == "href:http://[x"
    assert content.pages[0].pictures == (Picture("p1-i1", ref="http://[y"),)


def test_no_path_above_the_zip_root_is_ever_read() -> None:
    """A member stored as `../outside.xhtml` exists, but a path that leaves the root is
    never looked up: the spine item is not listed, a picture keeps its source as stored."""
    book = Book(
        items=[
            Item("c1", "c1.xhtml", content=xhtml('<p>In</p><img src="../../secret.png"/>')),
            Item("out", "../../outside.xhtml", in_spine=False),
        ],
        extra_files={"../outside.xhtml": xhtml("<p>Outside</p>")},
    )
    content = read(book.bytes())
    assert texts(content.pages[0]) == ["In"]
    assert content.pages[0].pictures == (Picture("p1-i1", ref="../../secret.png"),)
    book.items[1].in_spine = True
    with pytest.raises(ExtractionError, match="names 'out', which it does not list"):
        read(book.bytes())


def test_no_break_spaces_at_the_ends_are_kept() -> None:
    """Folding strips only ASCII white space; U+00A0 is text as stored (D-306)."""
    title = "<dc:title>\u00a0Title\u00a0</dc:title>"
    content = read(make_epub("<p> \u00a0kept\u00a0 </p>", metadata=title))
    assert texts(content.pages[0]) == ["\u00a0kept\u00a0"]
    assert content.metadata.title == "\u00a0Title\u00a0"


def test_pictures_keep_their_place_path_and_alternative_text() -> None:
    content = read(
        make_epub(
            '<h2>Maps</h2><figure><img src="images/map%201.png" alt="A map"/>'
            "<figcaption>Figure 1. The island.</figcaption></figure>"
            '<p>Inline <img src="../icon.png"/> icon</p><p>After</p>'
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<title>A drawn cover</title><image xlink:href="images/cover.jpg"/></svg>'
            '<img src="data:image/png;base64,AAAA" alt="inline data"/>'
        )
    )
    page = content.pages[0]
    assert page.pictures == (
        Picture("p1-i1", alt="A map", ref="OEBPS/images/map 1.png"),
        Picture("p1-i2", ref="icon.png"),
        Picture("p1-i3", alt="A drawn cover", ref="OEBPS/images/cover.jpg"),
        Picture("p1-i4", alt="inline data"),
    )
    # the inline picture comes after the line it stands in
    assert page.order == ("p1-l1", "p1-i1", "p1-l2", "p1-l3", "p1-i2", "p1-l4", "p1-i3", "p1-i4")
    assert texts(page) == ["Maps", "Figure 1. The island.", "Inline icon", "After"]


def test_head_scripts_and_styles_are_not_recorded_but_cdata_is() -> None:
    content = read(
        make_epub(
            "<script>var x = 1;</script><style>p {}</style><template><p>T</p></template>"
            "<p>Text<![CDATA[ and more]]></p>"
        )
    )
    assert texts(content.pages[0]) == ["Text and more"]


def test_malformed_markup_and_html_entities_are_read() -> None:
    body = (
        "<p>One &nbsp;&amp; &eacute;&#233;&#x41;<p>Two <b>bold <i>both</b> left</p></div><p>Three"
    )
    document = f"<html {XHTML_NS}><head><title>t</title></head><body>{body}</body></html>"
    book = Book(items=[Item("c1", "c1.xhtml", content=document)])
    page = read(book.bytes()).pages[0]
    assert texts(page) == ["One \u00a0& ééA", "Two bold both left", "Three"]


def test_text_in_utf_16_and_with_bad_bytes_is_read() -> None:
    utf16 = xhtml("<p>Grüße aus UTF-16</p>").replace('encoding="utf-8"', 'encoding="utf-16"')
    latin = xhtml("<p>caf\u00e9</p>").replace("utf-8", "iso-8859-1").encode("iso-8859-1")
    broken = xhtml("<p>bad byte here</p>").encode().replace(b"byte", b"b\xffte")
    book = Book(
        items=[
            Item("a", "a.xhtml", content=b"\xff\xfe" + utf16.encode("utf-16-le")),
            Item("b", "b.xhtml", content=latin),
            Item("c", "c.xhtml", content=broken),
        ]
    )
    content = read(book.bytes())
    assert [texts(page) for page in content.pages] == [
        ["Grüße aus UTF-16"],
        ["café"],
        ["bad b\ufffdte here"],
    ]


@pytest.mark.parametrize("codec", ["hex", "base64", "rot13", "zlib", "uu", "idna", "punycode"])
def test_a_declared_codec_that_is_not_for_text_reads_as_utf_8(codec: str) -> None:
    document = xhtml("<p>Plain café</p>").replace('encoding="utf-8"', f'encoding="{codec}"')
    assert texts(read(make_epub_document(document)).pages[0]) == ["Plain café"]


@pytest.mark.parametrize("codec", ["utf-16", "UTF-32", "utf-16-le"])
def test_utf_16_or_32_declared_without_a_byte_order_mark_reads_as_utf_8(codec: str) -> None:
    document = xhtml("<p>Plain café</p>").replace('encoding="utf-8"', f'encoding="{codec}"')
    assert texts(read(make_epub_document(document)).pages[0]) == ["Plain café"]


def make_epub_document(document: str) -> bytes:
    return Book(items=[Item("c1", "c1.xhtml", content=document.encode("utf-8"))]).bytes()


def test_spine_documents_of_other_kinds() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<title>Plate</title><image xlink:href="plate.png"/><text>Plate I</text></svg>'
    )
    book = Book(
        items=[
            Item("s", "plate.svg", "image/svg+xml", content=svg),
            Item("img", "plate.png", "image/png", content=b"\x89PNG\r\n\x1a\n"),
            Item("odd", "odd.dat", "application/x-odd", content=b"?", extra='fallback="fb"'),
            Item("fb", "fb.xhtml", content=xhtml("<p>Fallback</p>"), in_spine=False),
            Item("raw", "raw.dat", "application/x-raw", content=b"?"),
            Item("nl", "nl.xhtml", content=xhtml("<p>Not linear</p>")),
        ]
    )
    content = read(book.bytes())
    assert [(texts(p), p.pictures) for p in content.pages] == [
        (["Plate I"], (Picture("p1-i1", alt="Plate", ref="OEBPS/plate.png"),)),
        ([], (Picture("p2-i1", ref="OEBPS/plate.png"),)),
        (["Fallback"], ()),
        ([], ()),
        (["Not linear"], ()),
    ]


def test_deep_nesting_is_read_with_tags_for_the_outer_elements_only() -> None:
    depth = 3000
    body = "<div>" * depth + "deep" + "</div>" * depth
    line = read(make_epub(body)).pages[0].lines[0]
    assert line.text == "deep"
    assert line.runs[0].tags == ("div",) * 100  # MAX_TAGGED, as decided (D-315)


def test_many_tokens_on_many_elements_stay_small_and_fast() -> None:
    """Tags are capped per element (`MAX_TAGS`), so 100,000 `epub:type` tokens on a parent
    are not copied into each of its 2,000 children (it took 1.56 GB before the cap)."""
    tokens = " ".join(f"t{n}" for n in range(100_000))
    body = f'<div epub:type="{tokens}" role="{tokens}">' + "<span>x</span>" * 2000 + "</div>"
    data = make_epub(body)
    tracemalloc.start()
    started = time.perf_counter()
    try:
        content = read(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert time.perf_counter() - started < 10
    assert peak < 100 * 1024 * 1024
    runs = content.pages[0].lines[0].runs
    assert runs[0].tags[:3] == ("div", "epub:t0", "epub:t1")
    assert all(len(run.tags) == 200 for run in runs)  # MAX_TAGS, ancestors' included


def test_children_of_a_heavily_tagged_parent_share_one_tag_tuple() -> None:
    """#158: 197 `epub:type` tokens on a <p> with 50,000 <i> children made 50,000 copies of
    a 200-tag tuple (369 MB at 200,000 children); equal tags are now one tuple."""
    tokens = " ".join(f"t{n}" for n in range(197))
    data = make_epub(f'<p epub:type="{tokens}">' + "<i>a</i>" * 50_000 + "</p>")
    tracemalloc.start()
    try:
        content = read(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 40 * 1024 * 1024
    (run,) = content.pages[0].lines[0].runs  # one run, as before
    assert run.text == "a" * 50_000
    assert run.tags == ("p", *(f"epub:t{n}" for n in range(197)), "i")


# ---- the item limit (#158, #174, D-579) -----------------------------------------------------

ITEMS_MESSAGE = "book.epub: the EPUB is too large or damaged (more than {:,} pieces of text)"


def test_lines_pieces_and_pictures_count_across_the_whole_book(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each line, each piece of text and each picture is one item; white space between
    elements is none. Chapter 1 holds 4 (two lines of one piece), chapter 2 holds 4 (a
    line of two pieces and a picture)."""
    book = make_epub("<p>a</p>\n  <p>b</p>", '<p>c <i>d</i></p><img src="x.png" alt=""/>')
    monkeypatch.setattr(markup_module, "MAX_ITEMS", 8)
    assert [texts(page) for page in read(book).pages] == [["a", "b"], ["c d"]]
    monkeypatch.setattr(markup_module, "MAX_ITEMS", 7)
    assert outcome(book, "book.epub") == ITEMS_MESSAGE.format(7)


def test_white_space_between_inline_elements_is_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Folded white space is never kept, so it costs nothing and counts nothing."""
    monkeypatch.setattr(markup_module, "MAX_ITEMS", 6)  # "a", " ", "b", "c" and two lines
    content = read(make_epub("<p>a" + "<i> </i>" * 1000 + "b</p><p>c</p>"))
    assert texts(content.pages[0]) == ["a b", "c"]


@pytest.mark.parametrize(
    "body",
    [
        '<p><img src="x.png" alt=""/> Some text</p>',
        '<p>\n  <img src="x.png" alt=""/>\n  Some text</p>',  # pretty-printed (#328)
        '<p><span> </span><img src="x.png" alt=""/>Text</p>',
        '<p>\t<a id="q"/><img src="x.png" alt=""/>Text</p>',
    ],
)
def test_white_space_folded_away_does_not_start_a_line(body: str) -> None:
    """#328: a picture after white space that is folded away (D-306) is placed before the
    line, as a browser shows it, however the file is indented."""
    assert read(make_epub(body)).pages[0].order == ("p1-i1", "p1-l1")


@pytest.mark.parametrize(
    "body",
    [
        '<p>Some text <img src="x.png" alt=""/></p>',
        '<p>Some <b>text</b>\n  <img src="x.png" alt=""/></p>',
        '<pre>  <img src="x.png" alt=""/>code</pre>',  # kept white space in <pre>
    ],
)
def test_a_picture_after_kept_text_still_follows_its_line(body: str) -> None:
    assert read(make_epub(body)).pages[0].order == ("p1-l1", "p1-i1")


@pytest.mark.parametrize("space", ["", " ", "\n  ", "\t\n"])
def test_an_anchor_before_a_picture_names_it_however_the_file_is_indented(space: str) -> None:
    """#328: the anchor before the picture names the picture in every indentation, so a link
    to it points at the same place."""
    body = f'<span><b><a href="#q">{space}<a id="q"/><img src="x.png" alt=""/>\n d a'
    content = read(make_epub(body))
    line, index = run_of(content, "d a")
    assert "link:p1-i1" in line.runs[index].tags
    assert content.pages[0].order == ("p1-i1", "p1-l1")


@pytest.mark.parametrize(
    "element",
    [
        pytest.param('<a id="i{}"/>', id="ids"),
        pytest.param('<a href="#q"/>', id="links"),
    ],
)
def test_ids_and_links_count_as_they_are_kept_for_the_whole_book(
    monkeypatch: pytest.MonkeyPatch, element: str
) -> None:
    """An empty element with an id or a link keeps it until the book is read: 300,000 of
    them took 52 MB from 5 MB of XHTML (review R1-2 of #327)."""
    monkeypatch.setattr(markup_module, "MAX_ITEMS", 10)
    at_limit = "<p>a</p>" + "".join(element.format(n) for n in range(8))  # 2 + 8 items
    assert texts(read(make_epub(at_limit)).pages[0]) == ["a"]
    assert outcome(make_epub(at_limit + element.format(8)), "book.epub") == (
        ITEMS_MESSAGE.format(10)
    )


def test_unclosed_elements_are_bounded_by_the_same_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """300,000 unclosed <span>s held 51 MB from 1.8 MB of XHTML (review R1-3 of #327)."""
    monkeypatch.setattr(markup_module, "MAX_ITEMS", 10)
    assert texts(read(make_epub("<span>" * 5 + "a")).pages[0]) == ["a"]
    assert outcome(make_epub("<span>" * 20 + "a"), "book.epub") == ITEMS_MESSAGE.format(10)


def test_closed_elements_leave_no_name_behind() -> None:
    reader = markup_module.PageReader(1, "c1.xhtml", markup_module.Anchors())
    reader.read("".join(f"<t{n}></t{n}>" for n in range(1000)) + "<p>a</p>")
    assert not reader.open
    assert [line.text for line in reader.page().lines] == ["a"]


@pytest.mark.slow
@pytest.mark.timeout(600)  # 54 to 64 s on Linux; the macOS and Windows runners are slower
def test_a_book_of_more_items_than_the_limit_fails() -> None:
    """The reader has to read up to the limit to see it, so this is the slow twin of the
    test above at the decided limit: 500,001 paragraphs of one letter are 1,000,002 items."""
    data = make_epub("<p>a</p>" * 250_000, "<p>a</p>" * 250_001)
    tracemalloc.start()
    try:
        assert outcome(data, "book.epub") == ITEMS_MESSAGE.format(1_000_000)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1024 * 1024 * 1024


def test_the_item_limit_is_the_decided_one() -> None:
    assert markup_module.MAX_ITEMS == 1_000_000  # D-579


# ---- the markup and line limits (#329, D-777) ---------------------------------------------

MARKUP_MESSAGE = (
    "book.epub: the EPUB holds too much markup to read (more than {:,} tags, comments and"
    " declarations)"
)
LINE_MESSAGE = "book.epub: the EPUB holds a paragraph longer than {:,} characters"
TAG_MESSAGE = "book.epub: the EPUB holds a tag longer than {:,} characters"


def markup_of(text: str) -> int:
    """The markup `PageReader` counts for `text`."""
    reader = markup_module.PageReader(1, "c1.xhtml", markup_module.Anchors())
    reader.read(text)
    return reader.budget.markup


WRAPPER = markup_of(xhtml(""))  # the made-up chapter's own html, head and body tags
LONGEST_WRAPPER_TAG = max(map(len, re.findall(r"<[^>]*>", xhtml(""))))


@pytest.mark.parametrize(
    ("unit", "count"),
    [
        pytest.param("<p></p>", 1, id="element"),  # its end tag is paid for by the start
        pytest.param("<br>", 1, id="void"),
        pytest.param("<br/>", 1, id="self-closed void"),
        pytest.param("<span/>", 1, id="self-closed"),
        pytest.param("<b></b>", 1, id="inline"),
        pytest.param("</p>", 1, id="stray end tag"),
        pytest.param("<!---->", 1, id="comment"),
        pytest.param("<!DOCTYPE x>", 1, id="declaration"),
        pytest.param("<?x?>", 1, id="processing instruction"),
        pytest.param("<![CDATA[]]>", 1, id="CDATA"),
        pytest.param("<script></script>", 1, id="skipped element"),
        pytest.param("   \n\t", 0, id="white space"),
        pytest.param("text", 0, id="text"),
    ],
)
def test_each_tag_comment_and_declaration_is_counted_once(unit: str, count: int) -> None:
    assert markup_of(unit * 10) == 10 * count


@pytest.mark.parametrize("unit", ["<p></p>", "<br>", "</p>", "<!---->", "<?x?>"])
def test_markup_past_the_limit_fails(monkeypatch: pytest.MonkeyPatch, unit: str) -> None:
    """Empty elements cost time but no item: 64 MB of "<p></p>" took 105 s (#329)."""
    monkeypatch.setattr(markup_module, "MAX_MARKUP", WRAPPER + 1000)
    assert texts(read(make_epub("<p>a</p>" + unit * 999)).pages[0]) == ["a"]
    assert outcome(make_epub("<p>a</p>" + unit * 1000), "book.epub") == (
        MARKUP_MESSAGE.format(WRAPPER + 1000)
    )


def test_markup_counts_across_the_whole_book(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(markup_module, "MAX_MARKUP", 2 * WRAPPER + 1000)
    assert outcome(make_epub("<br>" * 500, "<br>" * 500), "book.epub") != (
        MARKUP_MESSAGE.format(2 * WRAPPER + 1000)
    )
    assert outcome(make_epub("<br>" * 500, "<br>" * 501), "book.epub") == (
        MARKUP_MESSAGE.format(2 * WRAPPER + 1000)
    )


def test_reading_stops_at_the_markup_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader raises at the first tag past the limit, so the rest of the file is not
    parsed: a chapter of 1,000,000 empty elements fails about as fast as one of 2,000."""
    monkeypatch.setattr(markup_module, "MAX_MARKUP", 1000)

    def fails(text: str) -> float:
        reader = markup_module.PageReader(1, "c1.xhtml", markup_module.Anchors())
        started = time.process_time()
        with pytest.raises(markup_module.TooMuchText) as raised:
            reader.read(text)
        assert (raised.value.kind, reader.budget.markup) == ("markup", 1001)
        return time.process_time() - started

    small = min(fails("<p></p>" * 2000) for _ in range(3))
    large = min(fails("<p></p>" * 1_000_000) for _ in range(3))
    assert large < 0.5 + 20 * small  # reading on to the end takes about 10 s


@pytest.mark.parametrize(
    "unit",
    [
        pytest.param("<li></li>", id="entries"),
        pytest.param("<br>", id="start tags"),
        pytest.param("</p>", id="end tags"),
        pytest.param("<!---->", id="comments"),
    ],
)
def test_the_navigation_document_counts_its_markup_too(
    monkeypatch: pytest.MonkeyPatch, unit: str
) -> None:
    """A table of contents of empty entries is bounded as the chapters are; past the limit
    the book reads without an outline (D-311), never with an error."""
    entries = '<li><a href="c1.xhtml">One</a></li>'
    reader = epub_module._NavReader("nav.xhtml")
    reader.feed(nav(entries + unit * 100))
    reader.close()
    monkeypatch.setattr(markup_module, "MAX_MARKUP", reader.budget.markup)  # 100 units: at it
    assert read(make_epub("<p>a</p>", nav_entries=entries + unit * 100)).outline
    content = read(make_epub("<p>a</p>", nav_entries=entries + unit * 101))
    assert content.outline == ()
    assert texts(content.pages[0]) == ["a"]


def test_a_line_past_the_line_limit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """One paragraph costs about 16 times its size: one of 64 MB took 1 GB (#329)."""
    monkeypatch.setattr(markup_module, "MAX_LINE", 1000)
    assert texts(read(make_epub("<p>" + "a" * 1000 + "</p><p>" + "b" * 1000)).pages[0]) == [
        "a" * 1000,
        "b" * 1000,
    ]
    assert outcome(make_epub("<p>" + "a" * 1001), "book.epub") == LINE_MESSAGE.format(1000)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("<p>" + "a" * 500 + "<b>" + "b" * 501 + "</b></p>", id="pieces add up"),
        pytest.param("<p>" + "a b " * 250 + "c</p>", id="white space inside text counts"),
        pytest.param("<p>a<br/>" + "b" * 1001 + "</p>", id="after a line break"),
        pytest.param(
            "<p>" + "a" * 500 + "<b>" + " " * 250 + "b" + " " * 250 + "</b></p>",
            id="white space around text counts",
        ),
    ],
)
def test_the_line_limit_counts_the_text_as_stored(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    monkeypatch.setattr(markup_module, "MAX_LINE", 1000)
    assert outcome(make_epub(body), "book.epub") == LINE_MESSAGE.format(1000)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("<p>" + "a" * 999 + "<i> </i>" * 1000 + "</p>", id="folded white space"),
        pytest.param("<pre>" + ("a" * 999 + "\n") * 3 + "</pre>", id="lines of pre"),
        pytest.param("<p>" + "a" * 1000 + "</p>" * 1 + "<p>" + "b" * 1000, id="two lines"),
    ],
)
def test_the_line_limit_is_per_line(monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    monkeypatch.setattr(markup_module, "MAX_LINE", 1000)
    assert isinstance(outcome(make_epub(body), "book.epub"), Content)


def test_a_paragraph_past_the_real_line_limit_fails_small() -> None:
    """At the decided limit: an 8 MB paragraph is refused before its runs are built (with
    the limit lifted it peaks at about 128 MB under tracemalloc)."""
    data = make_epub("<p>" + "word " * (8 * 1024 * 1024 // 5) + "</p>")
    tracemalloc.start()
    try:
        assert outcome(data, "book.epub") == LINE_MESSAGE.format(4_000_000)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 64 * 1024 * 1024


def test_an_svg_title_is_bounded_as_a_line_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """#329 review F3: an SVG's title becomes its pictures' alternative text; a 60 MB one
    took 935 MB and reached layout whole."""
    monkeypatch.setattr(markup_module, "MAX_LINE", 1000)

    def svg(title: str) -> bytes:
        return make_epub(f'<svg><title>{title}</title><image href="a.png"/></svg>')

    title = "a" * 593 + "<b>" + "b" * 400 + "</b>"  # 1,000 characters: a title is raw text
    (picture,) = read(svg(title)).pages[0].pictures
    assert picture.alt == title
    assert outcome(svg("a" + title), "book.epub") == LINE_MESSAGE.format(1000)


def tag(name: str, attributes: int, end: bool = False) -> str:
    """A start (or end) tag of `name` with `attributes` one-letter attributes; it holds
    len(name) + 2 * attributes + 2 characters (3 for an end tag)."""
    return f"<{'/' if end else ''}{name}" + " a" * attributes + ">"


@pytest.mark.parametrize(
    ("make", "length"),
    [
        pytest.param(lambda n: tag("p", n) + "x</p>", lambda n: 2 * n + 3, id="start tag"),
        pytest.param(lambda n: "<p>x" + tag("p", n, end=True), lambda n: 2 * n + 4, id="end tag"),
        pytest.param(
            lambda n: '<p a=">"' + " a" * n + ">x</p>", lambda n: 2 * n + 9, id="quoted >"
        ),
        pytest.param(lambda n: "<br" + " a" * n + "/>", lambda n: 2 * n + 5, id="self-closed"),
    ],
)
def test_a_tag_past_the_tag_limit_fails(
    monkeypatch: pytest.MonkeyPatch,
    make: Callable[[int], str],
    length: Callable[[int], int],
) -> None:
    """#329 review F1: the parser's tag regex cost about 150 times a tag's size (8 MB of
    attributes in one tag took 1.3 GB) before any other limit saw it."""
    n = 500  # a tag of about 1,000 characters
    monkeypatch.setattr(markup_module, "MAX_TAG", length(n))  # exactly at the limit: reads
    assert isinstance(outcome(make_epub(make(n)), "book.epub"), Content)
    monkeypatch.setattr(markup_module, "MAX_TAG", length(n) - 1)
    assert outcome(make_epub(make(n)), "book.epub") == TAG_MESSAGE.format(length(n) - 1)


def test_a_tag_in_the_navigation_document_is_bounded_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(markup_module, "MAX_TAG", 1000)
    entry = '<li><a href="c1.xhtml"' + " a" * 480 + ">One</a></li>"
    assert read(make_epub("<p>a</p>", nav_entries=entry)).outline
    content = read(make_epub("<p>a</p>", nav_entries=entry.replace(" a" * 480, " a" * 500)))
    assert content.outline == ()
    assert texts(content.pages[0]) == ["a"]


def test_a_navigation_label_is_bounded_as_a_line_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """#329 review F2: one 60 MB label took 935 MB; past the limit the book has no outline
    and its pages still read."""
    monkeypatch.setattr(markup_module, "MAX_LINE", 1000)

    def book(label: str) -> Content:
        return read(make_epub("<p>a</p>", nav_entries=f'<li><a href="c1.xhtml">{label}</a></li>'))

    assert book("a" * 500 + "<b>" + "b" * 500 + "</b>").outline
    two = '<li><a href="c1.xhtml">' + "a" * 600 + '</a></li><li><a href="c1.xhtml">' + "b" * 600
    assert len(read(make_epub("<p>a</p>", nav_entries=two + "</a></li>")).outline) == 2  # each
    content = book("a" * 500 + "<b>" + "b" * 501 + "</b>")
    assert content.outline == ()
    assert texts(content.pages[0]) == ["a"]


def test_a_tag_past_the_real_tag_limit_fails_small() -> None:
    """At the decided limit: one 4 MB tag is refused after the check's own bounded match
    (176 MB; with the check lifted, the regex over the whole tag peaks at 653 MB)."""
    data = make_epub(tag("p", 2_000_000) + "x</p>")
    tracemalloc.start()
    try:
        assert outcome(data, "book.epub") == TAG_MESSAGE.format(1_000_000)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 256 * 1024 * 1024


def test_the_markup_and_line_limits_are_the_decided_ones() -> None:
    assert markup_module.MAX_MARKUP == 2_000_000  # D-777
    assert markup_module.MAX_LINE == 4_000_000  # D-777
    assert markup_module.MAX_TAG == 1_000_000  # D-783


# ---- outline -------------------------------------------------------------------------------


def test_the_navigation_document_gives_the_outline() -> None:
    entries = (
        '<li><a href="c1.xhtml">Part One</a><ol>'
        '<li><a href="c1.xhtml#s2">  Chapter\n  Two </a></li>'
        '<li><span>No link</span><ol><li><a href="c2.xhtml#end">End of two</a></li></ol></li>'
        "</ol></li>"
        '<li><a href="nowhere.xhtml">Not in the spine</a></li>'
        "<li><a>   </a></li>"
    )
    content = read(
        make_epub(
            "<h1>Part One</h1><p>Intro</p><h2 id='s2'>Chapter Two</h2>",
            "<p>Text</p><p id='end'></p>",
            nav_entries=entries,
        )
    )
    assert content.outline == (
        OutlineEntry("Part One", 1, 1),
        OutlineEntry("Chapter Two", 2, 1, item="p1-l3"),
        OutlineEntry("No link", 2),
        OutlineEntry("End of two", 3, 2),
        OutlineEntry("Not in the spine", 1),
        OutlineEntry("", 1),
    )


def test_only_the_toc_nav_counts_and_bad_nesting_is_evened_out() -> None:
    document = xhtml(
        '<nav epub:type="landmarks"><ol><li><a href="c1.xhtml">Start</a></li></ol></nav>'
        '<nav epub:type="toc"><ol><ol><ol><li><a href="c1.xhtml">Deep first</a></li></ol></ol>'
        '</ol></nav><nav epub:type="page-list"><ol><li><a href="c1.xhtml">1</a></li></ol></nav>'
    )
    book = Book(
        items=[
            Item("c1", "c1.xhtml", content=xhtml("<p>x</p>")),
            Item("nav", "nav.xhtml", properties="nav", content=document, in_spine=False),
        ]
    )
    assert read(book.bytes()).outline == (OutlineEntry("Deep first", 1, 1),)


NCX = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head/><docTitle><text>A book</text></docTitle>
  <navMap>
    <navPoint id="a"><navLabel><text>Book One</text></navLabel><content src="c1.xhtml"/>
      <navPoint id="b"><navLabel><text> Chapter  1 </text></navLabel><content src="c1.xhtml#x"/>
      </navPoint>
    </navPoint>
    <navPoint id="c"><navLabel><text>Notes</text></navLabel><content src="c2.xhtml"/></navPoint>
  </navMap>
</ncx>
"""


def ncx_book(ncx: str | bytes | None, nav_entries: str | None = None) -> Book:
    book = Book(version="2.0", spine_toc="ncx")
    book.items = [
        Item("c1", "c1.xhtml", content=xhtml("<h1>Book One</h1><h2 id='x'>Chapter 1</h2>")),
        Item("c2", "c2.xhtml", content=xhtml("<p>Notes</p>")),
        Item("ncx", "toc.ncx", "application/x-dtbncx+xml", content=ncx, in_spine=False),
    ]
    if nav_entries is not None:
        book.items.append(
            Item("nav", "nav.xhtml", properties="nav", content=nav(nav_entries), in_spine=False)
        )
    return book


def test_an_epub_2_ncx_gives_the_outline() -> None:
    assert read(ncx_book(NCX).bytes()).outline == (
        OutlineEntry("Book One", 1, 1),
        OutlineEntry("Chapter 1", 2, 1, item="p1-l2"),
        OutlineEntry("Notes", 1, 2),
    )


def test_the_navigation_document_wins_over_the_ncx() -> None:
    book = ncx_book(NCX, nav_entries='<li><a href="c2.xhtml">From nav</a></li>')
    assert read(book.bytes()).outline == (OutlineEntry("From nav", 1, 2),)


@pytest.mark.parametrize(
    "ncx",
    [
        pytest.param(None, id="listed-but-missing"),
        pytest.param("<ncx><navMap><navPoint>", id="not-xml"),
        pytest.param(
            '<!DOCTYPE ncx [<!ENTITY a "aaaa">]><ncx><navMap/></ncx>', id="declares-entity"
        ),
        pytest.param(b"\x00\xff garbage", id="garbage"),
    ],
)
def test_a_damaged_outline_never_fails_the_file(ncx: str | bytes | None) -> None:
    content = read(ncx_book(ncx).bytes())
    assert content.outline == ()
    assert len(content.pages) == 2


@pytest.mark.parametrize(
    "entries",
    [
        '<li><a href="c1.xhtml">A</li></a>',
        '</li></a></span><li><span>B</li></span><a href="c1.xhtml">C</a>',
        '<li><a href="c1.xhtml">A</ol></nav><li><a href="c1.xhtml">B</a></li>',
    ],
)
def test_a_damaged_navigation_document_never_fails_the_file(entries: str) -> None:
    content = read(make_epub("<p>x</p>", nav_entries=entries))
    assert texts(content.pages[0]) == ["x"]


def test_a_deeply_nested_ncx_stops_at_level_fifteen() -> None:
    depth = 2000
    points = "".join(
        f'<navPoint id="n{n}"><navLabel><text>L{n}</text></navLabel><content src="c1.xhtml"/>'
        for n in range(depth)
    )
    ncx = NCX.split("<navMap>")[0] + "<navMap>" + points + "</navPoint>" * depth + "</navMap></ncx>"
    outline = read(ncx_book(ncx).bytes()).outline
    assert [entry.level for entry in outline] == list(range(1, 16))


def test_outline_levels_stop_at_fifteen() -> None:
    entries = ""
    for level in range(1, 18):
        entries += f'<li><a href="c1.xhtml">L{level}</a><ol>'
    entries += "</ol></li>" * 17
    outline = read(make_epub("<p>x</p>", nav_entries=entries)).outline
    assert [entry.level for entry in outline] == list(range(1, 16))


# ---- metadata ------------------------------------------------------------------------------


def test_metadata_as_the_package_states_it() -> None:
    metadata = """<dc:identifier id="isbn">urn:isbn:9780000000002</dc:identifier>
    <dc:identifier id="uid">urn:uuid:12345678-1234-4234-8234-123456789012</dc:identifier>
    <dc:title id="t">  The   Title </dc:title><dc:title>Second title</dc:title>
    <dc:creator id="a1">Ada Lovelace</dc:creator>
    <meta refines="#a1" property="role" scheme="marc:relators">aut</meta>
    <dc:creator id="a2">Ann Illustrator</dc:creator>
    <meta refines="#a2" property="role" scheme="marc:relators">ill</meta>
    <dc:creator opf:role="aut">Charles Babbage</dc:creator>
    <dc:creator opf:role="trl">Tom Translator</dc:creator>
    <dc:creator>No Role</dc:creator>
    <dc:date>1843-09-01T00:00:00Z</dc:date>
    <dc:language>en-GB</dc:language><dc:language>fr</dc:language>"""
    meta = read(make_epub("<p>x</p>", metadata=metadata)).metadata
    assert meta.title == "The Title"
    assert meta.authors == ("Ada Lovelace", "Charles Babbage", "No Role")
    assert meta.date == "1843-09-01"
    assert meta.identifier == "urn:uuid:12345678-1234-4234-8234-123456789012"
    assert meta.language == "en-GB"


@pytest.mark.parametrize(
    ("date", "kept"), [("1895", "1895"), ("1895-05", "1895-05"), ("May 1895", "")]
)
def test_the_date_keeps_its_date_part(date: str, kept: str) -> None:
    metadata = f"<dc:title>T</dc:title><dc:date>{date}</dc:date>"
    assert read(make_epub("<p>x</p>", metadata=metadata)).metadata.date == kept


def test_a_package_without_metadata_gives_empty_metadata() -> None:
    meta = read(make_epub("<p>x</p>", metadata="")).metadata
    assert (meta.title, meta.authors, meta.date, meta.identifier, meta.language) == (
        "",
        (),
        "",
        "",
        "",
    )


# ---- broken files (#5, D-315) --------------------------------------------------------------

GOOD = make_epub("<p>Readable</p>")


def drm_book(extra: dict[str, str | bytes]) -> bytes:
    return make_epub("<p>Locked</p>", extra_files=extra)


def encryption(algorithm: str) -> str:
    return (
        '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
        'xmlns:enc="http://www.w3.org/2001/04/xmlenc#"><enc:EncryptedData>'
        f'<enc:EncryptionMethod Algorithm="{algorithm}"/><enc:CipherData>'
        '<enc:CipherReference URI="OEBPS/c1.xhtml"/></enc:CipherData></enc:EncryptedData>'
        "</encryption>"
    )


BILLION_LAUGHS = (
    '<?xml version="1.0"?><!DOCTYPE package [<!ENTITY a "aaaaaaaaaa">'
    '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
    '<package xmlns="http://www.idpf.org/2007/opf"><metadata>&c;</metadata></package>'
)
EXTERNAL_ENTITY = (
    '<?xml version="1.0"?><!DOCTYPE package [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
    '<package xmlns="http://www.idpf.org/2007/opf"><metadata>&x;</metadata></package>'
)


def without(path: str) -> bytes:
    files = Book(items=[Item("c1", "c1.xhtml", content=xhtml("<p>x</p>"))]).files()
    del files[path]
    return pack(files)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(b"", "the file is empty", id="empty"),
        pytest.param(b"Just some words, no zip at all.", "not an EPUB", id="plain-text"),
        pytest.param(PAPER.read_bytes(), "not an EPUB", id="pdf-named-epub"),
        pytest.param(SAMPLE.read_bytes()[: SAMPLE.stat().st_size // 2], "not an EPUB", id="half"),
        pytest.param(GOOD[:200], "not an EPUB", id="truncated-start"),
        pytest.param(set_flag(GOOD, "OEBPS/c1.xhtml", 0), "password-protected", id="password"),
        pytest.param(set_method(GOOD, "OEBPS/c1.xhtml", 7), "not an EPUB", id="compression"),
        pytest.param(  # WinZip AES: method 99 with the encryption flag
            set_flag(set_method(GOOD, "OEBPS/c1.xhtml", 99), "OEBPS/c1.xhtml", 0),
            "password-protected",
            id="aes",
        ),
        pytest.param(without("META-INF/container.xml"), "no container file", id="no-container"),
        pytest.param(
            without("OEBPS/content.opf"),
            "package file OEBPS/content.opf is missing",
            id="no-package",
        ),
        pytest.param(
            Book(container="<container><rootfiles/></container>").bytes(),
            "names no package file",
            id="container-names-nothing",
        ),
        pytest.param(
            Book(container="<container").bytes(),
            "container file is damaged",
            id="container-not-xml",
        ),
        pytest.param(
            Book(opf="<package><spine>").bytes(), "package file is damaged", id="package-not-xml"
        ),
        pytest.param(
            Book(opf=BILLION_LAUGHS).bytes(), "package file is damaged", id="entity-expansion"
        ),
        pytest.param(
            Book(opf=EXTERNAL_ENTITY).bytes(), "package file is damaged", id="external-entity"
        ),
        pytest.param(Book().bytes(), "has no chapters", id="empty-spine"),
        pytest.param(
            Book(items=[Item("c1", "c1.xhtml", content=None)]).bytes(),
            r"damaged: OEBPS/c1\.xhtml is missing",
            id="chapter-missing",
        ),
        pytest.param(
            Book(
                opf=Book(items=[Item("c1", "c1.xhtml")])
                .package()
                .replace('idref="c1"', 'idref="nope"')
            ).bytes(),
            "reading order names 'nope'",
            id="spine-names-unlisted",
        ),
        pytest.param(drm_book({"META-INF/rights.xml": "<rights/>"}), "DRM", id="adobe-rights"),
        pytest.param(drm_book({"META-INF/sinf.xml": "<sinf/>"}), "DRM", id="apple-fairplay"),
        pytest.param(drm_book({"META-INF/license.lcpl": "{}"}), "DRM", id="readium-lcp"),
        pytest.param(
            drm_book(
                {
                    "META-INF/encryption.xml": encryption(
                        "http://www.w3.org/2001/04/xmlenc#aes128-cbc"
                    )
                }
            ),
            "DRM",
            id="encrypted-content",
        ),
        pytest.param(
            drm_book({"META-INF/encryption.xml": "<encryption"}),
            "encryption file is damaged",
            id="encryption-not-xml",
        ),
    ],
)
def test_broken_files_fail_with_a_clear_message(data: bytes, message: str) -> None:
    with pytest.raises(ExtractionError, match=message) as error:
        read_epub(data, "broken.epub")
    assert str(error.value).startswith("broken.epub: ")


@pytest.mark.parametrize(
    "algorithm", ["http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"]
)
def test_obfuscated_fonts_alone_are_not_drm(algorithm: str) -> None:
    content = read(drm_book({"META-INF/encryption.xml": encryption(algorithm)}))
    assert texts(content.pages[0]) == ["Locked"]


@pytest.mark.parametrize(
    ("limit", "value"),
    [("MAX_MEMBER", 1000), ("MAX_TOTAL", 1000), ("MAX_SPINE", 2)],
)
def test_too_large_files_are_refused(
    monkeypatch: pytest.MonkeyPatch, limit: str, value: int
) -> None:
    monkeypatch.setattr(epub_module, limit, value)
    data = make_epub("<p>" + "x" * 2000 + "</p>", "<p>b</p>", "<p>c</p>")
    with pytest.raises(ExtractionError, match="too large or damaged"):
        read(data)


def test_the_limits_are_the_decided_ones() -> None:
    """D-313 and D-315; the other tests lower them to keep the files small."""
    assert epub_module.MAX_MEMBER == 64 * 1024 * 1024
    assert epub_module.MAX_TOTAL == 512 * 1024 * 1024
    assert epub_module.MAX_SPINE == 10_000
    assert epub_module.MAX_COVER == 20 * 1024 * 1024
    assert markup_module.MAX_TAGGED == 100  # shared with Markdown since #74 (D-340)
    assert markup_module.MAX_TAGS == 200
    assert epub_module.MAX_OUTLINE_LEVEL == 15


def test_a_zip_bomb_stops_at_the_real_limit() -> None:
    """65 MB of spaces pack into about 64 KB; reading stops at 64 MB, not trusting the size
    the zip states."""
    data = Book(items=[Item("c1", "c1.xhtml", content=b" " * (65 * 1024 * 1024))]).bytes()
    assert len(data) < 200_000
    with pytest.raises(ExtractionError, match="too large or damaged"):
        read(data)


def test_a_missing_file_fails_with_a_clear_message(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match=r"^gone\.epub: cannot be opened"):
        extract_epub(tmp_path / "gone.epub")


def test_extraction_is_deterministic() -> None:
    assert read(SAMPLE.read_bytes()) == read(SAMPLE.read_bytes())


# ---- properties ----------------------------------------------------------------------------


def outcome(data: bytes, name: str) -> Content | str:
    """The content, or the message of the ExtractionError (any other exception fails)."""
    try:
        return read_epub(data, name)
    except ExtractionError as error:
        return str(error)


@settings(deadline=None)
@given(st.binary(max_size=2000))
def test_any_bytes_give_content_or_a_clear_error(data: bytes) -> None:
    result = outcome(data, "random.epub")
    assert isinstance(result, Content) or result.startswith("random.epub: ")


SMALL = make_epub(
    "<h1 id='a'>One</h1><p>Text <a href='c2.xhtml#n'>1</a><br/>more</p><img src='i.png' alt='x'/>",
    "<ol><li id='n'>Note</li></ol>",
    nav_entries='<li><a href="c1.xhtml#a">One</a></li>',
)


@settings(deadline=None)
@given(st.lists(st.tuples(st.integers(0, len(SMALL) - 1), st.integers(0, 255)), max_size=20))
def test_a_damaged_epub_gives_content_or_a_clear_error(changes: list[tuple[int, int]]) -> None:
    data = bytearray(SMALL)
    for position, value in changes:
        data[position] = value
    result = outcome(bytes(data), "damaged.epub")
    assert isinstance(result, Content) or result.startswith("damaged.epub: ")


TAGS = ["p", "div", "span", "em", "b", "li", "ol", "h2", "br", "a", "img", "table", "td", "svg"]
pieces = st.one_of(
    st.text(alphabet=" \t\n\r\fab\u00a0é<>&;", max_size=8),
    st.sampled_from(TAGS).map(lambda tag: f"<{tag}>"),
    st.sampled_from(TAGS).map(lambda tag: f"</{tag}>"),
    st.sampled_from(TAGS).map(lambda tag: f"<{tag}/>"),
    st.sampled_from(
        [
            '<p id="x">',
            '<a href="#x">',
            '<a href="c1.xhtml#x">',
            '<a href="http://[x">',
            '<img src="a.png" alt=" "/>',
            '<img src="http://[y"/>',
            "<!-- c -->",
        ]
    ),
)


@settings(deadline=None)
@given(st.lists(pieces, max_size=40).map("".join))
def test_any_markup_gives_folded_lines_with_unique_ids(body: str) -> None:
    content = read(make_epub(body))
    page = content.pages[0]
    for line in page.lines:
        assert line.text == line.text.strip(" \t\n\r\f")
        assert "  " not in line.text
        assert not set(line.text) & set("\t\n\r\f")
        assert all(run.text for run in line.runs)
    ids = [item.id for item in (*page.lines, *page.pictures)]
    assert sorted(page.order) == sorted(ids)
    assert len(set(ids)) == len(ids)


@settings(deadline=None)
@given(st.lists(pieces, max_size=40).map("".join))
def test_with_low_limits_any_markup_reads_or_names_a_limit(body: str) -> None:
    """Items, markup and line length each stop a book with their own message (#329)."""
    limits = (
        ITEMS_MESSAGE.format(8),
        MARKUP_MESSAGE.format(WRAPPER + 6),
        LINE_MESSAGE.format(5),
        TAG_MESSAGE.format(LONGEST_WRAPPER_TAG + 3),
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(markup_module, "MAX_ITEMS", 8)
        patch.setattr(markup_module, "MAX_MARKUP", WRAPPER + 6)
        patch.setattr(markup_module, "MAX_LINE", 5)
        patch.setattr(markup_module, "MAX_TAG", LONGEST_WRAPPER_TAG + 3)
        result = outcome(make_epub(body), "book.epub")
    assert isinstance(result, Content) or result in limits, result


INDENTS = st.text(alphabet=" \t\n\r\f", min_size=1, max_size=3)
solid = st.one_of(  # pieces without white space, so white space can go between any two
    st.sampled_from(["ab", "é", "c"]),
    st.sampled_from([tag for tag in TAGS if tag != "svg"]).map(lambda tag: f"<{tag}>"),
    st.sampled_from(TAGS).map(lambda tag: f"</{tag}>"),
    st.sampled_from(TAGS).map(lambda tag: f"<{tag}/>"),
    st.sampled_from(['<p id="x">', '<a id="y"/>', '<img src="a.png" alt=""/>', "<img/>"]),
)


@settings(deadline=None)
@given(st.lists(st.tuples(solid, st.one_of(st.just(""), INDENTS)), max_size=30))
def test_indenting_the_markup_never_moves_a_picture_or_an_anchor(
    pieces_and_spaces: list[tuple[str, str]],
) -> None:
    """#328: white space between elements that is folded away does not change `Page.order`
    or where an id points, as a browser shows the indented file the same way."""

    def placed(text: str) -> tuple[tuple[str, ...], dict[tuple[str, str], str]]:
        anchors = markup_module.Anchors()
        reader = markup_module.PageReader(1, "c1.xhtml", anchors)
        reader.read(text)
        return reader.page().order, anchors.items

    plain = "".join(piece for piece, _ in pieces_and_spaces)
    indented = "".join(piece + space for piece, space in pieces_and_spaces)
    assert placed(indented) == placed(plain)


@settings(deadline=None)
@given(st.lists(pieces, max_size=40).map("".join))
def test_any_navigation_markup_gives_content(entries: str) -> None:
    """A damaged table of contents never fails the file (D-311)."""
    content = read(make_epub("<p>x</p>", nav_entries=entries))
    assert texts(content.pages[0]) == ["x"]
    assert all(entry.page in (None, 1) for entry in content.outline)


def _sample_files() -> dict[str, bytes]:
    with zipfile.ZipFile(SAMPLE) as archive:
        return {name: archive.read(name) for name in archive.namelist() if name != "mimetype"}


SAMPLE_FILES = _sample_files()
CHAPTERS = sorted(name for name in SAMPLE_FILES if name.endswith(".xhtml"))


@settings(deadline=None, max_examples=25)
@given(
    st.sampled_from([*CHAPTERS, "epub/content.opf", "epub/toc.xhtml", "META-INF/container.xml"]),
    st.lists(
        st.tuples(st.integers(0, 40_000), st.text(alphabet="<>&;/=\"' ab#\x00�", max_size=6)),
        min_size=1,
        max_size=10,
    ),
)
def test_the_sample_with_damaged_markup_gives_content_or_a_clear_error(
    member: str, inserts: list[tuple[int, str]]
) -> None:
    text = SAMPLE_FILES[member].decode("utf-8")
    for position, piece in sorted(inserts, reverse=True):
        at = min(position, len(text))
        text = text[:at] + piece + text[at:]
    files = dict(SAMPLE_FILES, **{member: text.encode("utf-8")})
    result = outcome(pack(files), "sample.epub")
    assert isinstance(result, Content) or result.startswith("sample.epub: ")
