# ruff: noqa: RUF001  (dashes, quotes and symbols are meant as papers print them)
"""URLs, DOIs, arXiv identifiers and e-mail addresses are not read (TP-07, #66, D-167 to D-170).

Unit cases for every kind of link, the line-break rule and the five repair rules, with the
exact spans and reasons, and Hypothesis properties on sentences built around links.
"""

import itertools
import time
from collections import Counter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, Document, Edit, EditKind, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    LinkStep,
    Stage,
    Status,
    StepContext,
    TextStep,
    run_steps,
)
from sci2audio.textprep.links import find_links

EN = StepContext("en")
STEP = LinkStep()


def read(text: str, kind: BlockKind = BlockKind.PARAGRAPH, label: str = "") -> str:
    """What is read of one block after the links step alone."""
    from sci2audio.core import Block

    document = make_document([Block(kind, text, label=label)])
    lines = render(run_steps(document, EN, (STEP,), strict=True))
    return lines[0] if lines else ""


def edits(text: str) -> list[Edit]:
    return STEP.find(make_document([(BlockKind.PARAGRAPH, text)]), EN)


def links(text: str) -> list[str]:
    return [text[link.start : link.end] for link in find_links(text)]


# ---- what counts as a link ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("at https://github.com/JFChi/PLUE.", ["https://github.com/JFChi/PLUE"]),
        ("at http://x.org/a?b=1&c=2#top, then", ["http://x.org/a?b=1&c=2#top"]),
        ("ftp://ftp.example.org/pub/file.txt", ["ftp://ftp.example.org/pub/file.txt"]),
        ("see www.example.org/data.", ["www.example.org/data"]),
        ("see <https://example.org/a>.", ["https://example.org/a"]),
        ("(https://en.wikipedia.org/wiki/A_(b)) here", ["https://en.wikipedia.org/wiki/A_(b)"]),
        ("(see https://example.org/tool).", ["https://example.org/tool"]),
        ("“https://example.org”", ["https://example.org"]),
        ("at github.com/rycolab/prefix.", ["github.com/rycolab/prefix"]),
        ("doi:10.1000/xyz123.", ["doi:10.1000/xyz123"]),
        ("doi: 10.1000/xyz123", ["doi: 10.1000/xyz123"]),
        ("is 10.1038/s41565-023-01470-8.", ["10.1038/s41565-023-01470-8"]),
        ("on arXiv:2311.03973v2 and", ["arXiv:2311.03973v2"]),
        ("arXiv:hep-th/9901001.", ["arXiv:hep-th/9901001"]),
        ("mail j.doe@uni-example.edu.", ["j.doe@uni-example.edu"]),
        ("mailto:help@example.org.", ["mailto:help@example.org"]),
        ("{wasiahmad,yuant,kwchang}@ucla.edu", ["{wasiahmad,yuant,kwchang}@ucla.edu"]),
        (
            "{franz.nowak, ryan.cotterell}@inf.ethz.ch",
            ["{franz.nowak, ryan.cotterell}@inf.ethz.ch"],
        ),
        ("∗x.d.arsiwalla@gmail.com", ["x.d.arsiwalla@gmail.com"]),
    ],
)
def test_each_kind_of_link_is_found_without_the_sentence_punctuation(
    text: str, found: list[str]
) -> None:
    assert links(text) == found


@pytest.mark.parametrize(
    "text",
    [
        "e.g./i.e. and/or 3.5/4 Fig.2/3",
        "The ratio 10.5/2 and version 10.1/abc",  # a DOI prefix has four to nine digits
        "https:// alone, and www. too",
        "an @mention and a@b without a domain",
        "Smith et al. (2019) and [12]",
        "file.txt/x and readme.md/y",  # not a listed top-level domain
    ],
)
def test_other_text_is_not_a_link(text: str) -> None:
    assert links(text) == []


# ---- line breaks inside a link (D-170) ---------------------------------------------------


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("at https://github.\ncom/citp/policy.", "https://github.\ncom/citp/policy"),
        (
            "at https://github.com/DanHardtDK/\nellipsisGPT3.",
            "https://github.com/DanHardtDK/\nellipsisGPT3",
        ),
        (
            "is https:\n//doi.org/10.1007/s10773-024-05576-0",
            "https:\n//doi.org/10.1007/s10773-024-05576-0",
        ),
        ("https://doi.org/10.1002/acm2.\n13207", "https://doi.org/10.1002/acm2.\n13207"),
        (
            "http://www.x.se/files/Whitepaper_\nTFE_202106.pdf",
            "http://www.x.se/files/Whitepaper_\nTFE_202106.pdf",
        ),
        (
            "https://doi.org/\n10.48550/arXiv.2311.03973",
            "https://doi.org/\n10.48550/arXiv.2311.03973",
        ),
        # broken at a hyphen: the link claims the hyphen and the line break (review of #98, N1)
        (
            "https://aclanthology.org/2023.acl-\nshort.4 here",
            "https://aclanthology.org/2023.acl-\nshort.4",
        ),
        ("DOI 10.18653/v1/2023.acl-\nshort.4.", "10.18653/v1/2023.acl-\nshort.4"),
    ],
)
def test_a_link_broken_at_a_line_end_goes_on_in_the_next_line(text: str, found: str) -> None:
    assert links(text) == [found]


@pytest.mark.parametrize(
    "text",
    [
        "at https://mlco2.github.io/impact,\nbased on a total",  # a comma ends it
        "released at https://github.com/JFChi/PLUE.\nWe demonstrate it.",  # sentence ends
        "see https://example.org/a.\nthe next line",  # no "/" or digits only in the next word
        "see https://example.org/a\nand more",  # no character that cannot end a URL
    ],
)
def test_a_link_that_ends_at_a_line_end_does_not_take_the_next_line(text: str) -> None:
    (found,) = links(text)
    assert "\n" not in found


def test_a_link_broken_at_a_hyphen_is_claimed_whole_so_a_later_hyphen_rule_is_set_aside() -> None:
    class Hyphens(TextStep):
        id = "fake-hyphens"
        languages = ("en",)
        category = Category.CHARACTERS
        stage = Stage.INLINE

        def find(self, document: Document, context: StepContext) -> list[Edit]:
            text = document.blocks[0].text
            at = text.index("-\n")
            return [Edit(Span(0, at, at + 2), EditKind.REMOVE, "join", self.id)]

    for text in [
        "See it at https://aclanthology.org/2023.acl-\nshort.4.",
        "It is 10.18653/v1/2023.acl-\nshort.4.",
    ]:
        document = make_document([(BlockKind.PARAGRAPH, text)])
        run = run_steps(document, EN, (STEP, Hyphens()), strict=True)
        assert [o.status for o in run.outcomes] == [Status.ACCEPTED, Status.SET_ASIDE]


# ---- sentence repair (D-168) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        # 1. a bracket holding only the link and the words that introduce it
        ("Install it (see https://pypi.org/project/x/). Then run it.", "Install it. Then run it."),
        ("The tool (found at https://example.org/tool) works.", "The tool works."),
        ("A link <https://example.org/a>, then more.", "A link, then more."),
        ("(https://example.org) The text.", "The text."),
        # ... with a preposition before the bracket when a comma or stop follows it
        ("As shown in [https://example.org], it works.", "As shown, it works."),
        # 2. a label; the whole sentence when the label starts it and the link ends it
        ("Data are public. Contact: j.doe@uni-example.edu.", "Data are public."),
        ("Code: https://github.com/a/b. The data are public.", "The data are public."),
        ("Write to the authors (e-mail: j@x.org) for data.", "Write to the authors for data."),
        ("Jane Doe, E-mail: jd@x.org, wrote it.", "Jane Doe, wrote it."),
        ("Code: see https://x.org/a. It runs.", "It runs."),
        # 3. another colon
        ("University of Oxford: https://podcasts.ox.ac.\nuk/xerxes", "University of Oxford"),
        # 4. a preposition or verb before it
        ("The code is released at https://github.com/a/b.", "The code is released."),
        (
            "Calculated using https://mlco2.github.io/impact,\nbased on 100 hours.",
            "Calculated, based on 100 hours.",
        ),
        ("We used the tool at www.example.org to compute it.", "We used the tool to compute it."),
        ("Both are public, see also 10.5281/zenodo.1234567.", "Both are public."),
        # a short sentence or bracket a pointer word starts only points to the link
        ("It works. See https://x.org/a for details. Then more.", "It works. Then more."),
        ("Visit www.example.org.", ""),
        ("It works (see https://x.org/a for the code).", "It works."),
        # ... a longer one may say more, so only the pointer and the link go
        (
            "See https://x.org/a for the code, and note that it is slow.",
            "for the code, and note that it is slow.",
        ),
        # a comma left before a closing bracket goes too
        ("This holds (Smith, 2019, https://x.org/a).", "This holds (Smith, 2019)."),
        # 5. only the link
        ("Copenhagen Business School\ndha.msc@cbs.dk", "Copenhagen Business School"),
        ("https://example.org/a is the page.", "is the page."),
        # a run of links joined by "and" or a comma is one edit
        ("Data are at https://doi.org/10.1007/x and www.example.org/data.", "Data are."),
    ],
)
def test_the_sentence_is_repaired_around_a_removed_link(text: str, spoken: str) -> None:
    assert read(text) == spoken


def test_each_edit_names_the_link_as_printed_and_its_repair() -> None:
    text = (
        "Data are available at https://doi.org/10.1007/\ns10578 and www.example.org/data. "
        "Contact: j.doe@uni-example.edu."
    )
    first, second = edits(text)
    assert first.span == Span(0, 18, text.index(". Contact"))
    assert first.kind is EditKind.REMOVE
    assert first.reason == (
        'URLs "https://doi.org/10.1007/s10578" and "www.example.org/data" are not read; '
        '"at" before them goes too, so the sentence still reads (TP-07)'
    )
    assert second.span == Span(0, text.index(" Contact"), len(text))
    assert second.reason == (
        'e-mail address "j.doe@uni-example.edu" is not read; with the label "Contact:" the '
        "whole sentence goes (TP-07)"
    )
    assert {edit.step for edit in (first, second)} == {"links"}


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        # M1 (review of #103): a repair that reaches over a later link takes it along
        ("See https://a.org (mirror at www.b.org/x).", "(mirror)."),  # "mirror" is a word
        ("See https://a.org (or www.b.org/x) for details.", ""),
        ("It works (see https://a.org/x and also www.b.org/y).", "It works."),
        ("cf. www.b.org/y See 10.1000/xyz", ""),
        # M2: a removal at the start of a sentence takes the mark after it, not the space
        ("Foo bar. https://x.org/a. Bar baz.", "Foo bar. Bar baz."),
        ("Foo bar. https://x.org/a, then more.", "Foo bar. then more."),
        ("Foo bar. https://x.org/a.) More.", "Foo bar.) More."),
        # S1: the label takes the whole sentence only if nothing but links and their words
        # follow the link
        ("Code: https://x.org/a is where it lives.", "is where it lives."),
        ("Contact: a@b.org or see https://c.org/x.", ""),
        # S4: an e-mail domain stops before a glued sentence
        ("Write to x@ucla.edu.The end.", "Write.The end."),
        ("x@ucla.edu.The end.", "The end."),
        ("Mail X@UCLA.EDU now.", "Mail now."),
        # a pointer sentence needs a purpose after the link, or nothing
        ("See https://x.org/a on the data.", "on the data."),
    ],
)
def test_review_cases_of_the_first_round(text: str, spoken: str) -> None:
    assert read(text) == spoken


def test_merged_runs_are_one_edit_that_names_both_links() -> None:
    (edit,) = edits("It works (see https://a.org/x and also www.b.org/y).")
    assert edit.reason.startswith('URLs "https://a.org/x" and "www.b.org/y" are not read;')


def test_a_long_block_of_links_takes_linear_time() -> None:  # S2
    text = "Data at https://x.org/a and more. " * 3000  # 102,000 characters
    started = time.perf_counter()
    assert len(edits(text)) == 3000
    assert time.perf_counter() - started < 5


def test_a_pointer_sentence_names_its_pointer_word() -> None:
    (edit,) = edits("See https://x.org/a and www.x.org for details.")
    assert edit.reason == (
        'URLs "https://x.org/a" and "www.x.org" are not read; "See" starts a sentence that only '
        "points to them, so the sentence goes whole (TP-07)"
    )


def test_a_brace_group_keeps_its_spaces_in_the_reason() -> None:
    (edit,) = edits("{franz.nowak, ryan.cotterell}@inf.ethz.ch")
    assert '"{franz.nowak, ryan.cotterell}@inf.ethz.ch"' in edit.reason


def test_a_block_or_footnote_with_nothing_but_links_reads_nothing() -> None:
    assert read("https://github.com/rycolab/") == ""
    assert read("a@b.org, c@d.org") == ""
    assert read("5 https://github.com/huggingface/transformers", BlockKind.FOOTNOTE, "5") == ""
    assert read("∗x.d.arsiwalla@gmail.com", BlockKind.FOOTNOTE, "∗") == ""
    document = make_document([(BlockKind.PARAGRAPH, "(https://x.org/a)")])
    (edit,) = STEP.find(document, EN)
    assert edit.span == Span(0, 0, 17)
    assert (
        edit.reason
        == 'the text holds nothing but links ("https://x.org/a") and is not read (TP-07)'
    )


def test_a_footnote_with_text_keeps_its_text() -> None:
    text = "4The corpus is publicly available at https://github.\ncom/citp/policy."
    assert read(text, BlockKind.FOOTNOTE, "4") == "4The corpus is publicly available."


def test_two_repairs_in_one_block_never_overlap() -> None:
    text = "Data at https://a.org/x at https://b.org/y at https://c.org/z."
    found = edits(text)
    assert len(found) == 3
    assert all(a.span.end <= b.span.start for a, b in itertools.pairwise(found))


@pytest.mark.parametrize(
    "kind", [BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE]
)
def test_blocks_a_whole_block_edit_covers_are_skipped(kind: BlockKind) -> None:
    document = make_document([(kind, "see https://example.org/a")])
    assert STEP.find(document, EN) == []


def test_the_step_is_english_only_and_its_switch_reads_links_as_printed() -> None:
    assert STEP.languages == ("en",)
    assert STEP.category is Category.LINKS
    assert STEP.stage is Stage.INLINE
    text = "The code is released at https://github.com/a/b."
    document = make_document([(BlockKind.PARAGRAPH, text)])
    off = run_steps(document, EN, (STEP,), switched_off={Category.LINKS}, strict=True)
    assert render(off) == [text]
    german = make_document([(BlockKind.PARAGRAPH, text)], "de")
    assert run_steps(german, StepContext("de"), (STEP,), strict=True).not_run == ("links",)


def test_links_run_right_after_the_block_steps_and_before_citations() -> None:
    ids = [step.id for step in BUILT_IN_STEPS]
    inline = [step.id for step in BUILT_IN_STEPS if step.stage is Stage.INLINE]
    assert inline[:2] == ["links", "citations"]
    assert ids.index("links") < ids.index("citations")


# ---- properties ----------------------------------------------------------------------------

WORDS = st.sampled_from(
    ["data", "are", "the", "code", "is", "released", "available", "see", "at", "from", "and",
     "Contact:", "E-mail:", "URL:", "(see", "(", ")", "via", "using", "on", "x", "Smith"]
)  # fmt: skip
LINKS = st.sampled_from(
    [
        "https://github.com/JFChi/PLUE",
        "https://github.\ncom/citp/policy",
        "https:\n//doi.org/10.1007/s1",
        "https://doi.org/10.1002/acm2.\n13207",
        "www.example.org/data",
        "doi:10.1000/xyz123",
        "10.1038/s41565-023-01470-8",
        "arXiv:2311.03973",
        "j.doe@uni-example.edu",
        "{a,b}@x.org",
        "https://aclanthology.org/2023.acl-\nshort.4",
        "<https://example.org/a>",
    ]
)
ENDS = st.sampled_from([".", ",", ")", "", ".)", ";", ". Then"])
SPACE = st.sampled_from([" ", "\n", "  "])


@st.composite
def sentences(draw: st.DrawFn) -> tuple[str, list[str]]:
    """A text with links in it, and the links as placed."""
    parts, placed = [], []
    for _ in range(draw(st.integers(1, 4))):
        parts += draw(st.lists(WORDS, max_size=4))
        if draw(st.integers(0, 3)) != 1:  # 0, the simplest draw, places one
            link = draw(LINKS)
            placed.append(link)
            parts.append(link + draw(ENDS))
    text = ""
    for part in parts:
        text += (draw(SPACE) if text else "") + part
    return text, placed


@given(sentences())
def test_no_link_is_left_and_only_links_and_repair_words_go(case: tuple[str, list[str]]) -> None:
    text, placed = case
    document = make_document([(BlockKind.PARAGRAPH, text)])
    check_text_step(STEP, [document], allow_ask=False)
    spoken = " ".join(render(run_steps(document, EN, (STEP,), strict=True)))
    for marker in ("https", "www.", "doi:", "10.1038/", "arXiv:", "@"):
        assert marker not in spoken
    repair = {"see", "also", "at", "from", "via", "using", "on", "contact:", "e-mail:", "url:",
              "(see", "(", ")", "and", "released", "available"}  # fmt: skip
    # "released" and "available" introduce a link: "(released at https://...)" goes whole
    kept = Counter(spoken.split())
    for word in Counter(text.split()):
        if any(word.startswith(link.split()[0][:6]) for link in placed) or word.lower() in repair:
            continue
        stripped = word.rstrip(".,;)")
        if stripped and not any(stripped in link for link in placed):
            assert sum(n for w, n in kept.items() if stripped in w) >= 1, (word, text, spoken)
    assert " ." not in spoken
    assert " ," not in spoken  # the generated text has neither, so no repair may make one
    for doubled in ("..", ".,", ",.", ";."):  # a removal at a sentence start leaves none (M2)
        assert spoken.count(doubled) <= text.count(doubled), (doubled, text, spoken)


@given(st.text(max_size=200))
def test_any_text_keeps_the_contract(text: str) -> None:
    check_text_step(STEP, [make_document([(BlockKind.PARAGRAPH, text)])], allow_ask=False)


def test_the_generated_sentences_mostly_hold_links() -> None:
    # density probe (review of #83): most examples must exercise the step
    found = []

    @given(sentences())
    def probe(case: tuple[str, list[str]]) -> None:
        found.append(bool(case[1]))

    probe()
    assert sum(found) / len(found) > 0.6
