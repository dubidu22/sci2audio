"""Markdown extraction on small made-up files and broken files (#74, the Markdown part of #5).

The Markdown is rendered to HTML and read by the EPUB page reader (D-340), so it gets the
same lines, tags, styles, pictures and order as an EPUB chapter (D-306 to D-310). The dialect
(D-339), the roles of notes and maths (D-341), front matter (D-342), the empty outline (D-343)
and the nesting limit that fails rather than loses text (D-351) are pinned here.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Content, Metadata, Picture, SourceFormat, TextLine
from sci2audio.extraction import ExtractionError, extract_markdown, read_markdown
from sci2audio.extraction import markdown as markdown_module

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
def test_nesting_past_the_limit_fails_rather_than_losing_text(text: str) -> None:
    with pytest.raises(ExtractionError, match=r"^notes\.md: the Markdown is nested too deeply"):
        read(text)


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

N = 20_000
PATHOLOGICAL = {
    "nested brackets": "[" * N + "a" + "]" * N,
    "unclosed link openers": "[a](" + "(" * N,
    "emphasis openers": "*a " * N,
    "underscores": "_a_ " * N,
    "mixed delimiters": "a**b" * N + "c*" * N,
    "backticks": "`a``" * N,
    "angle brackets": "<" * N,
    "dollars": "$a " * N,
    "table columns": "|" + "a|" * N + "\n|" + "-|" * N + "\n",
    "table rows": "|a|b|\n|-|-|\n" + "|x|y|\n" * N,
    "note references": "[^a] " * N + "\n\n[^a]: x\n",
    "link definitions": "".join(f"[{i}]: /u{i}\n" for i in range(N)) + "[1]" * N,
    "entities": "&#x" * N,
}


@pytest.mark.parametrize("text", PATHOLOGICAL.values(), ids=PATHOLOGICAL.keys())
def test_pathological_inputs_are_read_in_linear_time(text: str) -> None:
    """Measured at most 0.7 s each; a case that grew quadratically would take minutes. The
    bound leaves room for slow CI machines."""
    start = time.perf_counter()
    outcome(text)
    assert time.perf_counter() - start < 5


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


@given(st.binary(max_size=500))
def test_any_bytes_give_content_or_a_clear_error(data: bytes) -> None:
    content = outcome(data)
    assert isinstance(content, Content) or content.startswith("notes.md: ")
