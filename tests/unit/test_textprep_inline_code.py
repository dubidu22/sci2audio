"""Inline code is read as printed (#854): no text step rewrites a run tagged `code`.

Markdown and EPUB mark inline code with the source tag `code` (`<code>` outside `<pre>`);
`run_steps` drops every inline edit that touches such a run, for built-in steps and
plugins alike. The prose around it is still read by the rules, and a code block keeps
its notice.
"""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, Document, Edit, EditKind, Span
from sci2audio.extraction import read_markdown
from sci2audio.layout import build_document
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    Stage,
    Status,
    StepContext,
    TextStep,
    overlap,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.runner import inline_code


def markdown(text: str, language: str) -> Document:
    data = f"---\nlang: {language}\n---\n{text}\n".encode()
    return build_document(read_markdown(data, "note.md"))


def read(document: Document, language: str, steps=BUILT_IN_STEPS) -> str:
    run = run_steps(document, StepContext(language), steps, strict=True)
    assert not run.problems
    return spoken_text(run.script())


class Arrows(TextStep):
    """Reads "=>" and "<=>" as words, as a rule for arrows typed in ASCII would (#841)."""

    id = "arrows"
    languages = ("en", "de")
    category = Category.NUMBERS_AND_UNITS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        words = {"en": ("if and only if", "implies"), "de": ("genau dann wenn", "daraus folgt")}
        both, one = words[context.language]
        edits = []
        for index, block in enumerate(document.blocks):
            at = 0
            while (found := block.text.find("=>", at)) >= 0:
                start = found - 1 if found and block.text[found - 1] == "<" else found
                said = both if start < found else one
                edits.append(
                    Edit(Span(index, start, found + 2), EditKind.REPLACE, "arrow", self.id, said)
                )
                at = found + 2
        return edits


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Use `x => x + 1` here.", "Use x => x + 1 here."),
        ("`a <=> b`", "a <=> b"),
    ],
)
def test_arrows_in_inline_code_stay_as_printed(language: str, printed: str, said: str) -> None:
    document = markdown(printed, language)
    assert read(document, language, (*BUILT_IN_STEPS[:-1], Arrows(), BUILT_IN_STEPS[-1])) == said
    assert read(document, language) == said


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "A => B, but `a <=> b`.", "A implies B, but a <=> b."),
        ("de", "A => B, aber `x => x + 1`.", "A daraus folgt B, aber x => x + 1."),
    ],
)
def test_the_same_arrow_in_prose_is_still_read(language: str, printed: str, said: str) -> None:
    steps = (*BUILT_IN_STEPS[:-1], Arrows(), BUILT_IN_STEPS[-1])
    assert read(markdown(printed, language), language, steps) == said


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        (
            "en",
            "Set `n = 2^3` and `p < 0.05` for 10 km, e.g. `10 km`.",
            "Set n = 2^3 and p < 0.05 for 10 kilometres, for example 10 km.",
        ),
        (
            "de",
            "Setze `n = 2^3` und `p < 0.05` für 10 km, z. B. `10 km`.",
            "Setze n = 2^3 und p < 0.05 für 10 Kilometer, zum Beispiel 10 km.",
        ),
    ],
)
def test_operators_and_numbers_in_inline_code_stay_and_prose_is_read(
    language: str, printed: str, said: str
) -> None:
    assert read(markdown(printed, language), language) == said


def test_a_code_block_keeps_its_notice() -> None:
    document = markdown("Before.\n\n```\nx = 2^3\n```\n\nAfter.", "en")
    said = read(document, "en")
    assert "2^3" not in said
    assert said.startswith("Before.")
    assert said.endswith("After.")


def test_hidden_inline_code_is_still_left_out() -> None:
    document = markdown("Shown <span hidden>`x => 1`</span> text.", "en")
    assert read(document, "en") == "Shown text."


@pytest.mark.parametrize(
    ("language", "printed", "url"),
    [
        (
            "en",
            "The data are available at `https://example.org/data` for everyone.",
            "https://example.org/data",
        ),
        ("en", "See `www.example.org/a`.", "www.example.org/a"),
        (
            "de",
            "Die Daten sind unter `https://example.org/daten` abrufbar.",
            "https://example.org/daten",
        ),
        ("de", "Siehe `example.org/a/b`.", "example.org/a/b"),
    ],
)
def test_a_code_span_of_only_a_url_is_left_out_as_before(
    language: str, printed: str, url: str
) -> None:
    document = markdown(printed, language)
    run = run_steps(document, StepContext(language), strict=True)
    links = [edit for edit in run.edits(Status.ACCEPTED) if edit.step == "links"]
    assert any(url in document.text_of(edit.span) for edit in links)
    without = markdown(printed.replace("`", ""), language)
    assert spoken_text(run.script()) == read(without, language)
    assert not inline_code(document)


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        (
            "en",
            "Run `curl https://example.org/a` first.",
            "Run curl https://example.org/a first.",
        ),
        (
            "de",
            "Führe `curl https://example.org/a` aus.",
            "Führe curl https://example.org/a aus.",
        ),
    ],
)
def test_a_url_inside_longer_code_stays_as_printed(language: str, printed: str, said: str) -> None:
    assert read(markdown(printed, language), language) == said


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    ("code", "url"),
    [
        ("https://example.org/a.", "https://example.org/a"),  # sentence punctuation inside
        ("https://example.org/a,", "https://example.org/a"),
        ("<https://example.org/a>", "https://example.org/a"),  # brackets around it
        ("(https://example.org/a)", "https://example.org/a"),
        ('"https://example.org/a"', "https://example.org/a"),
        ("https://example.org/a, https://example.org/b", "https://example.org/b"),  # two
        ("https://example.org/a https://example.org/b", "https://example.org/b"),
        ("https://example.org/a,https://example.org/b.", "https://example.org/b"),
        ("doi:10.1000/xyz123", "10.1000/xyz123"),  # any link the links step finds
    ],
)
def test_a_code_span_of_only_links_is_left_to_the_links_step(
    language: str, code: str, url: str
) -> None:
    printed = {
        "en": f"The data are available at `{code}` for everyone.",
        "de": f"Die Daten sind unter `{code}` abrufbar.",
    }[language]
    document = markdown(printed, language)
    assert not inline_code(document)
    run = run_steps(document, StepContext(language), strict=True)
    links = [edit for edit in run.edits(Status.ACCEPTED) if edit.step == "links"]
    assert any(url in document.text_of(edit.span) for edit in links)
    plain = make_document([(BlockKind.PARAGRAPH, document.blocks[0].text)], language)
    assert spoken_text(run.script()) == read(plain, language)


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    "code",
    [
        "curl https://example.org/a",
        "https://example.org/a and https://example.org/b",
        "https://example.org/a; x => 1",
        "fetch(https://example.org/a)",
    ],
)
def test_links_with_other_code_stay_as_printed(language: str, code: str) -> None:
    printed = {"en": f"Run `{code}` now.", "de": f"Führe `{code}` aus."}[language]
    said = printed.replace("`", "")
    assert read(markdown(printed, language), language) == said


def test_a_second_run_keeps_inline_code_as_printed() -> None:
    document = markdown("Set `n = 2^3` for 10 km.", "en")
    first = run_steps(document, StepContext("en"), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    second = run_steps(rebuilt, StepContext("en"), strict=True)
    assert spoken_text(second.script()) == spoken_text(first.script())
    assert spoken_text(first.script()) == "Set n = 2^3 for 10 kilometres."


def test_inline_code_spans_are_the_code_runs_in_block_text() -> None:
    document = markdown("Use `x => 1` and `y`.\n\n```\nz\n```", "en")
    assert {
        index: [document.blocks[index].text[start:end] for start, end in spans]
        for index, spans in inline_code(document).items()
    } == {0: ["x => 1", "y"]}


class Fixed(TextStep):
    def __init__(self, edits: list[Edit]) -> None:
        self.id = "fixed"
        self.languages = ("en",)
        self.category = Category.NUMBERS_AND_UNITS
        self.stage = Stage.INLINE
        self.edits = [replace(edit, step=self.id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


TEXT = "one two three four five six"


@st.composite
def tagged(draw: st.DrawFn) -> tuple[Document, list[Edit]]:
    """A one-block document with some words as inline code, and edits that do not
    overlap one another, anywhere in its text."""
    cuts = sorted(draw(st.sets(st.integers(0, len(TEXT)), max_size=8)))
    code = [(a, b, "code") for a, b in zip(cuts[::2], cuts[1::2], strict=False) if a < b]
    document = make_document([(BlockKind.PARAGRAPH, TEXT)], tags={0: code})
    edges = sorted(draw(st.sets(st.integers(0, len(TEXT)), max_size=8)))
    edits = []
    for a, b in zip(edges[::2], edges[1::2], strict=False):
        if a == b:
            edits.append(Edit(Span(0, a, a), EditKind.PAUSE, "test", "fixed"))
        else:
            edits.append(Edit(Span(0, a, b), EditKind.REPLACE, "test", "fixed", "said"))
    return document, edits


@given(tagged())
def test_no_inline_edit_touches_inline_code_and_others_are_untouched(
    found: tuple[Document, list[Edit]],
) -> None:
    document, edits = found
    code = [Span(0, start, end) for start, end in inline_code(document).get(0, [])]
    run = run_steps(document, StepContext("en"), [Fixed(edits)], strict=True)
    accepted = run.edits(Status.ACCEPTED)
    assert not [e for e in accepted for span in code if overlap(span, e.span)]
    assert len(run.outcomes) == len(accepted)
    assert set(accepted) == {e for e in edits if not any(overlap(s, e.span) for s in code)}
