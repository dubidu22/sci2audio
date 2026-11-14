"""From the laid-out document to the listening script of the chosen chapters (Q6).

The text steps run on the whole document, whatever chapters are chosen, so the report is
complete and a chapter choice needs no second analysis. The chapter choice applies when
the script is cut into utterances: only the chosen chapters' pieces are cut, and the
report marks the edits in the other chapters as not spoken. A block a move reads elsewhere
belongs to the chapter it is read in (`StepRun.read_at`, #213).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sci2audio.app.chapters import Chapter, find_chapters, selected
from sci2audio.app.settings import JobSettings
from sci2audio.core import Document, ScriptPiece
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    DEFAULT_MAX_CHARS,
    StepContext,
    StepRun,
    TextStep,
    Utterance,
    cut_utterances,
    run_steps,
)


@dataclass(frozen=True)
class ChapterScript:
    """A chapter, whether it is chosen, and what the voice says in it (nothing if not)."""

    chapter: Chapter
    selected: bool
    utterances: tuple[Utterance, ...] = ()

    @property
    def spoken(self) -> int:
        """How many utterances the voice speaks (pauses not counted)."""
        return sum(not utterance.pause for utterance in self.utterances)


@dataclass(frozen=True)
class ScriptResult:
    """Everything the script job worked out for one document, before anything is written."""

    run: StepRun  # every proposed edit and what became of it; `run.document` is the document
    chapters: tuple[ChapterScript, ...]
    ignored_chapters: tuple[int, ...] = ()  # chosen indices the document doesn't have

    @property
    def document(self) -> Document:
        return self.run.document

    @property
    def utterances(self) -> tuple[Utterance, ...]:
        """Every utterance of the chosen chapters, in order."""
        return tuple(u for chapter in self.chapters for u in chapter.utterances)

    def chapter_of(self, block: int) -> ChapterScript:
        """The chapter that holds block number `block`."""
        for chapter in self.chapters:
            if chapter.chapter.holds(block):
                return chapter
        raise ValueError(f"block {block} is in no chapter")


def prepare_script(
    document: Document,
    settings: JobSettings,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> ScriptResult:
    """Run the text steps on the whole document and cut the chosen chapters' script."""
    run = run_steps(
        document,
        StepContext(language=document.language),
        steps,
        switched_off=settings.switched_off,
    )
    chapters = find_chapters(document)
    chosen, ignored = selected(chapters, settings.chapters)
    pieces = run.script()
    scripts = []
    for chapter in chapters:
        if chapter.index in chosen:
            mine = _pieces_in(chapter, pieces, run)
            utterances = cut_utterances(document, mine, max_chars=max_chars)
            scripts.append(ChapterScript(chapter, True, utterances))
        else:
            scripts.append(ChapterScript(chapter, False))
    return ScriptResult(run, tuple(scripts), ignored)


def _pieces_in(chapter: Chapter, pieces: Sequence[ScriptPiece], run: StepRun) -> list[ScriptPiece]:
    """The chapter's pieces in reading order: a block moved elsewhere (a footnote read at its
    mark, #213) belongs to the chapter it is read in, not the one it is printed in."""
    return [piece for piece in pieces if chapter.holds(run.read_at(piece.span.block))]
