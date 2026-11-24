# ruff: noqa: RUF001, RUF002, RUF003
# (minus signs and superscripts are what these rules are about)
"""Raised exponents whose raise only their runs show (#576, #589): "10" and a raised "4"
before "K" is 10⁴ K, not "104 thousand"; "(I − P)" and a raised "−1" is an inverse."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Content,
    Document,
    Page,
    Part,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.testing import make_document
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.textprep import NumbersStep, StepContext, UnitStep, run_steps, spoken_text
from sci2audio.textprep.footnotes import as_superscripts, raised_exponents

STEPS = (NumbersStep(), UnitStep())


def tagged(*runs: str | tuple[str]) -> Document:
    """One paragraph of runs; a one-tuple is a run tagged `sup`."""
    text, tags = "", []
    for run in runs:
        if isinstance(run, tuple):
            tags.append((len(text), len(text) + len(run[0]), "sup"))
            text += run[0]
        else:
            text += run
    return make_document([(BlockKind.PARAGRAPH, text)], tags={0: tags})


def read(document: Document, language: str = "en") -> str:
    run = run_steps(document, StepContext(language), steps=STEPS, strict=True)
    return spoken_text(run.script())


def read_twice(document: Document, language: str = "en") -> tuple[str, str]:
    context = StepContext(language)
    first = run_steps(document, context, steps=STEPS, strict=True).script()
    rebuilt = rebuilt_from_script(document, first)
    second = run_steps(rebuilt, context, steps=STEPS, strict=True).script()
    return spoken_text(first), spoken_text(second)


def test_an_exponent_is_a_raised_run_glued_after_a_digit_or_a_signed_one_after_a_term() -> None:
    document = tagged(
        "10", ("4",), "K, ", ("40",), "K, x", ("2",), ", (I − P)", ("−1",), ", [A]", ("-2",),
        ", A", ("+1",), ", 10", ("−", ), ("3",), ", ", ("−1",), " and 10", ("1234",),
    )  # fmt: skip
    text = document.blocks[0].text
    found = [text[start:end] for start, end in raised_exponents(document)[0]]
    # not the mass number after a space, the digit after a letter, the signed run after a
    # space or the four digits; the "−" and "3" side by side are one run
    assert found == ["4", "−1", "-2", "+1", "−3"]


def test_as_superscripts_keeps_every_offset() -> None:
    assert as_superscripts("104K and (A)−1", [(2, 3), (12, 14)]) == "10⁴K and (A)⁻¹"


def test_a_raised_exponent_before_a_magnitude_letter_reads_as_a_power() -> None:
    assert read(tagged("At 10", ("4",), "K and 10", ("6",), "M and 104K.")) == (
        "At 10 to the power of 4 kelvin and 10 to the power of 6 M and 104 thousand."
    )


def test_a_raised_exponent_no_rule_reads_is_written_as_printed() -> None:
    assert read(tagged("It is 2", ("8",), " bits.")) == "It is 2⁸ bits."


def test_a_raised_minus_one_after_a_bracket_reads_as_a_power_untagged_not() -> None:
    assert read(tagged("So (I − P)", ("−1",), ", (I − P)−1 and f(x)−1.")) == (
        "So (I − P) to the power of minus 1, (I − P)−1 and f(x)−1."
    )


def test_a_raised_exponent_set_small_and_raised_in_a_pdf_reads_as_a_power() -> None:
    """No tag: the run is set small and raised, as a PDF gives it."""
    runs = [("At 10", 10.0, 100.0), ("4", 7.0, 97.0), ("K and (I − P)", 10.0, 100.0)]
    runs += [("−1", 7.0, 97.0), (".", 10.0, 100.0)]
    line, x = [], 0.0
    for text, size, top in runs:
        line.append(TextRun(text, size=size, box=Box(x, top, x + 5 * len(text), top + size)))
        x += 5 * len(text)
    text = "".join(run.text for run in line)
    page = Page(1, (TextLine("l0", tuple(line)),))
    block = Block(BlockKind.PARAGRAPH, text, (Part("l0", 0),))
    document = Document(Content(Source("a.pdf", SourceFormat.PDF), (page,)), "en", (block,))
    assert read(document) == ("At 10 to the power of 4 kelvin and (I − P) to the power of minus 1.")


def test_a_rebuilt_placeholder_keeps_its_raised_exponents_as_sup_runs() -> None:
    """The conformance check rebuilds a placeholder as printed with its run tags; a raise
    that only the size shows becomes a `sup` tag, so a second run reads the power again."""
    runs = [("P ← (I − P)", 10.0, 100.0), ("−1", 7.0, 97.0)]
    line, x = [], 0.0
    for text, size, top in runs:
        line.append(TextRun(text, size=size, box=Box(x, top, x + 5 * len(text), top + size)))
        x += 5 * len(text)
    text = "".join(run.text for run in line)
    page = Page(1, (TextLine("l0", tuple(line)),))
    block = Block(BlockKind.CODE, text, (Part("l0", 0),))
    document = Document(Content(Source("a.pdf", SourceFormat.PDF), (page,)), "en", (block,))
    rebuilt = rebuilt_from_script(document, [])
    assert raised_exponents(rebuilt) == {0: [(11, 13)]}


def test_german_reads_a_raised_exponent_before_a_glued_letter_or_after_a_bracket() -> None:
    """#815: a raised "4" after "10" reads "10 hoch 4" before a space and before a glued
    "K" ("Kelvin"), a raised "−1" after a bracket "hoch minus 1", the same on a second run;
    untagged "104K" and "(I − P)−1" stay as printed."""
    assert read_twice(tagged("Bei 10", ("4",), " und 10", ("4",), "K, nicht 104K.", ), "de") == (
        "Bei 10 hoch 4 und 10 hoch 4 Kelvin, nicht 104K.",
        "Bei 10 hoch 4 und 10 hoch 4 Kelvin, nicht 104K.",
    )  # fmt: skip
    assert read_twice(tagged("Mit (I − P)", ("−1",), ", (I − P)−1 hier."), "de") == (
        "Mit (I − P) hoch minus 1, (I − P)−1 hier.",
        "Mit (I − P) hoch minus 1, (I − P)−1 hier.",
    )


@pytest.mark.parametrize(
    "printed",
    [
        # a letter after it may go on the power: `_BRACKET_POWER`'s lookahead, and
        # `_unit_left_alone` as well (the x also `_x_left_alone`)
        "Mit (I − P)⁻¹x hier.",
        "Mit (I − P)⁻¹y hier.",
        "Mit (I − P)⁻¹,5 hier.",  # a decimal joined after it: `_LABEL_JOINED_AFTER`
        # German has no magnitude letter, so the units step sets no "M" apart after a power
        # and reads none: `_unit_left_alone` keeps the power as printed
        "Bei 10⁶M Sternen.",
    ],
)
def test_german_leaves_a_power_before_a_letter_or_a_joined_number_as_printed(
    printed: str,
) -> None:
    """#815: the guards round the German powers, the same on a second run. The
    letter rows fail only with both of their guards removed; the others with theirs."""
    document = make_document([(BlockKind.PARAGRAPH, printed)], "de")
    assert read_twice(document, "de") == (printed, printed)


def test_german_reads_a_raised_exponent_set_small_and_raised_in_a_pdf_as_a_power() -> None:
    """#815: no tag, the run is set small and raised, as a PDF gives it."""
    runs = [("Bei 10", 10.0, 100.0), ("4", 7.0, 97.0), ("K und (I − P)", 10.0, 100.0)]
    runs += [("−1", 7.0, 97.0), (".", 10.0, 100.0)]
    line, x = [], 0.0
    for text, size, top in runs:
        line.append(TextRun(text, size=size, box=Box(x, top, x + 5 * len(text), top + size)))
        x += 5 * len(text)
    text = "".join(run.text for run in line)
    page = Page(1, (TextLine("l0", tuple(line)),))
    block = Block(BlockKind.PARAGRAPH, text, (Part("l0", 0),))
    document = Document(Content(Source("a.pdf", SourceFormat.PDF), (page,)), "de", (block,))
    assert read(document, "de") == "Bei 10 hoch 4 Kelvin und (I − P) hoch minus 1."


@given(
    st.sampled_from(["At 10", "x = 2", "So (I − P)", "and [A]", "Take A", "cells", " "]),
    st.from_regex(r"[−+-]?[0-9]{1,3}", fullmatch=True),
    st.sampled_from(["K.", "M stars.", "KB", " here.", "", "kg", ")", "2"]),
)
def test_a_raised_exponent_reads_the_same_on_a_second_run(
    before: str, raised: str, after: str
) -> None:
    """Not before a spaced unit letter or a glued "x": "A⁻¹ K" and "2⁻¹x" printed so read
    "kelvin" and "times" only on a second run, on main too (a follow-up issue)."""
    for language in ("en", "de"):
        first, second = read_twice(tagged(before, (raised,), after), language)
        assert first == second, (first, second)
