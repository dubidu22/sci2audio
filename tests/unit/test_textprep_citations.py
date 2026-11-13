# ruff: noqa: RUF001  (dashes, quotes and symbols are meant as papers print them)
"""Citations: asides removed, citations the sentence needs read briefly (TP-03, TP-04, K2,
#66, D-171 to D-173).

Unit cases for numeric and author-year citations with the exact spans, replacements and
reasons, the brackets that are not citations, and Hypothesis properties on sentences built
around citations.
"""

import re
import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Edit, EditKind, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import Category, CitationStep, Stage, StepContext, run_steps
from sci2audio.textprep.citations import brackets

EN = StepContext("en")
STEP = CitationStep()


def read(text: str, kind: BlockKind = BlockKind.PARAGRAPH) -> str:
    document = make_document([Block(kind, text)])
    lines = render(run_steps(document, EN, (STEP,), strict=True))
    return lines[0] if lines else ""


def edits(text: str) -> list[Edit]:
    return STEP.find(make_document([(BlockKind.PARAGRAPH, text)]), EN)


# ---- numeric citations (D-171, D-172) -------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("It is not representational [127]. Next.", "It is not representational. Next."),
        ("Reported before [5-12; 14], and again.", "Reported before, and again."),
        ("Found [2–6, 16, 17].", "Found."),
        ("Found [52,63,68,74].", "Found."),
        ("Found [11, 12, 20, 34, 40–\n43] too.", "Found too."),
        ("Found [12a, 12b].", "Found."),
        ("Shown before [7]; that is, also later.", "Shown before; that is, also later."),
        ("[3] Smith, J. A study.", "Smith, J. A study."),  # an entry of an unheaded list
    ],
)
def test_a_numeric_citation_that_is_an_aside_is_removed(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("Discussed in [26, 61, 86, 93, 128].", "Discussed in references 26, 61, 86, 93 and 128."),
        ("As shown by [12], it holds.", "As shown by reference 12, it holds."),
        ("As shown by [2–6], it holds.", "As shown by references 2 to 6, it holds."),
        ("Similar to [8–10, 16, 44].", "Similar to references 8 to 10, 16 and 44."),
        ("The blueprint of Refs. [53, 58].", "The blueprint of references 53 and 58."),
        ("In the sense used in Ref. [1] for it.", "In the sense used in reference 1 for it."),
        ("A thought ( [53] discusses it).", "A thought (reference 53 discusses it)."),
        ("It holds. [12] showed that.", "It holds. Reference 12 showed that."),
        ("8See [47] for discussions.", "8See reference 47 for discussions."),
        ("(see also [15] for a recent view)", "(see also reference 15 for a recent view)"),
        (
            "(see [37, 88] and references therein)",
            "(see references 37 and 88 and references therein)",
        ),
    ],
)
def test_a_numeric_citation_the_sentence_needs_is_read_as_references(
    text: str, spoken: str
) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("In philosophy [52] (see also [48, 135]), and more.", "In philosophy, and more."),
        ("Within experiences (see [113,131]). Next.", "Within experiences. Next."),
        ("Mental (cf. [23, 24]; e.g., [5]). Next.", "Mental. Next."),
    ],
)
def test_a_bracket_of_lead_words_and_citations_goes_whole(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    "text",
    [
        "p: R → [0, 1] assigning",  # after a maths sign, and it holds 0
        "x ∈ [1, 2] and y = [3, 4]",
        "95% CI [1, 3] and the interval [2, 5] or range [1, 9]",
        "Tr[⟨ρ⟩ j] and x[1] and f(x)[2]",  # glued to a word or bracket
        "rates [3e-4, 1e-4] and [1.2, 3.4] and [0]",
        "[n (−1) E ] and [S (0) E ]",
        "a list (1) and (2, 3)",  # round brackets are never numeric citations
    ],
)
def test_maths_intervals_and_data_in_brackets_are_not_citations(text: str) -> None:
    assert edits(text) == []


def test_numeric_edits_name_the_citation_as_printed() -> None:
    aside, reading = edits("Found [2–6,\n16]. Discussed in Refs. [3, 5].")
    assert aside.kind is EditKind.REMOVE
    assert aside.span == Span(0, 5, 15)
    assert aside.reason == 'numeric citation "[2–6, 16]" is not read (TP-03)'
    assert reading.kind is EditKind.REPLACE
    assert reading.replacement == "references 3 and 5"
    assert reading.reason == (
        'citation "Refs. [3, 5]" is part of the sentence: read as "references 3 and 5" (TP-04)'
    )


def test_and_so_on_makes_an_aside() -> None:
    assert read("Time, and so on [42,67]. In all.") == "Time, and so on. In all."
    assert read("Sense and reference [52]. This.") == "Sense and reference. This."


# ---- author-year citations (D-173) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("It differs from ggplot2 (Wickham, 2016). It is.", "It differs from ggplot2. It is."),
        ("Noise (Smith et al., 2019; Jones & Lee, 2020).", "Noise."),
        ("Cubic (Smith et al. 2019a, 2019b; Jones, in press).", "Cubic."),
        ("Cubic (Wilson et al., 2016a,b; Smith, n.d.).", "Cubic."),
        ("Formalism (Eisenstein, 2019, Chapter 10). Next.", "Formalism. Next."),
        ("Case (Rozenberg and Salomaa, 1997, Chapter 9).", "Case."),
        ("Runtime (Graham et al., 1980; Moore, 2000, inter alia), and", "Runtime, and"),
        ("Fine (Corazza et al.\n1994; Sánchez and Benedí 1997). See", "Fine. See"),
        ("Models (e.g., Smith & Lee, 2019; see also van der Berg, 2020).", "Models."),
        ("Tools (Pastor-Serrano & Perkó, 2021;\nRodrı́guez et al., 2020).", "Tools."),
        ("Doctors (WHO, 2020) agree.", "Doctors agree."),
        ("Astropy (Astropy Collaboration, 2013); a", "Astropy; a"),
        ("Data (McKinney, 2010) frames.", "Data frames."),
        ("Inversion (see e.g. Althoen and McLaughlin (1987)).", "Inversion."),
        ("Phrase Ellipsis (VPE)(Bos and Spenader, 2011):", "Phrase Ellipsis (VPE):"),
    ],
)
def test_a_bracket_of_citations_is_removed(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("Grammars (RNNGs; Dyer et al., 2016; Kim et al., 2019) here.", "Grammars (RNNGs) here."),
        ("Sets (Smith, 2019; the PLUE set) here.", "Sets (the PLUE set) here."),
        ("Sets (A; Smith, 2019; B) here.", "Sets (A; B) here."),
        ("Models (e.g., BERT (Devlin et al., 2019)) here.", "Models (e.g., BERT) here."),
    ],
)
def test_in_a_bracket_with_other_text_only_the_citations_go(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("As shown by Smith (2019), it holds.", "As shown by Smith, it holds."),
        ("Smith et al. (2020a) show it.", "Smith et al. show it."),
        ("Jelinek and Lafferty’s (1991) algorithm.", "Jelinek and Lafferty’s algorithm."),
        ("Baker's (1979) method.", "Baker's method."),
        ("By Bos and Spe-\nnader (2011).", "By Bos and Spe- nader."),
        ("Kocijan et al.\n(2022)[p. 8], “Solving", "Kocijan et al., “Solving"),
        ("Smith (2019, p. 4) says.", "Smith says."),
        ("Quoref (Dasigi et al. (2019); Zhang and Zhao\n(2022)) is.", "Quoref is."),
        (
            "Task (Khullar (2020), Zhang et al.\n(2019); Bos and Spe-\nnader (2011)). Next",
            "Task. Next",
        ),
    ],
)
def test_a_narrative_citation_keeps_its_names(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        (
            "It is hard. (Dasigi et al., 2019)[p. 1] note that.",
            "It is hard. Dasigi et al. note that.",
        ),
        ("(Smith, 2019; Lee, 2020) show it.", "Smith and Lee show it."),
        ("(Smith, 2019; Lee, 2020; Chen, 2021) agree.", "Smith, Lee and Chen agree."),
        (
            "Approaches such as (Qin et al., 2022) could work.",
            "Approaches such as Qin et al. could work.",
        ),
        ("As argued in (Smith, 2019), it holds.", "As argued in Smith, it holds."),
    ],
)
def test_a_bracketed_citation_the_sentence_needs_keeps_its_names(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    "text",
    [
        "revised (Aug 2013) and (March 2020)",
        "a workshop (CoNLL 2017) and ({SOUPS} 2016)",
        "dated (1931 - 1958) and (QI-2008)",
        "stamped (Dated: April 5, 2024)",
        "the 2020 census (2020) and table 2 (2019)",
        "his edition (first english edition 1973)",
        "models (e.g., BERT) and (BERT 2019)",
        "values (n = 2019) and (p < 2020)",
    ],
)
def test_dates_events_and_other_brackets_are_not_citations(text: str) -> None:
    assert edits(text) == []


def test_a_quoted_page_reference_goes() -> None:
    assert read("He wrote “it is hard” [p. 8]. Then") == "He wrote “it is hard”. Then"
    assert edits("see the section [p. 8]") == []  # not after a quotation


def test_author_year_edits_name_the_citation_as_printed() -> None:
    (narrative,) = edits("Smith et al.\n(2020)[p. 3] show it.")
    assert narrative.span == Span(0, 12, 25)
    assert narrative.reason == (
        'year of the citation "Smith et al. (2020)[p. 3]" is not read; the names stay (TP-04)'
    )
    (removed,) = edits("Noise (Smith et al., 2019;\nJones & Lee, 2020).")
    assert (
        removed.reason == 'citation "(Smith et al., 2019; Jones & Lee, 2020)" is not read (TP-03)'
    )
    opening, closing = edits("(Dasigi et al., 2019) note it.")
    assert (opening.span, closing.span) == (Span(0, 0, 1), Span(0, 14, 21))
    assert (
        opening.reason
        == closing.reason
        == (
            'citation "(Dasigi et al., 2019)" is the subject of the sentence: only its names are '
            "read (TP-04)"
        )
    )
    (mixed,) = edits("Grammars (RNNGs; Dyer et al., 2016) here.")
    assert mixed.reason == (
        'citation "Dyer et al., 2016" is not read; the rest of the brackets stays (TP-03)'
    )


def test_et_al_stays_for_the_abbreviation_step() -> None:
    assert "et al." in read("Smith et al. (2019) show it.")


def test_brackets_are_matched_as_a_tree() -> None:
    (outer,) = brackets("a (b [c] (d) e) f")
    assert (outer.open, outer.close) == (2, 14)
    assert [(c.open, c.close) for c in outer.children] == [(5, 7), (9, 11)]
    assert [(b.open, b.close) for b in brackets("x ( [1] ] y")] == [(4, 6)]
    assert brackets("a ) b ( c") == []


@pytest.mark.parametrize(
    "kind", [BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE]
)
def test_blocks_a_whole_block_edit_covers_are_skipped(kind: BlockKind) -> None:
    assert STEP.find(make_document([(kind, "noise (Smith, 2019) [3]")]), EN) == []


def test_every_other_kind_of_block_is_read_without_its_citations() -> None:
    for kind in (BlockKind.HEADING, BlockKind.CAPTION, BlockKind.LIST_ITEM, BlockKind.FOOTNOTE):
        assert read("Results [3] here.", kind) == "Results here."


def test_the_step_is_english_only_and_its_switch_reads_citations_as_printed() -> None:
    assert (STEP.languages, STEP.category, STEP.stage) == (
        ("en",),
        Category.CITATIONS,
        Stage.INLINE,
    )
    text = "Noise (Smith et al., 2019) matters [3]."
    document = make_document([(BlockKind.PARAGRAPH, text)])
    off = run_steps(document, EN, (STEP,), switched_off={Category.CITATIONS}, strict=True)
    assert render(off) == [text]


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        # M2 (review of #103): a removal never leaves two marks side by side
        ("It holds. (Smith, 2019). Then more.", "It holds. Then more."),
        ("We use it, presented by Zimmeck et al. (2019). Then more.",
         "We use it, presented by Zimmeck et al. Then more."),
        ("Kocijan et al. (2022)[p. 8], “Solving", "Kocijan et al., “Solving"),
        ("Noise matters, [3]. Then more.", "Noise matters. Then more."),
        ("Noise matters, [1] [2].", "Noise matters."),
        ("It works, e.g., (see also [48, 135]).", "It works, e.g."),
        ("[12]. Noise [12]. [12], [12].", "Noise."),
        # S3: no capital after an abbreviation; a bracket after "Eq." is its number
        ("as shown before, cf. [4], and so", "as shown before, cf. reference 4, and so"),
        ("This e.g. [3] shows it.", "This e.g. reference 3 shows it."),
        ("Eq. [3] holds and Fig. [2] too.", "Eq. [3] holds and Fig. [2] too."),
        ("It works. [12] showed it.", "It works. Reference 12 showed it."),
    ],
)  # fmt: skip
def test_no_removal_leaves_doubled_marks_or_a_wrong_capital(text: str, spoken: str) -> None:
    assert read(text) == spoken


def test_a_deep_nest_of_brackets_does_not_crash() -> None:  # M3
    text = "(" * 5000 + "Smith, 2019" + ")" * 5000
    document = make_document([(BlockKind.PARAGRAPH, text)])
    check_text_step(STEP, [document], allow_ask=False)


@pytest.mark.parametrize("text", ["[1] " * 25_000, "Smith (2019) shows it [3]. " * 4000])
def test_a_long_block_takes_linear_time(text: str) -> None:  # S2: 100,000 characters
    started = time.perf_counter()
    edits(text)
    assert time.perf_counter() - started < 5  # about 0.4 s; it took 17 s for 80,000 before


def test_a_very_long_bracket_is_not_parsed() -> None:
    text = "x (" + "Smith, 2019; " * 400 + "Lee, 2020) y"
    assert edits(text) == []


# ---- properties ------------------------------------------------------------------------------

WORDS = st.sampled_from(
    ["noise", "matters", "as", "shown", "by", "in", "see", "also", "the", "effect", "holds",
     "Smith", "and", "so", "on", "x", "=", "∈", "CI", "(", ")", "e.g.,"]
)  # fmt: skip
CITATIONS = st.sampled_from(
    [
        "[12]",
        "[2–6, 16, 17]",
        "[5-12; 14]",
        "Refs. [53, 58]",
        "(see also [48, 135])",
        "(Smith et al., 2019; Jones & Lee, 2020)",
        "(Wickham, 2016)",
        "(Eisenstein, 2019, Chapter 10)",
        "(RNNGs; Dyer et al., 2016)",
        "Smith (2019)",
        "Kocijan et al.\n(2022)[p. 8]",
        "(Dasigi et al. (2019); Zhang and Zhao\n(2022))",
        "(e.g., BERT (Devlin et al., 2019))",
        "[0, 1]",
        "(Aug 2013)",
    ]
)
ENDS = st.sampled_from([".", ",", "", ";", ". Then", ")"])
SPACE = st.sampled_from([" ", "\n"])
LEFT_ALONE = ("[0, 1]", "(Aug 2013)")


@st.composite
def sentences(draw: st.DrawFn) -> tuple[str, list[str]]:
    parts, placed = [], []
    for _ in range(draw(st.integers(1, 4))):
        parts += draw(st.lists(WORDS, max_size=4))
        if draw(st.integers(0, 3)) != 1:  # 0, the simplest draw, places one
            citation = draw(CITATIONS)
            placed.append(citation)
            parts.append(citation + draw(ENDS))
    text = ""
    for part in parts:
        text += (draw(SPACE) if text else "") + part
    return text, placed


YEAR_OR_NUMBER = re.compile(r"\((?:[^()]*\b(?:2019|2016|2022|2020)\b[^()]*)\)|\[\d[\d,;–\s-]*\]")


@given(sentences())
def test_no_citation_is_left_and_no_word_is_lost(case: tuple[str, list[str]]) -> None:
    text, placed = case
    document = make_document([(BlockKind.PARAGRAPH, text)])
    check_text_step(STEP, [document], allow_ask=False)
    spoken = " ".join(render(run_steps(document, EN, (STEP,), strict=True)))
    for left in YEAR_OR_NUMBER.finditer(spoken):  # only maths, intervals and dates stay
        before = spoken[: left.start()]
        assert left.group() in LEFT_ALONE or re.search(r"(?:[=∈]|CI)\s*\Z", before), (text, spoken)
    # every word outside the citations is still read, in order
    # a bracket of lead words and citations goes whole: "( see [12])" (D-172)
    outside = re.sub(r"\((?:\s|see|also|e\.g\.,)*\[\d[\d,;–\s-]*\]\s*\)", " ", text)
    for citation in placed:
        outside = outside.replace(citation, " ")
    outside = YEAR_OR_NUMBER.sub(" ", outside)
    words = [w.strip(".,;()") for w in outside.split()]
    said = [w.strip(".,;()") for w in spoken.split()]
    position = 0
    for word in (w for w in words if w):
        while position < len(said) and said[position] != word:
            position += 1
        assert position < len(said), (word, text, spoken)
        position += 1
    assert " ." not in spoken
    assert " ," not in spoken
    for doubled in ("..", ",.", ";."):  # ".," stays after "et al." ("et al., “Solving")
        assert spoken.count(doubled) <= text.count(doubled), (doubled, text, spoken)


@given(st.text(alphabet=st.sampled_from("([])Smith, 2019;et al.&and e.g. 12–5\n"), max_size=80))
def test_bracket_soup_keeps_the_contract(text: str) -> None:
    check_text_step(STEP, [make_document([(BlockKind.PARAGRAPH, text)])], allow_ask=False)


@given(st.text(max_size=200))
def test_any_text_keeps_the_contract(text: str) -> None:
    check_text_step(STEP, [make_document([(BlockKind.PARAGRAPH, text)])], allow_ask=False)


def test_the_generated_sentences_mostly_hold_citations() -> None:
    found = []

    @given(sentences())
    def probe(case: tuple[str, list[str]]) -> None:
        found.append(bool(case[1]))

    probe()
    assert sum(found) / len(found) > 0.6
