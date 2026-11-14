# ruff: noqa: RUF001  (dashes, quotes and symbols are meant as papers print them)
"""Citations: asides removed, citations the sentence needs read briefly (TP-03, TP-04, K2,
#66, D-171 to D-173).

Unit cases for numeric and author-year citations with the exact spans, replacements and
reasons, the brackets that are not citations, and Hypothesis properties on sentences built
around citations.
"""

import re

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import Block, BlockKind, Edit, EditKind, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import (
    Category,
    CitationStep,
    Stage,
    StepContext,
    run_steps,
    spoken_text,
)
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


def test_the_step_reads_english_and_german_and_its_switch_reads_citations_as_printed() -> None:
    assert (STEP.languages, STEP.category, STEP.stage) == (
        ("en", "de"),  # German since #101
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
        ("Algorithm [5] runs.", "Algorithm [5] runs."),
        # ... but only a capitalised label word: these are citations (review round 2, R2-2)
        ("the EM algorithm [5] works.", "the EM algorithm works."),
        ("the Schrödinger equation [4] holds.", "the Schrödinger equation holds."),
        ("Bayes' theorem [3] holds.", "Bayes' theorem holds."),
        ("the first step [7] holds.", "the first step holds."),
        # "Reference" and "References" are read along, as "Ref." is (KB review, K5)
        ("As discussed in Reference [12], it holds.", "As discussed in reference 12, it holds."),
        ("References [3, 5] show it.", "References 3 and 5 show it."),
        ("the reference [52] list", "the reference list"),
        ("It works. [12] showed it.", "It works. Reference 12 showed it."),
    ],
)  # fmt: skip
def test_no_removal_leaves_doubled_marks_or_a_wrong_capital(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #271: the outer bracket is judged on what it reads once its inner citations go
        ("Noise matters ((Smith, 2019) Jones, 2020). Then", "Noise matters. Then"),
        ("Noise matters (see (Smith, 2019) Jones, 2020). Then", "Noise matters. Then"),
        ("Noise matters ((Smith, 2019)). Then", "Noise matters. Then"),
        ("Noise matters (((Smith, 2019) Jones, 2020) Brown, 2021). Then", "Noise matters. Then"),
        # as the subject its names stay, as for one citation
        ("((Smith, 2019) Jones, 2020) is cited.", "Jones is cited."),
        ("(((Smith, 2019) Jones, 2020) Brown, 2021) is cited.", "Brown is cited."),
        ("such as ((Smith, 2019) Jones and Lee, 2020) could", "such as Jones and Lee could"),
        # prose once the inner citation is read: the bracket stays (D-541)
        ("It holds ((Smith, 2019) see Table 2) here.", "It holds (Smith see Table 2) here."),
        ("It holds (see also (Smith, 2019); Jones, 2020).", "It holds (see also)."),
        # numeric citations inside are read in too (review round 1, M1)
        ("It holds ((Smith, 2019) [3] Jones, 2020) here.", "It holds here."),
        ("It holds ([1] Jones, 2020) here.", "It holds here."),
        # an inner reading in words goes in as a second run sees it ... (S1)
        ("It holds (see (Smith, 2019; Lee, 2020), 2020) here.", "It holds here."),
        # ... unless it is longer than the printed bracket: then this one stays (S1)
        ("It holds ([3] found it) here.", "It holds (reference 3 found it) here."),
        # a page glued after the nest goes with it (S2)
        ("It holds ((Smith, 2019) Jones, 2020)[p. 5] here.", "It holds here."),
    ],
)  # fmt: skip
def test_a_nested_citation_reads_the_same_on_a_second_run(printed: str, said: str) -> None:
    once = read(printed)
    assert once == said
    assert read(once) == once


def read_all(text: str, language: str = "en") -> str:
    """The whole chain of built-in steps."""
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    return spoken_text(run_steps(document, StepContext(language), strict=True).script())


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # a nest as the subject whose inner citation keeps its names (review round 2, M1)
        ("en", "(see (Smith, 2019) 2020) found it.", "Smith found it."),
        ("en", "(see (Smith, 2019; Lee, 2020) 2021) found it.", "Smith and Lee found it."),
        ("en", "(cf. (Smith, 2020) 2020) is cited.", "Smith is cited."),
        ("en", "(cf. (Smith, 2020) (Lee, 2019) 2020) is cited.", "Smith is cited."),
        ("en", "(see (Smith, 2020) [1] 2020) is cited.", "Smith is cited."),
        ("en", "It holds ((cf. (Smith, 2020) [1] 2020) the) here.", "It holds (Smith the) here."),
        ("en", "(see (Smith, 2019) and Lee, 2020) found it.", "Smith and Lee found it."),
        ("en", "(Brown and (Smith, 2019) Jones, 2020) found it.", "Brown and Jones found it."),
        ("de", "(vgl. (Müller, 2019) 2020) zeigt das.", "Müller zeigt das."),
        ("de", "wie (vgl. (Müller, 2019) 2020) zeigt", "wie Müller zeigt"),
        ("de", "Es gilt ((vgl. (Weber, 2020) [1] 2020) das) hier.", "Es gilt (Weber das) hier."),
        # a page glued to an inner citation goes with it (review round 2, M2)
        ("en", "It holds ((Smith, 2019)[p. 4] Jones, 2020) here.", "It holds here."),
        ("de", "Es gilt ((Müller, 2019)[S. 4] Schmidt, 2020) hier.", "Es gilt hier."),
    ],
)  # fmt: skip
def test_a_nest_that_keeps_inner_names_reads_the_same_on_a_second_run(
    language: str, printed: str, said: str
) -> None:
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once


_LEAVES = st.sampled_from(
    ["(Smith, 2019)", "(Smith, 2019; Lee, 2020)", "[3]", "(Smith, 2019)[p. 4]", "(2019)"]
)
_NESTS = st.recursive(
    _LEAVES,
    lambda inner: st.builds(
        "({}{}{})".format,
        st.sampled_from(["", "see ", "cf. ", "vgl. ", "Brown and "]),
        inner,
        st.sampled_from(["", " Jones, 2020", " 2020", ", Lee, 2020", "; Lee, 2021", " the"]),
    ),
    max_leaves=4,
)


@given(
    st.sampled_from(["It holds ", "", "such as ", "wie "]),
    _NESTS,
    st.sampled_from([" found it.", " is cited.", " here.", ")", " zeigt das."]),
    st.sampled_from(["en", "de"]),
)
def test_a_nest_reads_balanced_and_the_same_on_a_second_run(
    before: str, nest: str, after: str, language: str
) -> None:
    """Review round 2 of #279, M1: a nest's edits crossed its inner bracket's, and settling
    them left a stray ")"."""
    text = before + nest + after
    once = read_all(text, language)
    assert once.count("(") - once.count(")") == text.count("(") - text.count(")"), (text, once)
    assert read_all(once, language) == once, (text, once)


def test_an_empty_nest_as_the_subject_is_still_read_as_empty_brackets() -> None:
    """Today's reading, stable but empty: nothing is left to name (#278 fixes it; S3)."""
    once = read("((Smith, 2019)) is cited.")
    assert once == "() is cited."
    assert read(once) == once


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #285, D-547: an identifier alone in brackets is not read
        ("the IGERT program (0801700) and", "the IGERT program and"),
        ("the Simons Society of Fellows (527794). Many", "the Simons Society of Fellows. Many"),
        ("the NSF (grant no. DMS-1912345) and", "the NSF and"),
        ("the NIH (0801700, 527794) and", "the NIH and"),
        ("the NIH (0801700 and 527794) and", "the NIH and"),
        ("(Award 1912345) Then", "Then"),
        ("sample (12345) here", "sample here"),  # an ungrouped count goes too (D-547)
        # years, small numbers, grouped or labelled quantities, short-number names stay
        ("The year (2019) was", "The year (2019) was"),
        ("cases (12,345) and (12 345) here", "cases (12,345) and (12 345) here"),
        ("cases (n = 12345) here", "cases (n = 12345) here"),
        ("the (OPP-115) and (COVID-19) data", "the (OPP-115) and (COVID-19) data"),
        ("the (GPT-3) data", "the (GPT-3) data"),
        ("the (ISO 9001) and (ResNet-50) data", "the (ISO 9001) and (ResNet-50) data"),
        ("see (3) and (12)", "see (3) and (12)"),
        ("it (see grant 527794 for details) is", "it (see grant 527794 for details) is"),
        ("it (12345 participants) is", "it (12345 participants) is"),
        ("it (5 %) is", "it (5 %) is"),
    ],
)  # fmt: skip
def test_an_identifier_in_brackets_is_not_read(printed: str, said: str) -> None:
    once = read(printed)
    assert once == said
    assert read(once) == once


def test_an_identifier_says_why_it_is_not_read() -> None:
    (edit,) = edits("the program (0801700) and")
    assert edit.kind is EditKind.REMOVE
    assert edit.reason.startswith('identifier "(0801700)"')


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # #285 review round 1, R1-2: the other brackets are judged as a second run sees them
        ("en", "As shown by Smith (527794) (2019), it grew.", "As shown by Smith, it grew."),
        ("de", "Text (527794) (2019) mehr.", "Text mehr."),
        ("de", "Wie Müller (527794) (2019) zeigt, wuchs es.", "Wie Müller zeigt, wuchs es."),
        ("en", "Text (Smith, 2019; 527794) more.", "Text more."),
        ("en", "Text (527794; Smith, 2019) more.", "Text more."),
        ("de", "Text (Müller, 2019; 527794) mehr.", "Text mehr."),
        ("en", "(Smith, 2019; 527794) found it.", "Smith found it."),
        ("en", "It grew (527794; (Smith, 2019) Jones, 2020) fast.", "It grew fast."),
        # R1-3: a bracket left with only lead words goes whole
        ("en", "Text (see (527794)) more.", "Text more."),
        ("en", "Text (cf. (527794)) more.", "Text more."),
        ("en", "Text (e.g., (527794)) more.", "Text more."),
        ("de", "Text (siehe (527794)) mehr.", "Text mehr."),
        ("de", "Text (vgl. (527794)) mehr.", "Text mehr."),
        ("en", "Text (see) more.", "Text (see) more."),  # no identifier went: as before
        # a separator at the bracket's edge stays for now, the same on both runs (#305)
        ("en", "Text ((527794); 2019) more.", "Text (; 2019) more."),
    ],
)  # fmt: skip
def test_a_removed_identifier_leaves_the_other_brackets_as_a_second_run_reads_them(
    language: str, printed: str, said: str
) -> None:
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once


def test_a_bracket_of_lead_words_says_why_it_goes() -> None:
    reasons = [edit.reason for edit in edits("Text (see (527794)) more.")]
    assert reasons == ['bracket of lead words "(see)" is not read (TP-03)']


_IDENTIFIERS = st.sampled_from(
    [
        "(527794)",
        "(grant no. DMS-1912345)",
        "(0801700, 527794)",
        "(FKZ 01IS18026A)",
        "(Projekt 12.345)",
        "(12.345-mal)",
    ]
)


@st.composite
def _with_identifiers(draw: st.DrawFn) -> tuple[str, str]:
    """A text of citations, nested and side by side, and the same text with identifier
    brackets put in next to its brackets and inside them."""
    base = (
        draw(st.sampled_from(["As shown by Smith ", "It holds ", "", "such as ", "wie Müller "]))
        + " ".join(draw(st.lists(_NESTS, min_size=1, max_size=2)))
        + draw(st.sampled_from([" found it.", ", it grew.", " here.", ")", ". Then"]))
    )
    places = [
        at
        for at in range(len(base) + 1)
        if at == 0 or base[at - 1] in " (" or (at < len(base) and base[at] == ")")
    ]
    text = base
    chosen = draw(st.lists(st.sampled_from(places), min_size=1, max_size=2, unique=True))
    for at in sorted(chosen, reverse=True):
        found = draw(_IDENTIFIERS)
        put = f" {found}" if at < len(text) and text[at] == ")" else f"{found} "
        text = text[:at] + put + text[at:]
    return base, text


@given(_with_identifiers(), st.sampled_from(["en", "de"]))
def test_identifier_brackets_add_no_second_run_change(case: tuple[str, str], language: str) -> None:
    """#285 review round 1, R1-1 and R1-2: removing an identifier changed how the brackets
    next to it or around it were read on a second run. A text that reads the same on a
    second run without identifiers does so with them."""
    base, text = case
    plain = read_all(base, language)
    assume(read_all(plain, language) == plain)  # nests that break without one are #306's
    once = read_all(text, language)
    assert read_all(once, language) == once, (text, once)


def test_a_deep_nest_of_brackets_does_not_crash() -> None:  # M3
    text = "(" * 5000 + "Smith, 2019" + ")" * 5000
    document = make_document([(BlockKind.PARAGRAPH, text)])
    check_text_step(STEP, [document], allow_ask=False)


@pytest.mark.parametrize(
    ("unit", "count"),
    [
        ("[1] ", 25_000),
        ("Smith (2019) shows it [3]. ", 4000),
        ("Text ((Smith, 2019) Jones, 2020) here. ", 6000),  # #271: each nest judged on its own
        # #285 review round 1: the second look at a text without its identifiers
        ("Smith (527794) (2019) and (see (527794)) here. ", 2000),
    ],
    ids=["numeric", "author-year", "nests", "identifiers"],
)
def test_a_long_block_takes_linear_time(unit: str, count: int) -> None:  # S2: 100,000 characters
    # 8 times the text against a base run (#276); it took 17 s for 80,000 characters before
    assert_linear(edits, lambda n: unit * n, count)


def test_a_very_long_bracket_is_not_parsed() -> None:
    text = "x (" + "Smith, 2019; " * 400 + "Lee, 2020) y"
    assert edits(text) == []


@pytest.mark.parametrize(
    ("text", "spoken"),
    [  # #110, D-448: after an article the word before a year bracket names a thing
        ("the Olympics (2016) were held", "the Olympics (2016) were held"),
        ("A Workshop (2019) was held.", "A Workshop (2019) was held."),
        ("an Olympiad (2014) took place", "an Olympiad (2014) took place"),
        # ... unless "et al." or a second author shows a citation
        ("the Smith et al. (2019) study", "the Smith et al. study"),
        ("the Smith and Jones (2019) model", "the Smith and Jones model"),
        # no article: a narrative citation, as before
        ("As Smith (2019) shows, it holds.", "As Smith shows, it holds."),
    ],
)
def test_a_year_bracket_after_an_article_and_a_word_is_read(text: str, spoken: str) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    ("text", "spoken"),
    [  # #145, D-447: lead words and a narrative citation in a bracket go whole
        ("( see Smith (2019))", ""),
        ("It holds. (see Smith (2019))", "It holds."),
        ("It holds [12]. (See Smith (2019).)", "It holds."),
        ("It holds. (e.g., Smith et al. (2019).) Then", "It holds. Then"),
        # a full stop inside a bracket inside a sentence ends that sentence: left alone
        ("It holds (see Smith et al., 2019.)", "It holds (see Smith et al., 2019.)"),
        ("It holds (Smith, 2019.) Then", "It holds (Smith, 2019.) Then"),
        # "n.d." ends in a full stop that is no sentence end
        ("Cubic (Smith, n.d.).", "Cubic."),
    ],
)
def test_a_bracket_of_lead_words_and_a_narrative_citation_goes_whole(
    text: str, spoken: str
) -> None:
    assert read(text) == spoken


@pytest.mark.parametrize(
    "text",
    [  # #151, D-450: every form the statistics step reads as a confidence interval
        "the CI: [1, 3].",
        "the CI = [1, 3].",
        "two CIs [1, 3] and [2, 4].",
        "the CIs [1, 3], [2, 4] and [5, 6] hold.",
        "the CIs [1, 3], and [2, 4] hold.",
        "95% CI [1, 3] or [2, 4] here.",
    ],
)
def test_confidence_intervals_in_every_form_are_not_citations(text: str) -> None:
    assert edits(text) == []


def test_a_bracket_joined_on_after_a_citation_is_still_a_citation() -> None:
    assert read("noise [12] and [13] here.") == "noise and reference 13 here."


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
        # ... and a year after an article and a word: "the Smith (2019)" (D-448, #110)
        assert (
            left.group() in LEFT_ALONE
            or re.search(r"(?:[=∈]|CI)\s*\Z", before)
            or re.search(r"(?<!\S)the\s+Smith\s*\Z", before)
        ), (text, spoken)
    # every word outside the citations is still read, in order
    # a bracket of lead words and citations goes whole: "( see [12])", "( [12], see [3])"
    # (D-172), and so does one of lead words and a narrative citation: "( e.g., Smith
    # (2019))" (D-447, #145)
    lead = r"(?:[\s,;]|see|also|e\.g\.,)*"
    outside = re.sub(rf"\({lead}(?:\[\d[\d,;–\s-]*\]{lead})+\)", " ", text)
    outside = re.sub(r"\((?:\s|see|also|e\.g\.,)*Smith\s\(2019\)\s*\)", " ", outside)
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
