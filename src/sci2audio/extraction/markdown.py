"""Record what a Markdown file holds as `Content`, deciding nothing (D-63, D-337 to D-351).

The file is decoded as a text file (D-345), rendered to HTML by markdown-it-py and read by
the same page reader as an EPUB chapter (D-340), so layout meets one shape for both: one page,
one text line per block element, tags for the markup around each run, pictures with their
alternative text and `ref`, and `Page.order`.

The dialect is CommonMark with GFM tables and strikethrough, footnotes, dollar maths and YAML
front matter; raw HTML is read as HTML; no smart quotes, no automatic links, no heading
anchors (D-339). Notes and maths are rendered with the roles an EPUB uses, so layout finds them
the same way (D-341): a note mark is ``<sup><a role="doc-noteref">1</a></sup>``, the notes are
``<li role="doc-endnote">`` in a ``<section role="doc-endnotes">``, and maths is a ``span`` or
``div`` with ``role="math"`` holding the TeX as typed. Front matter is not text: its title,
authors, date, language and identifier fill `Metadata` (D-342). The outline stays empty: the
headings are lines (D-343).

markdown-it drops the rest of a block nested deeper than its nesting limit without an error,
so a file that reaches the limit fails instead of losing text (D-351). A file of more lines
than `MAX_LINES`, more marks that can start markup than `MAX_MARKS`, or a block between two
blank lines longer than `MAX_BLOCK` characters fails before it is parsed (D-579, #329), and
the page reader stops at `markup.MAX_ITEMS` pieces of text, `markup.MAX_MARKUP` tags and
`markup.MAX_LINE` characters in one line.

Three things in the file are not read, as markdown-it and its footnote plugin have it: a
note that no mark cites and everything after a ``<!--`` that is never closed (GitHub and a
browser drop these too), and all but the last of two notes with one label. The unclosed
comment is decided here, not left to the HTML parser, as Python's read it differently in
different patch versions (sci2audio now brings its own copy, #175).

An image's alternative text is its text only: inline HTML tags are left out and a line break
is a space (#602), as markdown-it-py 4.3 started to keep both.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

from sci2audio.core import Content, Metadata, SourceFormat
from sci2audio.extraction.errors import ExtractionError
from sci2audio.extraction.language import stated_language
from sci2audio.extraction.markup import (
    Anchors,
    Budget,
    PageReader,
    TooMuchText,
    fold,
    resolve_links,
)
from sci2audio.extraction.text import check_lines, decode_text, source_of

MAX_NESTING = 100  # markdown-it's nesting limit (D-351); far below Python's recursion limit
# Size limits, counted on the decoded text before markdown-it makes its tokens, which cost far
# more than the file (#174, D-579): a file at the limits took at most about 900 MB to read
# (250,000 list items of one emphasis each), where the 64 MB byte limit allowed some 30 GB.
MAX_LINES = 250_000  # printed lines, blank ones included
MAX_MARKS = 500_000  # characters in _MARKS: one line of "*a* " costs about 470 times its size
# characters between two blank lines (#329, D-777): markdown-it costs about 22 times the size
# of a paragraph (one of 64 MB in short lines took 1.4 GB); 16 blocks at this limit took 595 MB
MAX_BLOCK = 4_000_000
_MARKS = "*_`[<$!\\&|~"
_LINE = re.compile(r"[^\r\n]*(?:\r\n?|\n)?")  # one printed line and its line end
_BLANK = re.compile(r"[ \t]*(?:\r\n?|\n)?")  # a blank line, as CommonMark has it
_DATE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")


def extract_markdown(path: Path) -> Content:
    """Read the Markdown file at `path` into `Content`; ExtractionError if it can't be read."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ExtractionError(f"{path.name}: cannot be opened ({error.strerror})") from error
    return read_markdown(data, path.name)


def read_markdown(data: bytes, name: str) -> Content:
    """Read Markdown bytes into `Content`; `name` is the bare file name the source keeps."""
    decoded = decode_text(data, name)
    check_lines(decoded.text, name, MAX_LINES, "Markdown")
    if sum(decoded.text.count(mark) for mark in _MARKS) > MAX_MARKS:
        raise ExtractionError(
            f"{name}: the Markdown holds too much markup to read (more than {MAX_MARKS:,}"
            " marks such as * _ ` [ <)"
        )
    if longest_block(decoded.text) > MAX_BLOCK:
        raise ExtractionError(
            f"{name}: the Markdown holds a paragraph or block longer than {MAX_BLOCK:,}"
            " characters (counted between blank lines)"
        )
    parser = _parser()
    env: EnvType = {}
    too_deep = ExtractionError(f"{name}: the Markdown is nested too deeply to read")
    try:
        tokens = parser.parse(decoded.text, env)
        if any(token.level >= MAX_NESTING - 1 for token in tokens):
            raise too_deep
        html = parser.renderer.render(tokens, parser.options, env)
    except RecursionError as error:
        raise too_deep from error
    anchors = Anchors()
    anchors.pages[name] = 1
    reader = PageReader(1, name, anchors, Budget())
    try:
        reader.read(html)
    except TooMuchText as error:
        message = error.message("Markdown") or (
            f"the Markdown is too large to read (more than {error.limit:,} pieces of text)"
        )
        raise ExtractionError(f"{name}: {message}") from None
    (page,) = resolve_links((reader.page(),), anchors)
    if not page.lines and not page.pictures:
        raise ExtractionError(f"{name}: the file holds no text")
    front = next((token.content for token in tokens if token.type == "front_matter"), "")
    return Content(
        source=source_of(data, name, SourceFormat.MARKDOWN, decoded),
        pages=(page,),
        metadata=_metadata(front),
    )


def longest_block(text: str) -> int:
    """The characters of the longest stretch of `text` between two blank lines (a line of
    only spaces and tabs is blank), line ends included; a linear scan that copies no line."""
    longest = block = 0
    for line in _LINE.finditer(text):
        start, end = line.span()
        if start == end:  # the empty match at the end of the text
            break
        if _BLANK.fullmatch(text, start, end):
            block = 0
        else:
            block += end - start
            longest = max(longest, block)
    return longest


# ---- the parser ------------------------------------------------------------------------


def _parser() -> MarkdownIt:
    """A fresh parser per file: no state is shared between jobs."""
    parser = MarkdownIt(
        "commonmark",
        {"maxNesting": MAX_NESTING, "html": True, "linkify": False, "typographer": False},
    )
    parser.enable(["table", "strikethrough"])
    parser.use(front_matter_plugin)
    parser.use(footnote_plugin)
    # As Pandoc: no space inside the dollars and no digit right after the closing one, so
    # "$5 and $10" stays text; display maths ends at a blank line.
    parser.use(dollarmath_plugin, allow_space=False, allow_digits=False, allow_blank_lines=False)
    rules = {
        "front_matter": _nothing,
        "footnote_ref": _note_mark,
        "footnote_block_open": _notes_open,
        "footnote_block_close": _notes_close,
        "footnote_open": _note_open,
        "footnote_close": _note_close,
        "footnote_anchor": _nothing,  # the back-link arrow is not in the file
        "html_block": _html_block,
        "image": _image,
        "math_inline": _maths_inline,
        "math_inline_double": _maths_block,
        "math_block": _maths_block,
        "math_block_label": _maths_block,
    }
    for kind, rule in rules.items():
        parser.add_render_rule(kind, rule)
    return parser


def _nothing(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    return ""


def _html_block(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    """Raw HTML as typed, except a comment that is never closed: it hides the rest of the
    file, decided here because Python's HTML parser has read it as text in some versions."""
    content = tokens[idx].content
    if content.lstrip().startswith("<!--") and "-->" not in content:
        return ""
    return content


def _image(
    self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
) -> str:
    """An image whose alternative text is its text only (#602): markdown-it-py 4.3 keeps
    inline HTML and line breaks in it, which would reach the spoken figure notice."""
    token = tokens[idx]
    token.attrSet("alt", _alt_text(token.children or []))
    return self.renderToken(tokens, idx, options, env)


def _alt_text(tokens: Sequence[Token]) -> str:
    """The text of an image's description: text and code as typed (escapes and entities
    already resolved), nested images' text, a space for a line break, no HTML tags."""
    out: list[str] = []
    for token in tokens:
        if token.type in ("text", "code_inline"):
            out.append(token.content)
        elif token.type == "image":
            out.append(_alt_text(token.children or []))
        elif token.type in ("softbreak", "hardbreak"):
            out.append(" ")
    return "".join(out)


def _number(token: Token) -> str:
    return str(token.meta["id"] + 1)


def _note_mark(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    token = tokens[idx]
    number = _number(token)
    ref = f"fnref{number}" + (f":{token.meta['subId']}" if token.meta.get("subId", 0) > 0 else "")
    return f'<sup><a href="#fn{number}" id="{ref}" role="doc-noteref">{number}</a></sup>'


def _notes_open(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    return '<section role="doc-endnotes">\n<ol>\n'


def _notes_close(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    return "</ol>\n</section>\n"


def _note_open(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    return f'<li id="fn{_number(tokens[idx])}" role="doc-endnote">'


def _note_close(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    return "</li>\n"


def _maths_inline(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    return f'<span role="math">{escapeHtml(tokens[idx].content)}</span>'


def _maths_block(self: object, tokens: Sequence[Token], idx: int, *_: object) -> str:
    token = tokens[idx]
    label = f" ({escapeHtml(token.info)})" if token.type == "math_block_label" else ""
    return f'<div role="math">{escapeHtml(token.content.strip())}{label}</div>\n'


# ---- front matter ---------------------------------------------------------------------


def _metadata(front: str) -> Metadata:
    """Title, authors, date, language and identifier from YAML front matter (D-342), read
    by a small line reader: `key: value`, `key: [a, b]`, `- a` and `- name: a` lists, and
    `>` or `|` blocks. Anything else is ignored; nothing here can fail the file."""
    values = _values(front)

    def first(*keys: str) -> str:
        for key in keys:
            if found := [v for v in values.get(key, []) if v]:
                return found[0]
        return ""

    date = ""
    if found := _DATE.match(first("date")):
        date = "-".join(part for part in found.groups() if part)
    return Metadata(
        title=first("title"),
        authors=tuple(v for v in values.get("author", []) + values.get("authors", []) if v),
        date=date,
        identifier=first("doi", "identifier", "isbn"),
        language=_language(values),
    )


def _language(values: dict[str, list[str]]) -> str:
    """The first value of `lang`, then `language`, that names a language (#237): "und"
    states none, so the next one counts, as in an EPUB."""
    stated = (stated_language(v) for key in ("lang", "language") for v in values.get(key, []))
    return next((tag for tag in stated if tag), "")


def _values(front: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    key = ""
    block: list[str] | None = None  # the lines of a `>` or `|` block being read
    for line in front.splitlines():
        stripped = line.strip()
        indented = line[:1] in (" ", "\t")
        if block is not None:
            if indented or not stripped:
                block.append(stripped)
                continue
            values[key] = [fold(" ".join(block))]
            block = None
        if not stripped or stripped.startswith("#"):
            continue
        if not indented and not stripped.startswith("-") and ":" in stripped:
            name, _, value = stripped.partition(":")
            key = name.strip().lower()
            value = value.strip()
            if value in (">", "|", ">-", "|-", ">+", "|+"):
                block = []
                values[key] = []
            else:
                values[key] = _items(value) if value else []
        elif key and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item.lower().startswith("name:"):
                item = item[len("name:") :].strip()
            elif _is_mapping(item):  # another field of a list entry (affiliation: ...)
                continue
            values.setdefault(key, []).append(_unquote(item))
        elif key and indented and stripped.lower().startswith("name:"):
            values.setdefault(key, []).append(_unquote(stripped[len("name:") :].strip()))
    if block is not None:
        values[key] = [fold(" ".join(block))]
    return values


def _items(value: str) -> list[str]:
    if value.startswith("[") and value.endswith("]"):
        return [_unquote(part.strip()) for part in value[1:-1].split(",") if part.strip()]
    return [_unquote(value)]


def _is_mapping(item: str) -> bool:
    key, colon, _ = item.partition(":")
    return bool(colon) and bool(re.fullmatch(r"[A-Za-z_][\w-]*", key.strip()))


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return fold(value)
