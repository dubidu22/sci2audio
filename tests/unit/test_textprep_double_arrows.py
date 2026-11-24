# ruff: noqa: RUF001
# (the minus sign is one of the signs next to the arrows)
"""A long double arrow printed as "=" and an arrow (#590): one arrow in both languages, on
both runs. The voices read "=⇒" as "equals" ("gleich"), which flips the meaning. Between two
operands the arrows are read as words, since the voices say nothing for them (#796)."""

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, apply_edits
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import Category, StatisticsStep, StepContext, run_steps, spoken_text


def first_and_second_run(text: str, language: str) -> tuple[str, str]:
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    context = StepContext(language)
    first = run_steps(document, context, strict=True)
    assert not first.problems
    second = run_steps(rebuilt_from_script(document, first.script()), context, strict=True)
    return spoken_text(first.script()), spoken_text(second.script())


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "So A =⇒ B, and C⇐=D iff P ⇐=⇒ Q.",
         "So A implies B, and C is implied by D iff P if and only if Q."),
        ("en", "Then X=⇒Y and Y ⇐⇒ Z.", "Then X implies Y and Y if and only if Z."),
        ("de", "Also gilt A =⇒ B und C⇐=D.", "Also gilt A daraus folgt B und C folgt aus D."),
        ("de", "Dann gilt P ⇐=⇒ Q und X=⇒Y.",
         "Dann gilt P genau dann, wenn Q und X daraus folgt Y."),
        ("de", "Für x =⇒ 3 gilt y ⇐= 5.", "Für x daraus folgt 3 gilt y folgt aus 5."),
    ],
)  # fmt: skip
def test_a_pieced_double_arrow_is_one_arrow_on_both_runs(
    language: str, printed: str, said: str
) -> None:
    first, second = first_and_second_run(printed, language)
    assert first == said
    assert second == first


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "If A ⇒ B, then B ⇐ A and A ⇔ A.",
         "If A implies B, then B is implied by A and A if and only if A."),
        ("en", "So f(x)⇒g(x) and [a]⇔¬b.", "So f(x) implies g(x) and [a] if and only if ¬b."),
        ("en", "Also p => q, p <=> q and p =>\nq.",
         "Also p implies q, p if and only if q and p implies q."),
        ("en", "A ⇒ B ⇒ C", "A implies B implies C"),
        ("en", "1234 ⇒ A and A ⇒ ¬B", "1234 implies A and A implies ¬B"),  # no count "1,234"
        ("en", "A ⇒\n=> B", "A implies implies B"),  # the reading takes the line break along
        ("de", "Wenn A ⇒ B, dann B ⇐ A und A ⇔ A.",
         "Wenn A daraus folgt B, dann B folgt aus A und A genau dann, wenn A."),
        ("de", "Also p => q und p <=> q.", "Also p daraus folgt q und p genau dann, wenn q."),
        ("de", "Für 1234 ⇒ A gilt B.", "Für 1234 daraus folgt A gilt B."),
    ],
)  # fmt: skip
def test_an_arrow_between_two_operands_is_read_as_words_on_both_runs(
    language: str, printed: str, said: str
) -> None:
    """#796: the voices say nothing for "⇒", "⇐" and "⇔"; the listener heard "A B"."""
    first, second = first_and_second_run(printed, language)
    assert first == said
    assert second == first


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    "printed",
    [
        "⇒ faster training",  # a list bullet
        "Results:\n⇒ faster\n⇒ smaller",  # bullets at line starts
        "Results: ⇒ faster.",  # after a colon
        "It shows it. ⇔",  # alone at the end
        "⇔",  # a figure label
        "A ⇒",  # no operand after it
        "x ==> y, a >=> b, c =>> d, e <==> f",  # ASCII runs that are no arrow of #796
        "a=>",
    ],
)
def test_an_arrow_standing_alone_is_not_read_as_a_word(language: str, printed: str) -> None:
    """#796: a lone arrow is no sentence word; it is left as printed (the voice is silent)."""
    first, second = first_and_second_run(printed, language)
    assert first == " ".join(printed.split())
    assert second == first


@pytest.mark.parametrize("language", ["en", "de"])
def test_an_ascii_arrow_in_a_code_block_is_not_read(language: str) -> None:
    """#796: "=>" in code (a JavaScript arrow function) stays code, also with the code notice
    switched off, when the code block's text is read as printed."""
    document = make_document([(BlockKind.CODE, "const f = x => x + 1;")], language)
    off = frozenset({Category.CODE, Category.FOOTNOTE_TEXTS})
    context = StepContext(language, switched_off=off)
    assert StatisticsStep().find(document, context) == []
    run = run_steps(document, context, switched_off=off, strict=True)
    assert spoken_text(apply_edits(document, run.accepted)) == "const f = x => x + 1;"


def test_each_arrow_edit_quotes_the_printed_arrow() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "A =⇒ B")], "en")
    [edit] = StatisticsStep().find(document, StepContext("en"))
    assert (edit.span.start, edit.span.end, edit.replacement) == (1, 5, " implies ")
    assert edit.reason == '"=⇒" read as "implies"'


_PIECES = ["A", "B", "p", "q", "y", "3.5", "f(x)", "(p", "q)", "[a]", "¬b", "is", "where", "Der",
           "⇒", "⇐", "⇔", "=⇒", "⇐=", "⇐=⇒", "⇐⇒", "=>", "<=>", "==>", "->",
           "=", "<", "≤", "±", "−", ":", ".", ",", "%", "¨"]  # fmt: skip
_GAPS = ["", " ", " ", "\n", "\u00a0", "\u00ad", "\u00ad\n"]


@st.composite
def arrow_texts(draw: st.DrawFn) -> str:
    parts = []
    for _ in range(draw(st.integers(1, 10))):
        parts += [draw(st.sampled_from(_PIECES)), draw(st.sampled_from(_GAPS))]
    return "".join(parts)


@given(arrow_texts(), st.sampled_from(["en", "de"]))
@example("e.g.=1", "en")  # #972
@example("cf.\u21d2A", "en")  # #972
@example("A \u21d0==> 3x", "de")  # #984
@example("A \u21d0==> 3x", "en")  # #984
@example("A > 3x", "en")  # #988
@example("e.g. < 3x", "en")  # #988
@example("A = \u2212 3x", "en")  # #997
def test_arrows_and_signs_read_the_same_on_a_second_run(text: str, language: str) -> None:
    """D-577 for #796: whether an arrow is read depends on nothing a first run changes."""
    first, second = first_and_second_run(text, language)
    assert second == first


_BEFORE_SIGN = ["", "A", "y", "I", "a", "B", "(a)", "f(x)", "e.g.", "z. B.", "2 s", "It is",
                "A \u21d2", "A \u21d0=", "x", "the cost"]  # fmt: skip
# "=" glued before a spaced minus ("A=\u2212 3") is a statistics difference of its own, with or
# without "Nx", so "=" and "\u2212" come here spaced apart
_SIGNS_BEFORE_NX = ["<", ">", "\u2212", "-", "=", "\u2264", "\u00b1", "<<", "<=", "->", "\u21d2",
                    "\u21d0==>", "= \u2212", "\u21d2 \u2212"]  # fmt: skip
_AFTER_NX = ["", ".", " and B.", " faster.", " here", ", and", " + 1", " \u21d2 B"]


@st.composite
def signs_before_nx(draw: st.DrawFn) -> str:
    gap = st.sampled_from(["", " "])
    return (
        draw(st.sampled_from(_BEFORE_SIGN))
        + draw(gap)
        + draw(st.sampled_from(_SIGNS_BEFORE_NX))
        + draw(gap)
        + draw(st.sampled_from(["3", "2.5", "10"]))
        + draw(st.sampled_from(["x", " x"]))
        + draw(st.sampled_from(_AFTER_NX))
    )


@given(signs_before_nx(), st.sampled_from(["en", "de"]))
@example("A < 3x", "en")  # #988
@example("e.g. > 3x", "en")  # #988
@example("A \u2212 3x", "en")  # #997
@example("A \u21d2 \u2212 3x", "en")  # #997
@example("\u2212 3x", "en")  # #997
def test_a_sign_before_nx_reads_the_same_on_a_second_run(text: str, language: str) -> None:
    """D-577 for #988 and #997: a sign before "Nx", "<", ">" and "\u2212" among them, makes it a
    variable or "N times" the same way on both runs."""
    first, second = first_and_second_run(text, language)
    assert second == first


@pytest.mark.parametrize(
    ("language", "printed"),
    [
        ("en", "such that α ⇒ · · · ⇒ β, where ⇒ marks a derivation step."),
        ("en", "The arrow ⇒ denotes implication."),
        ("en", "We write ⇒ for implication."),
        ("en", "Here ⇔ is the biconditional."),
        ("de", "wobei ⇒ einen Ableitungsschritt markiert."),
        ("de", "Der Pfeil ⇔ steht für die Äquivalenz."),
    ],
)
def test_an_arrow_named_in_prose_is_left_as_printed(language: str, printed: str) -> None:
    """#796: an arrow between two ordinary prose words is a named symbol, not a
    connective ("where ⇒ marks a derivation step" is no "where implies marks")."""
    first, second = first_and_second_run(printed, language)
    assert first == printed
    assert second == first


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "Then α ⇒ β holds.", "Then α implies β holds."),
        ("en", "So A ⇒ B and x ⇒ y.", "So A implies B and x implies y."),
        ("en", "the rule p(αXγ ⇒ αβγ) applies", "the rule p(αXγ implies αβγ) applies"),
        ("de", "Dann gilt α ⇒ β und x ⇒ y.", "Dann gilt α daraus folgt β und x daraus folgt y."),
    ],
)
def test_an_arrow_between_symbols_is_still_read(language: str, printed: str, said: str) -> None:
    first, second = first_and_second_run(printed, language)
    assert first == said
    assert second == first
