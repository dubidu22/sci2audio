"""The script in memory (Q6, Q15): steps on the whole document, the chapter choice applied
when utterances are cut, edits in chapters not chosen marked as not spoken."""

from dataclasses import replace

from app_helpers import document_with
from core_strategies import documents
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.app import JobSettings, build_report, prepare_script, report_data
from sci2audio.app.job import settings_data
from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Section, Span
from sci2audio.testing import make_document
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    Stage,
    Status,
    StepContext,
    TextStep,
    cut_utterances,
)

P, H = "paragraph", "heading"


class Fixed(TextStep):
    """A step that proposes the edits it is given, and records the blocks it was shown."""

    def __init__(self, step_id, edits=(), *, stage=Stage.INLINE, category=Category.CITATIONS):  # type: ignore[no-untyped-def]
        self.id = step_id
        self.stage = stage
        self.category = category
        self.languages = ("en",)
        self.edits = [replace(edit, step=step_id) for edit in edits]
        self.seen: list[int] = []

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        self.seen = list(range(len(document.blocks)))
        return list(self.edits)


class Failing(TextStep):
    id = "broken-step"
    languages = ("en",)
    category = Category.NUMBERS_AND_UNITS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        raise RuntimeError("it broke")


def paper() -> Document:
    """Front text, two chapters and a reference list."""
    blocks = [
        (P, "A Title"),
        (H, "1 Intro"),
        (P, "We cite [1]. It works."),
        (H, "2 More"),
        (P, "See [2] here."),
        (H, "References"),
        (P, "[1] Smith. 2020."),
    ]
    sections = (
        Section("1 Intro", 1, 1, 3),
        Section("2 More", 1, 3, 5),
        Section("References", 1, 5, 7),
    )
    return document_with(blocks, sections, title="A Title")


def edit(block: int, start: int, end: int, kind=EditKind.REMOVE, replacement="") -> Edit:  # type: ignore[no-untyped-def]
    return Edit(Span(block, start, end), kind, "a test", "x", replacement)


def test_the_steps_see_every_block_whatever_chapters_are_chosen() -> None:
    step = Fixed("cite", [edit(2, 8, 12), edit(4, 4, 8), edit(6, 0, 3)])
    result = prepare_script(paper(), JobSettings(chapters=frozenset({1})), [step])
    assert step.seen == list(range(7))
    assert len(result.run.outcomes) == 3
    assert all(o.status is Status.ACCEPTED for o in result.run.outcomes)


def test_only_the_chosen_chapters_are_cut_into_utterances() -> None:
    result = prepare_script(paper(), JobSettings(chapters=frozenset({1})), [])
    assert [c.selected for c in result.chapters] == [False, True, False, False]
    assert [u.text for u in result.utterances] == ["1 Intro", "We cite [1].", "It works."]
    assert all(c.utterances == () for c in result.chapters if not c.selected)


def test_the_default_choice_leaves_out_the_reference_list() -> None:
    result = prepare_script(paper(), JobSettings(), [])
    assert [c.selected for c in result.chapters] == [True, True, True, False]
    assert result.chapters[3].chapter.references
    assert all(u.span.block < 5 for u in result.utterances)


def test_edits_in_chapters_not_chosen_are_reported_as_not_spoken() -> None:
    step = Fixed("cite", [edit(2, 8, 11), edit(4, 4, 8), edit(6, 0, 3)])
    result = prepare_script(paper(), JobSettings(chapters=frozenset({1})), [step])
    report = build_report(result, settings_data(JobSettings()))
    assert [(e.chapter, e.spoken) for e in report.edits] == [(1, True), (2, False), (3, False)]
    citations = next(c for c in report.counts if c.category is Category.CITATIONS)
    assert (citations.applied, citations.not_spoken) == (1, 2)
    assert [u.text for u in result.utterances] == ["1 Intro", "We cite .", "It works."]


def test_unknown_chapters_are_ignored_with_a_warning() -> None:
    result = prepare_script(paper(), JobSettings(chapters=frozenset({0, 9})), [])
    assert result.ignored_chapters == (9,)
    report = build_report(result, {})
    assert report.warnings == (
        "chapter 9 was chosen, but the document has chapters 0 to 3 only; ignored",
    )


def test_a_failing_step_and_an_ask_edit_never_stop_the_run() -> None:
    asking = Fixed("unsure", [edit(2, 8, 11, EditKind.ASK, "one")])
    result = prepare_script(paper(), JobSettings(), [asking, Failing()])
    report = build_report(result, {})
    assert report.problems == (("broken-step", "RuntimeError: it broke"),)
    (entry,) = report.edits
    assert (entry.kind, entry.said, entry.spoken) == (EditKind.ASK, "[1]", True)
    assert "We cite [1]." in [u.text for u in result.utterances]


def test_set_aside_edits_are_listed_with_the_edit_that_won() -> None:
    first = Fixed("first", [edit(2, 8, 11, EditKind.REPLACE, "one")])
    second = Fixed("second", [edit(2, 3, 11)])
    result = prepare_script(paper(), JobSettings(), [first, second])
    report = build_report(result, {})
    assert [e.status for e in report.edits] == [Status.ACCEPTED, Status.SET_ASIDE]
    won_by = report.edits[1].won_by
    assert won_by is not None
    assert won_by[0] == "first"
    assert won_by[2].span == Span(2, 8, 11)
    data = report_data(report)["edits"][1]
    assert data["won_by"] == {
        "step": "first",
        "kind": "replace",
        "block": 2,
        "start": 8,
        "end": 11,
        "page": 1,
        "printed_page": "",
    }


def test_switched_off_categories_are_reported_and_not_applied() -> None:
    step = Fixed("cite", [edit(2, 8, 12)])
    settings = JobSettings(switched_off=frozenset({Category.CITATIONS}))
    result = prepare_script(paper(), settings, [step])
    report = build_report(result, {})
    assert report.edits[0].status is Status.SWITCHED_OFF
    assert not report.edits[0].spoken
    assert "We cite [1]." in [u.text for u in result.utterances]


def test_a_pause_shows_in_the_report_and_the_utterances() -> None:
    step = Fixed("breath", [edit(2, 12, 12, EditKind.PAUSE)])
    result = prepare_script(paper(), JobSettings(), [step])
    report = build_report(result, {})
    assert (report.edits[0].original, report.edits[0].said) == ("", "[pause]")
    assert [u.pause for u in result.chapters[1].utterances] == [False, False, True, False]
    assert result.chapters[1].spoken == 3


Run = tuple[Document, list[Edit], frozenset[int] | None]

_TEXT = st.text(alphabet="ab C. ,!\n", min_size=1, max_size=40).filter(str.strip)
_KINDS = st.sampled_from(["paragraph", "paragraph", "heading", "furniture", "footnote"])


@st.composite
def edits_in(draw: st.DrawFn, document: Document) -> list[Edit]:
    """Two to eight edits on random blocks: removals, replacements and pauses."""
    edits = []
    for _ in range(draw(st.integers(2, 8))):
        block = draw(st.integers(0, len(document.blocks) - 1))
        length = len(document.blocks[block].text)
        start = draw(st.integers(0, length))
        end = draw(st.integers(start, length))
        kind = draw(st.sampled_from([EditKind.REMOVE, EditKind.REPLACE, EditKind.PAUSE]))
        if kind is EditKind.PAUSE:
            edits.append(edit(block, start, start, kind))
        elif end > start:
            replacement = "said" if kind is EditKind.REPLACE else ""
            edits.append(edit(block, start, end, kind, replacement))
    return edits


@st.composite
def chaptered(draw: st.DrawFn) -> Run:
    """A document with two to five top-level sections (and maybe front text), edits in
    random blocks, and a choice drawn from its own chapter indices (sometimes with an
    index it doesn't have, sometimes the default)."""
    count = draw(st.integers(2, 12))
    blocks = [(draw(_KINDS), draw(_TEXT)) for _ in range(count)]
    starts = sorted(draw(st.sets(st.integers(0, count - 1), min_size=2, max_size=5)))
    ends = [*starts[1:], count]
    sections = tuple(Section(blocks[a][1], 1, a, b) for a, b in zip(starts, ends, strict=True))
    document = document_with(blocks, sections, title="T")
    chapters = len(starts) + (starts[0] > 0)
    chosen = {index for index in range(chapters) if draw(st.booleans())}
    if len(chosen) in (0, chapters) and draw(st.sampled_from([True] * 9 + [False])):
        chosen ^= {draw(st.integers(0, chapters - 1))}  # mostly a partial choice
    if draw(st.sampled_from([False] * 9 + [True])):
        chosen |= {chapters + draw(st.integers(0, 3))}  # an index the document doesn't have
    choice = None if draw(st.sampled_from([False] * 9 + [True])) else frozenset(chosen)
    return document, draw(edits_in(document)), choice


@st.composite
def anything(draw: st.DrawFn) -> Run:
    """Any document the core strategies make, with edits and any choice."""
    document = draw(documents())
    edits = draw(edits_in(document)) if document.blocks else []
    return document, edits, draw(st.none() | st.frozensets(st.integers(0, 8)))


def check_chapter_choice(run: Run) -> None:
    document, edits, chapters = run
    steps = [*BUILT_IN_STEPS, *(Fixed(f"s{n}", [e]) for n, e in enumerate(edits))]
    result = prepare_script(document, JobSettings(chapters=chapters), steps)
    everything = cut_utterances(document, result.run.script())
    chosen = {c.chapter.index for c in result.chapters if c.selected}
    expected = tuple(
        u for u in everything if result.chapter_of(u.span.block).chapter.index in chosen
    )
    assert result.utterances == expected
    report = build_report(result, {})
    for entry in report.edits:
        chapter = result.chapters[entry.chapter]
        assert chapter.chapter.holds(entry.where.span.block)
        assert entry.spoken == (entry.status is Status.ACCEPTED and chapter.selected)
    total = sum(c.applied + c.not_spoken + c.set_aside + c.switched_off for c in report.counts)
    assert total == len(report.edits) == len(result.run.outcomes)


@given(chaptered())
def test_cutting_the_chosen_chapters_equals_cutting_all_and_dropping_the_rest(run: Run) -> None:
    check_chapter_choice(run)


@given(anything())
def test_the_chapter_choice_holds_on_any_document(run: Run) -> None:
    check_chapter_choice(run)


@given(documents())
def test_the_built_in_steps_always_prepare_a_script(document: Document) -> None:
    result = prepare_script(document, JobSettings(), BUILT_IN_STEPS)
    report = build_report(result, {})
    assert report.problems == ()
    # every edit comes from a built-in step (since #64 they edit more than furniture: notes,
    # placeholders, the reference list), and the default job leaves no note out (D-142)
    ids = {step.id for step in BUILT_IN_STEPS}
    for entry in report.edits:
        assert entry.step in ids
    assert all(o.status is not Status.ACCEPTED for o in result.run.outcomes
               if o.edit.step == "footnote-texts")  # fmt: skip


def test_a_default_job_reads_each_note_and_footnote_texts_leaves_them_out() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "Body."),
                              Block(BlockKind.FOOTNOTE, "1 A note.", label="1")])  # fmt: skip
    read = [u.text for u in prepare_script(document, JobSettings()).utterances]
    assert "Footnote 1." in read
    everything = JobSettings(switched_off=frozenset())  # Footnote texts turned on
    assert [u.text for u in prepare_script(document, everything).utterances] == ["Body."]
