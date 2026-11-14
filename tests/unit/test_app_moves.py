"""The app with moved blocks (#213, plan Q6, Q9, Q10): a footnote printed in one chapter and
read at its mark in another belongs to the chapter it is read in, for the utterances, the
report and the audio plan."""

from dataclasses import replace

from app_helpers import document_with

from sci2audio.app import (
    JobSettings,
    build_report,
    plan_audio,
    prepare_script,
    report_data,
    report_markdown,
    script_text,
)
from sci2audio.app.job import settings_data
from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Section, Span
from sci2audio.output import Pause
from sci2audio.textprep import Category, Stage, Status, StepContext, TextStep

P, H = "paragraph", "heading"


class Fixed(TextStep):
    """A step that proposes the edits it is given."""

    languages = ("en",)
    category = Category.FOOTNOTES

    def __init__(self, step_id: str, edits: list[Edit], stage: Stage = Stage.INLINE) -> None:
        self.id = step_id
        self.stage = stage
        self.edits = [replace(edit, step=step_id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


def paper() -> Document:
    """A note marked in chapter 1 and printed in chapter 2, after the next heading."""
    blocks = [
        (P, "A Title"),
        (H, "1 Intro"),
        (P, "It works.1 It holds."),
        (H, "2 More"),
        Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
        (P, "More text."),
    ]
    sections = (Section("1 Intro", 1, 1, 3), Section("2 More", 1, 3, 6))
    return document_with(blocks, sections, title="A Title")


MARK = Edit(Span(2, 9, 10), EditKind.REMOVE, "footnote mark", "x")
INTRO = Edit(Span(4, 0, 1), EditKind.REPLACE, "introduced", "x", "Footnote 1.")
MOVE = Edit(Span(4, 0, 9), EditKind.MOVE, "read after its mark", "x", to=Span(2, 10, 10))
STEPS = [Fixed("footnotes", [MARK, INTRO]), Fixed("places", [MOVE], Stage.MOVE)]


def chapters(settings: JobSettings | None = None) -> list[list[str]]:
    result = prepare_script(paper(), settings or JobSettings(), STEPS)
    return [[u.text for u in chapter.utterances] for chapter in result.chapters]


def test_a_moved_note_is_read_in_the_chapter_of_its_mark() -> None:
    assert chapters() == [
        ["A Title"],
        ["1 Intro", "It works.", "Footnote 1.", "A note.", "It holds."],
        ["2 More", "More text."],
    ]


def test_a_moved_note_is_not_read_when_its_mark_s_chapter_is_not_chosen() -> None:
    assert chapters(JobSettings(chapters=frozenset({2}))) == [[], [], ["2 More", "More text."]]
    assert chapters(JobSettings(chapters=frozenset({1})))[1][2:4] == ["Footnote 1.", "A note."]


def test_a_move_set_aside_leaves_the_note_in_its_printed_chapter() -> None:
    texts = Fixed("footnote-texts", [Edit(Span(2, 0, 20), EditKind.REMOVE, "gone", "x")],
                  Stage.BLOCK)  # fmt: skip
    result = prepare_script(paper(), JobSettings(switched_off=frozenset()), [texts, *STEPS])
    assert result.run.outcomes[-1].status is Status.SET_ASIDE  # its target block is gone
    assert [u.text for u in result.chapters[2].utterances] == [
        "2 More",
        "Footnote 1.",
        "A note.",
        "More text.",
    ]


def test_the_report_shows_a_move_and_counts_the_note_s_edits_in_the_mark_s_chapter() -> None:
    result = prepare_script(paper(), JobSettings(chapters=frozenset({1})), STEPS)
    report = build_report(result, settings_data(JobSettings()))
    rows = [(e.kind, e.chapter, e.spoken, e.said) for e in report.edits]
    assert rows == [
        (EditKind.REMOVE, 1, True, ""),
        (EditKind.REPLACE, 1, True, "Footnote 1."),  # printed in chapter 2, heard in 1
        (EditKind.MOVE, 1, True, ""),
    ]
    move = report.edits[2]
    assert move.original == "1 A note."
    assert (move.where.span, move.to and move.to.span) == (Span(4, 0, 9), Span(2, 10, 10))
    data = report_data(report)["edits"][2]
    assert (data["kind"], data["block"], data["to"]["block"], data["to"]["start"]) == (
        "move",
        4,
        2,
        10,
    )
    assert data["to"]["page"] == 1
    assert "to" not in report_data(report)["edits"][0]
    assert "“1 A note.” → read after its mark (page 1)." in report_markdown(report)


def test_a_moved_note_gets_a_paragraph_pause_before_and_after_it() -> None:
    result = prepare_script(paper(), JobSettings(), STEPS)
    plan = plan_audio(result, engine="fake", engine_version="1", voice="v", speed=1.0)
    kinds = [(c.utterance.text, c.pause) for c in plan.chunks if c.chapter == 1]
    assert kinds == [
        ("1 Intro", Pause.PARAGRAPH),
        ("It works.", Pause.HEADING),
        ("Footnote 1.", Pause.PARAGRAPH),
        ("A note.", Pause.SENTENCE),
        ("It holds.", Pause.PARAGRAPH),
    ]


def test_the_script_file_shows_a_moved_note_on_its_own_lines() -> None:
    text = script_text(prepare_script(paper(), JobSettings(), STEPS))
    assert "It works.\n\nFootnote 1.\nA note.\n\nIt holds.\n\n# 3. 2 More" in text
