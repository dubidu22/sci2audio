"""Markdown extraction on small made-up files and broken files (#74, the Markdown part of #5).

The Markdown is rendered to HTML and read by the EPUB page reader (D-340), so it gets the
same lines, tags, styles, pictures and order as an EPUB chapter (D-306 to D-310). The dialect
(D-339), the roles of notes and maths (D-341), front matter (D-342), the empty outline (D-343)
and the nesting limit that fails rather than loses text (D-351) are pinned here.
"""

from __future__ import annotations

import re
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import Content, Metadata, Picture, SourceFormat, TextLine
from sci2audio.extraction import ExtractionError, extract_markdown, read_markdown
from sci2audio.extraction import markdown as markdown_module
from sci2audio.extraction import markup as markup_module

pytestmark = pytest.mark.timeout(60)


def read(text: str | bytes) -> Content:
    return read_markdown(text.encode() if isinstance(text, str) else text, "notes.md")


def outcome(text: str | bytes) -> Content | str:
    """The content, or the message of the ExtractionError (any other error fails the test)."""
    try:
        return read(text)
    except ExtractionError as error:
        return str(error)


def lines(content: Content) -> list[tuple[str, tuple[str, ...]]]:
    """Each line's text with the tags of its first run."""
    return [(line.text, line.runs[0].tags) for line in content.pages[0].lines]


def texts(content: Content) -> list[str]:
    return [line.text for line in content.pages[0].lines]


def runs(line: TextLine) -> list[tuple[str, tuple[str, ...], bool, bool]]:
    return [(run.text, run.tags, run.bold, run.italic) for run in line.runs]


# ---- blocks and inline markup (D-339, D-340) ---------------------------------------------


def test_headings_keep_their_level_and_are_bold() -> None:
    content = read("# One\n\n## Two\n\n###### Six\n\nSetext\n======\n")
    assert lines(content) == [
        ("One", ("h1",)),
        ("Two", ("h2",)),
        ("Six", ("h6",)),
        ("Setext", ("h1",)),
    ]
    assert all(line.runs[0].bold for line in content.pages[0].lines)


def test_one_page_without_positions_and_an_empty_outline() -> None:
    content = read("# A\n\nText.\n")
    assert len(content.pages) == 1
    page = content.pages[0]
    assert (page.number, page.width, page.height) == (1, None, None)
    assert page.order == ("p1-l1", "p1-l2")
    assert content.outline == ()  # D-343: the headings are lines
    assert (content.source.name, content.source.format) == ("notes.md", SourceFormat.MARKDOWN)
    assert (content.source.encoding, content.source.encoding_guessed) == ("utf-8", False)


def test_soft_breaks_fold_and_hard_breaks_end_a_line() -> None:
    content = read("one\ntwo  \nthree\\\nfour\n")
    assert lines(content) == [("one two", ("p",)), ("three", ("p", "br")), ("four", ("p", "br"))]


def test_emphasis_strong_code_and_strikethrough_are_runs() -> None:
    (line,) = read("a *b* **c** `d` ~~e~~ _f_\n").pages[0].lines
    assert runs(line) == [
        ("a ", ("p",), False, False),
        ("b", ("p", "em"), False, True),
        (" ", ("p",), False, False),
        ("c", ("p", "strong"), True, False),
        (" ", ("p",), False, False),
        ("d", ("p", "code"), False, False),
        (" ", ("p",), False, False),
        ("e", ("p", "s"), False, False),
        (" ", ("p",), False, False),
        ("f", ("p", "em"), False, True),
    ]


def test_code_blocks_keep_their_white_space_one_line_per_printed_line() -> None:
    content = read("```python\ndef f():\n    return 1\n```\n\n    indented  code\n")
    assert lines(content) == [
        ("def f():", ("pre", "code")),
        ("    return 1", ("pre", "code", "br")),
        ("indented  code", ("pre", "code")),
    ]


def test_tight_and_loose_lists_as_html_renders_them() -> None:
    tight = read("- a\n- b\n  1. c\n")
    assert lines(tight) == [
        ("a", ("ul", "li")),
        ("b", ("ul", "li")),
        ("c", ("ul", "li", "ol", "li")),
    ]
    loose = read("- a\n\n- b\n")
    assert lines(loose) == [("a", ("ul", "li", "p")), ("b", ("ul", "li", "p"))]


def test_block_quotes_nest() -> None:
    assert lines(read("> a\n>\n> > b\n")) == [
        ("a", ("blockquote", "p")),
        ("b", ("blockquote", "blockquote", "p")),
    ]


def test_each_table_cell_is_a_line_and_header_cells_are_bold() -> None:
    content = read("| H1 | H2 |\n|---|--:|\n| a | b |\n")
    assert lines(content) == [
        ("H1", ("table", "thead", "tr", "th")),
        ("H2", ("table", "thead", "tr", "th")),
        ("a", ("table", "tbody", "tr", "td")),
        ("b", ("table", "tbody", "tr", "td")),
    ]
    assert [line.runs[0].bold for line in content.pages[0].lines] == [True, True, False, False]


def test_pictures_keep_alt_text_path_and_place() -> None:
    content = read(
        'Before.\n\n![A chart](figs/./chart.png "title")\n\nText ![](icon.png) inline.\n\n'
        "![data](data:image/png;base64,AAAA) ![web](https://example.org/x.png)\n"
    )
    page = content.pages[0]
    assert page.pictures == (
        Picture("p1-i1", alt="A chart", ref="figs/chart.png"),
        Picture("p1-i2", ref="icon.png"),
        Picture("p1-i3", alt="data"),
        Picture("p1-i4", alt="web", ref="https://example.org/x.png"),
    )
    # a picture inside a line of text stands after that line
    assert page.order == ("p1-l1", "p1-i1", "p1-l2", "p1-i2", "p1-i3", "p1-i4")
    assert texts(content) == ["Before.", "Text inline."]


@pytest.mark.parametrize(
    ("markdown", "alt"),
    [
        pytest.param("![next <b>bold</b>](u.png)", "next bold", id="inline HTML (AC-1)"),
        pytest.param("![line\\\nnext](u.png)", "line next", id="hard break (AC-2)"),
        pytest.param("![line  \nnext](u.png)", "line next", id="hard break by spaces"),
        pytest.param("![line\nnext](u.png)", "line next", id="soft break"),
        pytest.param("![a \\* b](u.png)", "a * b", id="escape (AC-3)"),
        pytest.param("![the `x` var](u.png)", "the x var", id="code span (AC-3)"),
        pytest.param("![&amp; and &copy;](u.png)", "& and ©", id="entities (AC-3)"),
        pytest.param("![*em* and **strong**](u.png)", "em and strong", id="emphasis"),
        pytest.param("![a ![b](c.png) d](u.png)", "a b d", id="a nested image"),
        pytest.param('![<img src="x.png" alt="y">](u.png)', "", id="only a tag"),
    ],
)
def test_alt_text_is_the_text_only(markdown: str, alt: str) -> None:
    """#602: markdown-it-py 4.3 keeps inline HTML and line breaks in an image's alt text;
    the figure notice would read the tags."""
    (picture,) = read(markdown).pages[0].pictures
    assert picture.alt == alt


def test_links_inside_the_file_resolve_and_others_keep_their_address() -> None:
    content = read(
        '<p id="top">Top</p>\n\n[up](#top) [web](https://example.org/a?b=1) <https://x.org>'
        " [other](other.md#x) [nowhere](#missing) https://bare.org\n"
    )
    line = content.pages[0].lines[1]
    tags = [(run.text, run.tags[-1]) for run in line.runs if "a" in run.tags]
    assert tags == [
        ("up", "link:p1-l1"),
        ("web", "href:https://example.org/a?b=1"),
        ("https://x.org", "href:https://x.org"),
        ("other", "href:other.md#x"),
        ("nowhere", "href:#missing"),
    ]
    assert line.text.endswith(" https://bare.org")  # no automatic links (D-339)


def test_raw_html_is_read_as_html() -> None:
    content = read(
        'H<sub>2</sub>O <!-- not read -->and <span lang="de">Haus</span>\n\n'
        '<div class="x">\n<p>Block HTML</p>\n</div>\n\n<script>var x = 1;</script>\n\n'
        "<style>p {}</style>\n\nEnd\n"
    )
    assert texts(content) == ["H2O and Haus", "Block HTML", "End"]
    first = content.pages[0].lines[0]
    assert ("2", ("p", "sub"), False, False) in runs(first)
    assert ("Haus", ("p", "span", "lang:de"), False, False) in runs(first)


def test_entities_are_decoded_and_quotes_stay_as_typed() -> None:
    assert texts(read("AT&amp;T &copy; \"quoted\" -- 'single' ...\n")) == [
        "AT&T © \"quoted\" -- 'single' ..."
    ]


def test_escaped_characters_are_the_characters() -> None:
    assert texts(read("\\*not emphasis\\* and \\$5\n")) == ["*not emphasis* and $5"]


# ---- notes and maths (D-341) -------------------------------------------------------------


def test_notes_have_the_roles_an_epub_uses_and_marks_link_to_them() -> None:
    content = read(
        "Text.[^a] More[^b] and again[^a].\n\nInline^[An inline note.]\n\n"
        "[^b]: Second, **bold**.\n[^a]: First.\n"
    )
    page = content.pages[0]
    body, inline, *notes = page.lines
    marks = [(run.text, run.tags) for run in body.runs if "role:doc-noteref" in run.tags]
    assert marks == [
        ("1", ("p", "sup", "a", "#fnref1", "role:doc-noteref", f"link:{notes[0].id}")),
        ("2", ("p", "sup", "a", "#fnref2", "role:doc-noteref", f"link:{notes[1].id}")),
        ("1", ("p", "sup", "a", "#fnref1:1", "role:doc-noteref", f"link:{notes[0].id}")),
    ]
    assert body.text == "Text.1 More2 and again1."
    assert inline.text == "Inline3"
    assert [(note.text, note.runs[0].tags) for note in notes] == [
        ("First.", ("section", "role:doc-endnotes", "ol", "li", "#fn1", "role:doc-endnote", "p")),
        (
            "Second, bold.",
            ("section", "role:doc-endnotes", "ol", "li", "#fn2", "role:doc-endnote", "p"),
        ),
        (
            "An inline note.",
            ("section", "role:doc-endnotes", "ol", "li", "#fn3", "role:doc-endnote", "p"),
        ),
    ]
    assert "↩" not in "".join(texts(content))  # no back-link arrow: it is not in the file


def test_a_mark_without_a_note_stays_text() -> None:
    assert texts(read("Text[^none].\n")) == ["Text[^none]."]


# markdown-it leaves out some text of the file on purpose (the uncited note and the unclosed
# comment as GitHub and a browser do); pinned so it is decided, not accidental (#169).


def test_a_note_nobody_cites_is_not_read() -> None:
    assert texts(read("Body.\n\n[^1]: A note nobody cites.\n")) == ["Body."]


def test_of_two_notes_with_one_label_only_the_last_is_read() -> None:
    content = read("Body.[^a]\n\n[^a]: First.\n\n[^a]: Second.\n")
    assert texts(content) == ["Body.1", "Second."]


def test_an_unclosed_html_comment_hides_the_rest_of_the_file() -> None:
    assert outcome("<!-- hello\n\nworld\n") == "notes.md: the file holds no text"
    assert texts(read("Before.\n\n<!-- hello\n\nworld\n")) == ["Before."]


def test_the_unclosed_comment_is_dropped_before_the_html_parser_sees_it() -> None:
    """Python's HTML parser reads an unclosed comment as text in some patch versions
    (3.12.10), so the renderer leaves it out itself; closed comments pass through."""
    render = markdown_module._parser().render
    assert render("Before.\n\n<!-- hello\n\nworld\n") == "<p>Before.</p>\n"
    assert render("  <!-- a\nb -->\n\nText\n") == "  <!-- a\nb -->\n<p>Text</p>\n"


def test_an_indented_unclosed_comment_is_dropped_as_well() -> None:
    assert markdown_module._parser().render("Before.\n\n  <!-- hello\n\nworld\n") == (
        "<p>Before.</p>\n"
    )


def test_double_dollars_inside_a_paragraph_are_two_single_maths_marks() -> None:
    """markdown-it's `double_inline` is off: `$$a$$` in a paragraph is `$` + `$a$` + `$`,
    so the renderer's rule for `math_inline_double` is never reached (#632)."""
    (line,) = read("Text $$a$$ more.\n").pages[0].lines
    assert line.text == "Text $a$ more."
    assert [run.text for run in line.runs if "role:math" in run.tags] == ["a"]


def test_maths_is_tagged_and_keeps_the_tex_as_typed() -> None:
    content = read("Let $a_1 * b^2$ hold.\n\n$$\n\\frac{1}{2} < x\n$$\n\n$$y = 1$$ (eq1)\n")
    first = content.pages[0].lines[0]
    assert ("a_1 * b^2", ("p", "span", "role:math"), False, False) in runs(first)
    assert lines(content)[1:] == [
        ("\\frac{1}{2} < x", ("div", "role:math")),
        ("y = 1 (eq1)", ("div", "role:math")),
    ]
    assert first.text == "Let a_1 * b^2 hold."


@pytest.mark.parametrize(
    "text",
    [
        "Prices: $5 and $10.",
        "Between $ 1 and 2 $ here.",
        "Costs $x$5 each.",
        "A lone $ sign.",
    ],
)
def test_dollars_that_are_not_maths_stay_text(text: str) -> None:
    (line,) = read(text + "\n").pages[0].lines
    assert line.text == text
    assert not any("role:math" in run.tags for run in line.runs)


def test_display_maths_ends_at_a_blank_line() -> None:
    """A stray `$$` must not swallow the paragraphs after it into a formula: a blank line
    ends display maths, so these stay text (D-339)."""
    content = read("$$\nA paragraph.\n\nAnother.\n$$\n")
    assert lines(content) == [("$$ A paragraph.", ("p",)), ("Another. $$", ("p",))]


# ---- front matter (D-342) ----------------------------------------------------------------


def test_front_matter_fills_metadata_and_is_not_read() -> None:
    content = read(
        "---\ntitle: 'A Title: With Colon'\nauthor:\n  - name: A. One\n    affiliation: X\n"
        "  - B. Two\ndate: 2024-03-01T10:00:00Z\nlang: de-CH\ndoi: 10.1/x\nisbn: 978\n"
        "tags: [a, b]\n---\n\n# Heading\n"
    )
    assert content.metadata == Metadata(
        title="A Title: With Colon",
        authors=("A. One", "B. Two"),
        date="2024-03-01",
        identifier="10.1/x",
        language="de-CH",
    )
    assert texts(content) == ["Heading"]


@pytest.mark.parametrize(
    ("front", "expected"),
    [
        ('authors: ["A", "B"]', Metadata(authors=("A", "B"))),
        ("author: Solo Author", Metadata(authors=("Solo Author",))),
        ("author:\n  name: Mapped Author", Metadata(authors=("Mapped Author",))),
        (
            "title: >\n  Folded\n  title\nlanguage: en",
            Metadata(title="Folded title", language="en"),
        ),
        ("title: |\n  Literal\ndate: March 2024", Metadata(title="Literal")),
        ("identifier: urn:x\nisbn: 978", Metadata(identifier="urn:x")),
        ("isbn: 978-3", Metadata(identifier="978-3")),
        ("identifier: urn:y\ndoi: 10.2/y", Metadata(identifier="10.2/y")),  # a DOI first
        (
            "author:\n  - affiliation: Lab\n    name: Second Field",
            Metadata(authors=("Second Field",)),
        ),
        (
            "# a comment\n\ntitle: T # not a comment in our reader",
            Metadata(title="T # not a comment in our reader"),
        ),
        ("::: nonsense\n- - -\n  : :\n[unclosed", Metadata()),
    ],
)
def test_front_matter_forms(front: str, expected: Metadata) -> None:
    assert read(f"---\n{front}\n---\nBody\n").metadata == expected


def front(text: str) -> Metadata:
    return read(f"---\n{text}\n---\nBody\n").metadata


@pytest.mark.parametrize("marker", [">", "|", ">-", "|-", ">+", "|+"])
def test_every_block_marker_starts_a_block(marker: str) -> None:
    """#632: `>-` and `|+` are block markers as well; read as a value, one would be the title."""
    assert front(f"title: {marker}\n  Folded\n  title\nlang: en") == Metadata(
        title="Folded title", language="en"
    )


def test_a_block_holds_its_blank_lines_and_ends_with_the_front_matter() -> None:
    assert front("title: >\n  One\n\n  Two\nlang: en") == Metadata(title="One Two", language="en")
    assert front("lang: en\ntitle: >\n  Last\n  lines") == Metadata(
        title="Last lines", language="en"
    )
    assert front("title: |\n\tTabbed\n\tlines\nlang: en") == Metadata(
        title="Tabbed lines", language="en"
    )


def test_keys_and_name_fields_are_read_in_any_case() -> None:
    assert front("Title: T\nAUTHOR:\n  - Name: A. One\n  - B. Two\nLang: de") == Metadata(
        title="T", authors=("A. One", "B. Two"), language="de"
    )
    assert front("author:\n  Name: Mapped Author") == Metadata(authors=("Mapped Author",))
    assert front("author:\n  - name: 'Quoted One'\n  - Name: \"Quoted Two\"") == Metadata(
        authors=("Quoted One", "Quoted Two")
    )
    assert front("author:\n  name: 'Quoted Mapped'") == Metadata(authors=("Quoted Mapped",))


def test_a_list_may_start_at_the_margin_and_a_comment_does_not_end_it() -> None:
    assert front("author:\n- A. One\n- name: B. Two\n# note: skipped\n- C. Three") == Metadata(
        authors=("A. One", "B. Two", "C. Three")
    )
    assert front("author:\n# note: skipped\n  - A. One") == Metadata(authors=("A. One",))


def test_only_other_fields_of_a_list_entry_are_skipped() -> None:
    """A field is a plain identifier and a colon; "Dr. A: B" or "1x: y" is a name."""
    entries = [
        "Single",
        "Dr. A: B",
        "1x: kept",
        "with-dash: skipped",
        "_under: skipped",
        "Affiliation: skipped",
        "affil : skipped",
        "Name: Cased Name",
    ]
    authors = ("Single", "Dr. A: B", "1x: kept", "Cased Name")
    assert front("author:\n" + "".join(f"  - {entry}\n" for entry in entries)) == Metadata(
        authors=authors
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('"', '"'),
        ("'", "'"),
        ('""', ""),
        ("'a'", "a"),
        ('"a b"', "a b"),
        ("xyx", "xyx"),
        ("'a\"", "'a\""),
        ("[a]", "a"),
        ("[a", "[a"),
        ("a]", "a]"),
        ("[ 'a' , \"b\" ]", "a"),
    ],
)
def test_quotes_and_brackets_are_stripped_only_in_pairs(value: str, expected: str) -> None:
    assert front(f"title: {value}").title == expected


def test_a_flow_list_holds_every_value_and_skips_the_empty_ones() -> None:
    assert front("author: [a]") == Metadata(authors=("a",))
    assert front("author: [a, , 'b']") == Metadata(authors=("a", "b"))
    assert front("author: []") == Metadata()


def test_the_author_and_authors_keys_are_both_read_author_first() -> None:
    assert front("authors: [B]\nauthor: A") == Metadata(authors=("A", "B"))


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        ("2024", "2024"),
        ("2024-03", "2024-03"),
        ("2024-3-1", "2024"),
        ("'2024-03-01'", "2024-03-01"),
    ],
)
def test_a_date_keeps_the_year_month_and_day_it_states(date: str, expected: str) -> None:
    assert front(f"date: {date}").date == expected


def test_an_empty_identifier_field_gives_way_to_the_next_one() -> None:
    assert front("doi:\nidentifier: urn:x") == Metadata(identifier="urn:x")
    assert front("lang: und\nlanguage: de") == Metadata(language="de")


def test_unclosed_front_matter_is_ordinary_markdown() -> None:
    content = read("---\ntitle: X\n\nBody text\n")
    assert content.metadata == Metadata()
    assert texts(content) == ["title: X", "Body text"]


def test_front_matter_only_holds_no_text() -> None:
    with pytest.raises(ExtractionError, match="the file holds no text"):
        read("---\ntitle: Nothing else\n---\n")


# ---- nesting (D-351) ----------------------------------------------------------------------


def nested_list(depth: int) -> str:
    return "".join("  " * level + f"- item {level}\n" for level in range(depth)) + "\nAfter.\n"


def test_deeply_nested_lists_are_read_whole_up_to_the_limit() -> None:
    content = read(nested_list(30))
    assert texts(content) == [f"item {level}" for level in range(30)] + ["After."]


@pytest.mark.parametrize(
    "text",
    [nested_list(50), nested_list(3000), ">" * 100 + " deep\n\nafter\n", ">" * 5000 + " x\n"],
)
def test_nesting_past_the_limit_fails_rather_than_losing_text(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    # 3,000 levels of list are 9 MB of indent in one block, which MAX_BLOCK refuses first
    monkeypatch.setattr(markdown_module, "MAX_BLOCK", 10**9)
    with pytest.raises(ExtractionError, match=r"^notes\.md: the Markdown is nested too deeply"):
        read(text)


def test_nesting_is_refused_from_the_level_markdown_it_stops_at() -> None:
    """97 block quotes reach level 98, which reads; 98 reach level 99, the last one the
    parser makes, and that is refused (#632)."""
    assert texts(read(">" * 97 + " deep\n\nafter\n")) == ["deep", "after"]
    with pytest.raises(ExtractionError, match="nested too deeply"):
        read(">" * 98 + " deep\n\nafter\n")


def test_deep_inline_nesting_keeps_its_text() -> None:
    text = "*" * 3000 + "x" + "*" * 3000 + " " + "[" * 3000 + "y" + "](u)" * 3000
    assert "x" in texts(read(text))[0]
    assert "y" in texts(read(text))[0]


def test_the_limit_is_the_decided_one() -> None:
    assert markdown_module.MAX_NESTING == 100


# ---- broken files and encodings (D-345, D-347) --------------------------------------------


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "the file is empty"),
        (b"\n  \n", "the file holds no text"),
        (b"<!-- only a comment -->\n", "the file holds no text"),
        (b"***\n\n---\n", "the file holds no text"),  # rules only
        (b"[ref]: https://example.org\n", "the file holds no text"),
        (b"# Title\x00", "not a text file"),
        (b"%PDF-1.4\n", "this is a PDF, not a text file"),
        (b"PK\x03\x04rest", "not a text file"),
    ],
)
def test_broken_files_fail_with_a_clear_message(data: bytes, message: str) -> None:
    with pytest.raises(ExtractionError, match=message) as error:
        read(data)
    assert str(error.value).startswith("notes.md: ")


def test_an_image_alone_is_content() -> None:
    assert read("![only](a.png)\n").pages[0].pictures == (
        Picture("p1-i1", alt="only", ref="a.png"),
    )


def test_markdown_not_in_utf8_is_read_as_windows_1252_and_marked_as_guessed() -> None:
    content = read("# Caf\u00e9 \u2013 \u201cx\u201d\n".encode("cp1252"))
    assert texts(content) == ["Caf\u00e9 \u2013 \u201cx\u201d"]
    assert (content.source.encoding, content.source.encoding_guessed) == ("windows-1252", True)


def test_a_file_is_read_from_its_path(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Hi\n", encoding="utf-8")
    assert texts(extract_markdown(path)) == ["Hi"]
    with pytest.raises(ExtractionError, match=r"^gone\.md: cannot be opened"):
        extract_markdown(tmp_path / "gone.md")


# ---- speed: CommonMark's pathological inputs (D-351) ----------------------------------------

N = 20_000  # the large input; the base run is an eighth of it
PATHOLOGICAL: dict[str, Callable[[int], str]] = {
    "nested brackets": lambda n: "[" * n + "a" + "]" * n,
    "unclosed link openers": lambda n: "[a](" + "(" * n,
    "emphasis openers": lambda n: "*a " * n,
    "underscores": lambda n: "_a_ " * n,
    "mixed delimiters": lambda n: "a**b" * n + "c*" * n,
    "backticks": lambda n: "`a``" * n,
    "angle brackets": lambda n: "<" * n,
    "dollars": lambda n: "$a " * n,
    "table columns": lambda n: "|" + "a|" * n + "\n|" + "-|" * n + "\n",
    "table rows": lambda n: "|a|b|\n|-|-|\n" + "|x|y|\n" * n,
    "note references": lambda n: "[^a] " * n + "\n\n[^a]: x\n",
    "link definitions": lambda n: "".join(f"[{i}]: /u{i}\n" for i in range(n)) + "[1]" * n,
    "entities": lambda n: "&#x" * n,
}


@pytest.mark.parametrize("sized", PATHOLOGICAL.values(), ids=PATHOLOGICAL.keys())
def test_pathological_inputs_are_read_in_linear_time(sized: Callable[[int], str]) -> None:
    """Eight times the input against a base run, on CPU time (#298): a case that grew
    quadratically takes about 64 times as long and fails."""
    assert_linear(outcome, sized, N)


# ---- size limits (#174, D-579) ------------------------------------------------------------


def refused_before_parsing(text: str, message: str, monkeypatch: pytest.MonkeyPatch) -> int:
    """Read `text`, which must fail with `message` before markdown-it parses it; the peak
    of traced memory in bytes."""

    def parse(*_: object) -> None:
        raise AssertionError("markdown-it ran")

    monkeypatch.setattr(markdown_module.MarkdownIt, "parse", parse)
    tracemalloc.start()
    try:
        with pytest.raises(ExtractionError, match=message):
            read(text)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def test_a_file_of_more_lines_than_the_limit_is_refused_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = (
        r"^notes\.md: the file is too large; sci2audio reads Markdown files of up to 250,000 lines$"
    )
    assert refused_before_parsing("w\n" * 250_001, message, monkeypatch) < 20 * 1024 * 1024


def test_a_line_of_more_marks_than_the_limit_is_refused_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One line of "*a* " costs markdown-it about 470 times its size, and a limit on lines
    alone does not see it (D-579)."""
    message = (
        r"^notes\.md: the Markdown holds too much markup to read"
        r" \(more than 500,000 marks such as \* _ ` \[ <\)$"
    )
    text = "*a* " * 250_000 + "*"
    assert refused_before_parsing(text, message, monkeypatch) < 20 * 1024 * 1024


@pytest.mark.parametrize("mark", list("*_`[<$!\\&|~"))
def test_each_kind_of_mark_counts(monkeypatch: pytest.MonkeyPatch, mark: str) -> None:
    monkeypatch.setattr(markdown_module, "MAX_MARKS", 3)
    assert "marks" not in str(outcome("x" + mark * 3))
    assert "more than 3 marks" in str(outcome("x" + mark * 4))


def test_marks_are_counted_over_the_whole_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(markdown_module, "MAX_MARKS", 3)
    assert "more than 3 marks" in str(outcome("*a*\n\n|b|\n"))


def test_lines_at_the_limit_still_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(markdown_module, "MAX_LINES", 3)
    assert texts(read("a\n\nb\n")) == ["a", "b"]
    assert "of up to 3 lines" in str(outcome("a\n\nb\nc"))


def test_more_pieces_of_text_than_the_limit_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lines, pieces of text and pictures share one budget (`markup.MAX_ITEMS`): a file of
    few lines and marks can still make many of them, e.g. one list item per line."""
    monkeypatch.setattr(markup_module, "MAX_ITEMS", 6)
    assert texts(read("- a\n- b\n- c\n")) == ["a", "b", "c"]  # 3 lines of one piece each
    assert outcome("- a\n- b\n- c\n- d\n") == (
        "notes.md: the Markdown is too large to read (more than 6 pieces of text)"
    )


BLOCK_MESSAGE = (
    "notes.md: the Markdown holds a paragraph or block longer than {:,} characters"
    " (counted between blank lines)"
)


def test_a_paragraph_past_the_block_limit_is_refused_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """markdown-it costs about 22 times a paragraph's size: one of 64 MB in short lines
    took 1.4 GB, one long line 1.2 GB (#329)."""
    text = ("word " * 53 + "\n") * (8 * 1024 * 1024 // 266)  # 8 MB, no blank line
    message = re.escape(BLOCK_MESSAGE.format(4_000_000))
    assert refused_before_parsing(text, f"^{message}$", monkeypatch) < 40 * 1024 * 1024


def test_one_long_line_is_refused_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "word " * (8 * 1024 * 1024 // 5)
    message = re.escape(BLOCK_MESSAGE.format(4_000_000))
    assert refused_before_parsing(text, f"^{message}$", monkeypatch) < 40 * 1024 * 1024


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 9 + "\n\n" + "b" * 9, id="paragraphs"),
        pytest.param("a" * 9 + "\n \t\n" + "b" * 9, id="a blank line of spaces and tabs"),
        pytest.param("a" * 8 + "\r\n\r\n" + "b" * 9, id="CR LF"),
        pytest.param("a" * 9 + "\r\r" + "b" * 9, id="CR"),
        pytest.param("- " + "a" * 7 + "\n\n- " + "b" * 7 + "\n", id="list items"),
    ],
)
def test_blocks_at_the_limit_read(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """Each block holds 10 characters, its line end included."""
    monkeypatch.setattr(markdown_module, "MAX_BLOCK", 10)
    assert isinstance(outcome(text), Content)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 11, id="one line"),
        pytest.param("a" * 5 + "\n" + "b" * 5, id="two lines"),
        pytest.param("x\n\n" + "a" * 5 + "\r\n" + "b" * 5, id="CR LF inside a block"),
        pytest.param("- a\n- b\n- c\n- d", id="a tight list"),
        pytest.param("```\nabc\ndefgh\n```", id="a code block"),
        pytest.param("|a|b|\n|-|-|\n|c|d|", id="a table"),
    ],
)
def test_a_block_past_the_limit_is_refused(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(markdown_module, "MAX_BLOCK", 10)
    assert outcome(text) == BLOCK_MESSAGE.format(10)


@pytest.mark.parametrize(
    ("text", "longest"),
    [
        ("", 0),
        ("\n\n", 0),
        ("abc", 3),
        ("abc\n", 4),
        ("ab\ncd\n\nefghij", 6),
        ("ab\r\ncd\r\n \r\nx", 8),
        ("ab\rcd\r\t\r", 6),
        ("  \t  \n", 0),
        (" " * 100 + "x", 101),  # spaces before text make no blank line
    ],
)
def test_the_longest_block_counts_characters_between_blank_lines(text: str, longest: int) -> None:
    assert markdown_module.longest_block(text) == longest


def test_the_longest_block_is_found_in_linear_time() -> None:
    def sized(size: int) -> str:
        return ("a" * 50 + "\n" + " " * 50 + "\n\n") * (size // 103)

    assert_linear(markdown_module.longest_block, sized, 4_000_000)


def test_the_line_and_markup_limits_of_the_page_reader_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After rendering, the page reader's own limits (#329) stop the Markdown too."""
    with monkeypatch.context() as patch:
        patch.setattr(markup_module, "MAX_LINE", 5)
        assert outcome("abcdef") == (
            "notes.md: the Markdown holds a paragraph longer than 5 characters"
        )
    monkeypatch.setattr(markup_module, "MAX_MARKUP", 3)  # <ul> and two <li>
    assert isinstance(outcome("- a\n- b\n"), Content)
    assert outcome("- a\n- b\n- c\n") == (
        "notes.md: the Markdown holds too much markup to read (more than 3 tags, comments"
        " and declarations)"
    )


def test_the_tag_limit_applies_to_html_in_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(markup_module, "MAX_TAG", 100)
    assert texts(read("<p" + " a" * 48 + ">x</p>\n")) == ["x"]  # 100 characters
    assert outcome("<p" + " a" * 49 + ">x</p>\n") == (
        "notes.md: the Markdown holds a tag longer than 100 characters"
    )


def test_the_limits_are_the_decided_ones() -> None:
    assert (markdown_module.MAX_LINES, markdown_module.MAX_MARKS) == (250_000, 500_000)
    assert markup_module.MAX_ITEMS == 1_000_000  # D-579
    assert markdown_module.MAX_BLOCK == 4_000_000  # D-777
    assert markup_module.MAX_TAG == 1_000_000  # D-783


# ---- properties --------------------------------------------------------------------------

MARKUP = st.lists(
    st.sampled_from(
        [
            *"ab #*_`~[]()!<>|-+=:$^\\\n\t ",
            *("\n\n", "```", "$$", "[^1]", "[^1]: ", "<p>", "</p>", "<br>", "    ", "---\n"),
        ]
    ),
    max_size=80,
).map("".join)


@given(MARKUP)
def test_any_markdown_gives_content_or_a_clear_error(text: str) -> None:
    content = outcome(text)
    if isinstance(content, str):
        assert content.startswith("notes.md: ")
        return
    page = content.pages[0]
    ids = [item.id for item in (*page.lines, *page.pictures)]
    assert len(ids) == len(set(ids))
    assert sorted(page.order) == sorted(ids)
    for line in page.lines:
        if any("pre" in run.tags for run in line.runs):
            continue
        assert line.text == line.text.strip(" ")
        assert "  " not in line.text
        assert not set(line.text) & set("\n\r\t\x0c")


@given(MARKUP)
def test_with_low_limits_any_markdown_reads_or_names_a_limit(text: str) -> None:
    limits = (
        r"the file is empty|the file holds no text|the Markdown is nested too deeply to read"
        r"|the file is too large; sci2audio reads Markdown files of up to 4 lines"
        r"|the Markdown holds too much markup to read \(more than 5 marks"
        r"|the Markdown is too large to read \(more than 8 pieces of text\)"
        r"|the Markdown holds a paragraph or block longer than 12 characters"
        r"|the Markdown holds too much markup to read \(more than 9 tags"
        r"|the Markdown holds a paragraph longer than 6 characters"
        r"|the Markdown holds a tag longer than 8 characters"
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(markdown_module, "MAX_LINES", 4)
        patch.setattr(markdown_module, "MAX_MARKS", 5)
        patch.setattr(markdown_module, "MAX_BLOCK", 12)
        patch.setattr(markup_module, "MAX_ITEMS", 8)
        patch.setattr(markup_module, "MAX_MARKUP", 9)
        patch.setattr(markup_module, "MAX_LINE", 6)
        patch.setattr(markup_module, "MAX_TAG", 8)
        content = outcome(text)
    if isinstance(content, str):
        assert re.match(rf"notes\.md: (?:{limits})", content), content


@given(st.binary(max_size=500))
def test_any_bytes_give_content_or_a_clear_error(data: bytes) -> None:
    content = outcome(data)
    assert isinstance(content, Content) or content.startswith("notes.md: ")
