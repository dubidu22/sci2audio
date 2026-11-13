"""Planning the audio (D-116, D-157, D-155): which chunks the voice speaks, the pause kind
before each, the output chapters, and how a skipped utterance is left out."""

from __future__ import annotations

from dataclasses import replace

from app_helpers import document_with
from core_strategies import documents, edits_on, overlaps, spans_in
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.app import JobSettings, chunk_key, plan_audio, prepare_script
from sci2audio.app.audio import assemble, audiobook_files, book_info
from sci2audio.core import Document, Edit, EditKind, Metadata, Section, Span
from sci2audio.output import OutputSettings, Pause
from sci2audio.output.names import book_name
from sci2audio.output.timeline import check_chapters
from sci2audio.textprep import Category, Stage, StepContext, TextStep

P, H = "paragraph", "heading"


class Fixed(TextStep):
    """A step that proposes the edits it is given."""

    id = "fixed"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def __init__(self, edits: list[Edit]) -> None:
        self.edits = [replace(edit, step=self.id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


def plan(document: Document, steps=(), settings=None, max_chars=300):  # type: ignore[no-untyped-def]
    result = prepare_script(document, settings or JobSettings(), steps, max_chars)
    return result, plan_audio(result, engine="fake", engine_version="1", voice="v", speed=1.0)


def paper() -> Document:
    blocks = [
        (P, "A Title"),
        (H, "1 Intro"),
        (P, "One here. Two here."),
        (P, "Three here."),
        (H, "2 More"),
        (P, "Four here."),
        (H, "References"),
        (P, "[1] Smith. 2020."),
    ]
    sections = (
        Section("1 Intro", 1, 1, 4),
        Section("2 More", 1, 4, 6),
        Section("References", 1, 6, 8),
    )
    return document_with(blocks, sections, title="A Title")


def test_pause_kinds_follow_blocks_headings_and_sentences() -> None:
    _, made = plan(paper())
    assert [(c.chapter, c.utterance.text, c.pause) for c in made.chunks] == [
        (0, "A Title", Pause.PARAGRAPH),
        (1, "1 Intro", Pause.PARAGRAPH),  # a chapter's first chunk: output's chapter pause
        (1, "One here.", Pause.HEADING),
        (1, "Two here.", Pause.SENTENCE),
        (1, "Three here.", Pause.PARAGRAPH),
        (2, "2 More", Pause.PARAGRAPH),
        (2, "Four here.", Pause.HEADING),
    ]  # the reference list is not chosen by default
    assert made.silent == ()


def test_a_clause_cut_gets_no_pause_and_a_pause_edit_at_least_the_edit_pause() -> None:
    document = document_with([(P, "aaa bbb, ccc ddd. Eee fff."), (P, "Ggg hhh.")])
    pause = Edit(Span(0, 17, 17), EditKind.PAUSE, "a test", "x")
    _, made = plan(document, [Fixed([pause])], max_chars=12)
    assert [(c.utterance.text, c.pause) for c in made.chunks] == [
        ("aaa bbb,", Pause.PARAGRAPH),
        ("ccc ddd.", Pause.NONE),
        ("Eee fff.", Pause.PAUSE_EDIT),  # a pause edit before a sentence: the edit's pause
        ("Ggg hhh.", Pause.PARAGRAPH),
    ]
    end = Edit(Span(0, 26, 26), EditKind.PAUSE, "a test", "x")
    _, made = plan(document, [Fixed([end])], max_chars=100)
    # a pause edit at a paragraph end meets the paragraph pause: the stronger one wins
    assert [c.pause for c in made.chunks] == [Pause.PARAGRAPH, Pause.SENTENCE, Pause.PARAGRAPH]


def test_a_chosen_chapter_with_nothing_to_say_is_listed_and_gets_no_audio() -> None:
    document = paper()
    remove = Edit(Span(5, 0, 10), EditKind.REMOVE, "a test", "x")
    _, made = plan(document, [Fixed([remove, Edit(Span(4, 0, 6), EditKind.REMOVE, "t", "x")])])
    assert made.silent == (2,)
    assert {c.chapter for c in made.chunks} == {0, 1}


def test_the_same_text_twice_shares_one_chunk() -> None:
    _, made = plan(document_with([(P, "Table 2 is skipped."), (P, "Table 2 is skipped.")]))
    first, second = made.chunks
    assert first.key == second.key
    assert first.file == second.file
    assert first.utterance.span != second.utterance.span


def test_assemble_leaves_out_skipped_chunks_and_carries_their_pause() -> None:
    _, made = plan(paper())
    titles = {0: "A Title", 1: "1 Intro", 2: "2 More"}
    durations = {c.key: 1.0 for c in made.chunks}
    chapters, spoken = assemble(made, durations, titles)
    assert [(c.title, c.first) for c in chapters] == [("A Title", 0), ("1 Intro", 1), ("2 More", 5)]
    del durations[made.chunks[4].key]  # "Three here.", a paragraph start
    del durations[made.chunks[5].key]  # "2 More": chapter 2 now starts with "Four here."
    chapters, spoken = assemble(made, durations, titles)
    assert [(c.title, c.first) for c in chapters] == [("A Title", 0), ("1 Intro", 1), ("2 More", 4)]
    assert [s.pause for s in spoken] == [
        Pause.PARAGRAPH,
        Pause.PARAGRAPH,
        Pause.HEADING,
        Pause.SENTENCE,
        Pause.HEADING,
    ]
    durations.clear()
    assert assemble(made, durations, titles) == ([], [])


def test_book_info_and_the_audiobook_files_follow_outputs_naming(tmp_path) -> None:  # type: ignore[no-untyped-def]
    document = paper()
    content = replace(document.content, metadata=Metadata(title="A: Title", authors=("Ann", " ")))
    book = book_info(replace(document, content=content))
    assert (book.title, book.authors, book.language) == ("A: Title", ("Ann",), "en")
    files = audiobook_files(tmp_path, book, ["One", "Two"], OutputSettings())
    base = book_name("A: Title")
    assert [f.name for f in files] == [
        f"{base} - 01 One.mp3",
        f"{base} - 02 Two.mp3",
        f"{base}.m4b",
        f"{base}.readalong.json",
    ]
    only_m4b = audiobook_files(tmp_path, book, ["One"], OutputSettings(mp3=False))
    assert [f.name for f in only_m4b] == [f"{base}.m4b", f"{base}.readalong.json"]


def test_the_key_depends_on_text_voice_speed_and_engine_version_only() -> None:
    base = chunk_key("Hello.", "af_heart", 1.0, "kokoro", "1")
    assert base == chunk_key("Hello.", "af_heart", 1, "kokoro", "1")
    others = {
        chunk_key("Hello!", "af_heart", 1.0, "kokoro", "1"),
        chunk_key("Hello.", "bm_george", 1.0, "kokoro", "1"),
        chunk_key("Hello.", "af_heart", 1.25, "kokoro", "1"),
        chunk_key("Hello.", "af_heart", 1.0, "kokoro", "2"),
        chunk_key("Hello.", "af_heart", 1.0, "other", "1"),
    }
    assert base not in others
    assert len(others) == 5
    assert len(base) == 64
    assert int(base, 16) >= 0


# ---- properties -------------------------------------------------------------------------


@st.composite
def results(draw: st.DrawFn):  # type: ignore[no-untyped-def]
    """A script result of a random document, with random edits, chapters and a limit."""
    document = draw(documents())
    edits: list[Edit] = []
    if document.blocks:
        for _ in range(draw(st.integers(0, 6))):
            edit = draw(edits_on(draw(spans_in(document))))
            if edit.kind is EditKind.ASK:
                continue
            if not any(overlaps(edit.span, other.span) for other in edits):
                edits.append(edit)
    chosen = draw(st.none() | st.frozensets(st.integers(0, 6)))
    max_chars = draw(st.integers(1, 60))
    return prepare_script(document, JobSettings(chapters=chosen), [Fixed(edits)], max_chars)


@given(results(), st.data())
def test_every_spoken_utterance_becomes_one_chunk_in_order(result, data) -> None:  # type: ignore[no-untyped-def]
    made = plan_audio(result, engine="fake", engine_version="1", voice="v", speed=1.0)
    spoken = [
        (chapter.chapter.index, u)
        for chapter in result.chapters
        if chapter.selected
        for u in chapter.utterances
        if not u.pause
    ]
    assert [(c.chapter, c.utterance) for c in made.chunks] == spoken
    with_speech = {c.chapter for c in made.chunks}
    chosen = {c.chapter.index for c in result.chapters if c.selected}
    assert set(made.silent) == chosen - with_speech
    titles = {c.chapter.index: c.chapter.title for c in result.chapters}
    # any subset of chunks may have failed: output's chapter rules still hold
    durations = {c.key: 0.5 for c in made.chunks if data.draw(st.booleans())}
    chapters, out = assemble(made, durations, titles)
    assert [s.chunk.span for s in out] == [
        c.utterance.span for c in made.chunks if c.key in durations
    ]
    if out:
        check_chapters(chapters, len(out))
        assert len(chapters) == len({c.chapter for c in made.chunks if c.key in durations})
    else:
        assert chapters == []
    for chunk in made.chunks:
        assert chunk.file == f"chunks/{chunk.key[:2]}/{chunk.key}.wav"
