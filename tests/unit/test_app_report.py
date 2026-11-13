"""The report (UC-01) and the script text: fields, pages, formats."""

import json
from dataclasses import replace

from sci2audio.app import (
    JobSettings,
    build_report,
    prepare_script,
    report_data,
    report_markdown,
    script_text,
)
from sci2audio.app.report import FORMAT, VERSION
from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Edit,
    EditKind,
    Page,
    Part,
    Section,
    Source,
    SourceFormat,
    Span,
    TextLine,
    TextRun,
)
from sci2audio.textprep import Category, Stage, StepContext, TextStep


class Fixed(TextStep):
    languages = ("en",)

    def __init__(self, step_id, edits, category=Category.CITATIONS):  # type: ignore[no-untyped-def]
        self.id = step_id
        self.stage = Stage.INLINE
        self.category = category
        self.edits = [replace(edit, step=step_id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


def two_pages() -> Document:
    """A heading and a paragraph on page 1 (printed "vii"), a paragraph across pages 1 and 2
    (printed "8"), a reference list on page 2."""
    lines = [
        TextLine("a", (TextRun("1 Intro"),)),
        TextLine("b", (TextRun("First [1] and | *odd*."),)),
        TextLine("c", (TextRun("Runs on"),)),
        TextLine("d", (TextRun("to page two [2]."),)),
        TextLine("e", (TextRun("References"),)),
        TextLine("f", (TextRun("[1] A. 2020."),)),
    ]
    content = Content(
        Source("two.pdf", SourceFormat.PDF, sha256="ab" * 32),
        (Page(1, tuple(lines[:3])), Page(2, tuple(lines[3:]))),
    )
    blocks = (
        Block(BlockKind.HEADING, "1 Intro", (Part("a"),), label="1"),
        Block(BlockKind.PARAGRAPH, "First [1] and | *odd*.", (Part("b"),)),
        Block(BlockKind.PARAGRAPH, "Runs on\nto page two [2].", (Part("c"), Part("d", 8))),
        Block(BlockKind.HEADING, "References", (Part("e"),)),
        Block(BlockKind.PARAGRAPH, "[1] A. 2020.", (Part("f"),)),
    )
    sections = (Section("1 Intro", 1, 0, 3), Section("References", 1, 3, 5))
    return Document(content, "en", blocks, sections, page_labels=("vii", "8"))


EDITS = [
    Edit(Span(1, 6, 9), EditKind.REMOVE, "a citation is not read", "x"),
    Edit(Span(2, 20, 23), EditKind.REPLACE, "a citation is read as its number", "x", "two"),
    Edit(Span(2, 0, 0), EditKind.PAUSE, "a breath", "x"),
    Edit(Span(4, 0, 3), EditKind.REMOVE, "a citation is not read", "x"),
]


def prepared():  # type: ignore[no-untyped-def]
    return prepare_script(two_pages(), JobSettings(), [Fixed("cite", EDITS)])


def test_each_edit_names_its_page_as_numbered_and_as_printed() -> None:
    report = build_report(prepared(), {})
    pages = [(e.where.span, e.where.page, e.where.printed_page) for e in report.edits]
    assert pages == [
        (Span(1, 6, 9), 1, "vii"),
        (Span(2, 0, 0), 1, "vii"),
        (Span(2, 20, 23), 2, "8"),  # the part that holds the span's first character
        (Span(4, 0, 3), 2, "8"),
    ]


def test_each_edit_shows_the_original_and_what_is_said() -> None:
    report = build_report(prepared(), {})
    said = [(e.kind, e.original, e.said, e.spoken) for e in report.edits]
    assert said == [
        (EditKind.REMOVE, "[1]", "", True),
        (EditKind.PAUSE, "", "[pause]", True),
        (EditKind.REPLACE, "[2]", "two", True),
        (EditKind.REMOVE, "[1]", "", False),  # in the reference list, not chosen
    ]


def test_the_json_has_a_fixed_shape() -> None:
    data = report_data(build_report(prepared(), {"language": ""}))
    assert list(data) == [
        "format", "version", "sci2audio", "source", "language", "settings", "chapters",
        "counts", "edits", "problems", "not_run", "warnings",
    ]  # fmt: skip
    assert (data["format"], data["version"]) == (FORMAT, VERSION) == ("sci2audio-report", 1)
    assert data["source"] == {"name": "two.pdf", "format": "pdf", "sha256": "ab" * 32}
    assert data["chapters"] == [
        {"index": 0, "title": "1 Intro", "blocks": [0, 3], "first_page": 1,
         "references": False, "selected": True, "utterances": 3},
        {"index": 1, "title": "References", "blocks": [3, 5], "first_page": 2,
         "references": True, "selected": False, "utterances": 0},
    ]  # fmt: skip
    assert list(data["counts"]) == [str(c) for c in Category]
    assert data["counts"]["citations"] == {
        "label": "Citations", "applied": 3, "not_spoken": 1, "set_aside": 0, "switched_off": 0,
    }  # fmt: skip
    assert data["edits"][2] == {
        "category": "citations",
        "step": "cite",
        "kind": "replace",
        "reason": "a citation is read as its number",
        "status": "accepted",
        "spoken": True,
        "original": "[2]",
        "said": "two",
        "chapter": 0,
        "block": 2,
        "start": 20,
        "end": 23,
        "page": 2,
        "printed_page": "8",
    }
    json.dumps(data)  # plain JSON data


def test_the_markdown_names_chapters_counts_and_edits() -> None:
    text = report_markdown(build_report(prepared(), {}))
    assert text.startswith("# What sci2audio will read: two.pdf\n")
    assert "| 2 | References | 2 | no (reference list) | 0 |" in text
    assert "| Citations | 3 | 1 | 0 | 0 |" in text
    assert "## Citations (4)" in text
    assert (
        "- page 2 (printed 8), chapter 1, applied: “\\[2\\]” → read as “two”. "
        "Reason: a citation is read as its number. Step: cite." in text
    )
    assert "chapter 2, not spoken (chapter not chosen): “\\[1\\]” → left out." in text
    assert "(position) → a pause" in text
    assert "## Problems" not in text


def test_the_markdown_escapes_what_markdown_would_read_as_markup() -> None:
    document = two_pages()
    step = Fixed("odd", [Edit(Span(1, 16, 21), EditKind.REMOVE, "odd | text", "x")])
    text = report_markdown(build_report(prepare_script(document, JobSettings(), [step]), {}))
    assert "“\\*odd\\*”" in text
    assert "Reason: odd \\| text." in text


def test_the_script_has_one_utterance_per_line_and_a_blank_line_between_blocks() -> None:
    assert script_text(prepared()) == (
        "sci2audio listening script\nSource: two.pdf\nLanguage: en\n\n"
        "# 1. 1 Intro\n\n1 Intro\n\nFirst and | *odd*.\n\n[pause]\nRuns on to page two two.\n\n"
        "# 2. References (not spoken)\n"
    )


def test_an_empty_chosen_chapter_says_so() -> None:
    step = Fixed(
        "all",
        [
            Edit(Span(3, 0, 10), EditKind.REMOVE, "r", "x"),
            Edit(Span(4, 0, 12), EditKind.REMOVE, "r", "x"),
        ],
    )
    result = prepare_script(two_pages(), JobSettings(chapters=frozenset({1})), [step])
    assert script_text(result).endswith("# 2. References\n\n(nothing to read)\n")
    report = build_report(result, {})
    assert report.chapters[1].utterances == 0
