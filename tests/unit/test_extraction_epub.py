"""EPUB extraction on small made-up EPUBs and broken files (#73, the EPUB part of #5).

Each made-up EPUB is built here by `epub_maker` (D-316). Extraction records what the file
holds and decides nothing (D-63): one text line per block element with its markup as tags
(D-306, D-307), bold and italic from the HTML default rendering (D-308), pictures with their
place (`Page.order`, D-309) and path (`Picture.ref`, D-310), the table of contents as the
outline (D-311) and the package metadata (D-312). Broken files fail with a clear message,
never a traceback or a hang (D-315).
"""

from __future__ import annotations

import time
import tracemalloc
import zipfile
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
