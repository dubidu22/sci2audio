"""The conformance suite every text step must pass (D-57, #6).

`check_text_step(step)` runs the step on sample documents and raises `ConformanceError`
listing everything it breaks: the declared attributes (id, languages, category, stage,
`api_version`), edit spans inside their blocks, the step's id on every edit (a reason is
enforced by `core.Edit` itself),
no overlap among its own edits, whole-block edits for a block step, moves from a move step
and nothing else (#213), the same edits for the
same input, no network access, and idempotence (run again on the text it produced, nothing
more changes; a placeholder comes back as printed, so an edit inside one is checked on a
copy whose placeholder holds the step's own output, D-710). Built-in steps also may not
propose `ask` edits in v1.0 (`allow_ask=False`).
Each run is checked twice: with nothing switched off, and with every category in
`StepContext.switched_off`, so a step that reads that field keeps the contract either way
(D-595).

Plain functions on purpose: tests wrap them, and this module never imports pytest.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sci2audio.core import (
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    FurnitureRole,
    ScriptPiece,
    Section,
    apply_edits,
    check_edits,
)
from sci2audio.testing.documents import make_document, rebuilt_from_script
from sci2audio.textprep import (
    Category,
    Stage,
    StepContext,
    TextStep,
    spoken_text,
    step_problems,
)


class ConformanceError(AssertionError):
    """A text step breaks the text-step contract; the message lists every problem."""

    def __init__(self, step: object, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        listed = "\n".join(f"- {problem}" for problem in problems)
        super().__init__(f"{step!r} breaks the text-step contract:\n{listed}")


class NetworkUsedError(RuntimeError):
    """Code inside `no_network()` tried to reach the network."""


@contextmanager
def no_network() -> Iterator[list[str]]:
    """Make every attempt to open a network connection or look up a name fail.

    Yields the list of attempts, so an attempt the code caught is still seen. Not thread
    safe: it patches the `socket` module for the duration.
    """
    attempts: list[str] = []

    def refuse(name: str) -> Callable[..., Any]:
        def refused(*args: object, **kwargs: object) -> Any:
            attempts.append(f"{name}{args[1:] if name.startswith('socket.') else args}")
            raise NetworkUsedError(f"network access is not allowed here ({name})")

        return refused

    patched = {
        (socket.socket, "connect"): refuse("socket.connect"),
        (socket.socket, "connect_ex"): refuse("socket.connect_ex"),
        (socket, "create_connection"): refuse("create_connection"),
        (socket, "getaddrinfo"): refuse("getaddrinfo"),
    }
    saved = {key: getattr(*key) for key in patched}
    try:
        for (owner, name), replacement in patched.items():
            setattr(owner, name, replacement)
        yield attempts
    finally:
        for (owner, name), original in saved.items():
            setattr(owner, name, original)


def _sample_documents() -> tuple[Document, ...]:
    furniture = [
        Block(BlockKind.FURNITURE, text, role=role)
        for text, role in [
            ("12", FurnitureRole.PAGE_NUMBER),
            ("Journal of Examples (2024) 3:1-9", FurnitureRole.RUNNING_HEAD),
            ("Licensed under CC BY 4.0", FurnitureRole.FOOTER),
            ("arXiv:2401.00001v1 [cs.CL] 2 Jan 2024", FurnitureRole.SIDE_STAMP),
            ("1\n2\n3", FurnitureRole.LINE_NUMBER),
            ("1 Introduction . . . 1", FurnitureRole.CONTENTS),
            ("Software\nReview\nRepository", FurnitureRole.SIDEBAR),
            ("Unknown furniture", None),
            ("", FurnitureRole.RUNNING_HEAD),  # a logo repeated on every page: no text
        ]
    ]
    paper = [
        Block(BlockKind.HEADING, "1 Introduction", label="1"),
        (
            BlockKind.PARAGRAPH,
            "Several studies examined noise (Smith et al., 2019; Jones & Lee, 2020),\n"
            "but findings remain inconsistent [2\u20136, 16, 17]. Exposure may affect develop-\n"
            "ment and cause diﬃculties, i.e., delays.1",
        ),
        (
            BlockKind.PARAGRAPH,
            "Data are at https://doi.org/10.1000/xyz123 and www.example.org/data.\n"
            "Contact: j.doe@uni-example.edu. In total n = 35 (p < .05, 95% CI [1.2, 3.4]);\n"
            "3.5 mg/kg at 37 °C, approx. 1,234 participants (± 12%) vs. 980 aged ≥ 18.",
        ),
        Block(BlockKind.FOOTNOTE, "1 See the appendix.", label="1"),
        (BlockKind.TABLE, "Group n Mean\nA 12 3.4\nB 15 2.9"),
        Block(BlockKind.CAPTION, "Table 1: Results by group.", describes=4, label="Table 1"),
        Block(BlockKind.FORMULA, "E = mc2 (1)", label="1"),
        (BlockKind.FIGURE, ""),
        (BlockKind.CODE, 'g = sns.relplot(data=fmri, kind="line")\ng.savefig("demo-\nplot.pdf")'),
        Block(BlockKind.LIST_ITEM, "(a) the first item", label="(a)"),
        Block(BlockKind.HEADING, "References"),
        (BlockKind.PARAGRAPH, "Smith, J. (2019). A study. Journal 1, 1\u20139. doi:10.1/abc"),
        (BlockKind.PARAGRAPH, ""),
        (BlockKind.PARAGRAPH, "  \n\t  "),
    ]
    # German (v1.1): one paragraph per German rule, written for sci2audio
    german = [
        (BlockKind.HEADING, "Einleitung"),
        (BlockKind.PARAGRAPH, "Mehrere Studien (Müller u. a., 2019) zeigen z. B. Effekte."),
        Block(BlockKind.FURNITURE, "Seite 3", role=FurnitureRole.PAGE_NUMBER),
        (
            BlockKind.PARAGRAPH,
            "Die Bun-\ndesregierung prüft während der Corona-\nPandemie die Kinder-\n"
            "und Jugendhilfe sowie die PDF-\nDatei.",
        ),
        # notices and footnotes in German (#212): a mark, its note, the placeholders
        (BlockKind.PARAGRAPH, "Die Werte stehen in der Tabelle.1"),
        Block(BlockKind.FOOTNOTE, "1 Siehe den Anhang.", label="1"),
        (BlockKind.TABLE, "Gruppe n Mittel\nA 12 3,4"),
        Block(BlockKind.CAPTION, "Tab. 1: Ergebnisse je Gruppe.", describes=6, label="Tab. 1"),
        Block(BlockKind.FORMULA, "E = mc2 (1)", label="1"),
        (BlockKind.FIGURE, ""),
        (BlockKind.CODE, "x = berechne(3, 5)  # z. B. https://example.org"),
        # links and citations in German (#101)
        (
            BlockKind.PARAGRAPH,
            "Die Daten sind unter https://example.org/daten verfügbar (abgerufen am\n"
            "12.03.2020). Kontakt: a.muster@uni-beispiel.de. Siehe https://example.org für mehr.",
        ),
        (
            BlockKind.PARAGRAPH,
            "Wie Müller (2019) zeigt, gilt das (vgl. Schmidt u. a., 2020, S. 12); siehe auch\n"
            "[3, 5] und das 95 %-KI [1,2; 3,4], nicht aber die neue Studie (2021).",
        ),
        (BlockKind.HEADING, "Literatur"),
        (BlockKind.PARAGRAPH, "Müller, A. (2019). Eine Studie. Zeitschrift 1, 1\u20139."),
    ]
    # the footnote mark after "delays." is set as a superscript; "References" heads a section
    mark = len(paper[1][1]) - 1  # type: ignore[index]
    tags = {1: [(mark, mark + 1, "sup")]}
    sections = [Section("References", 1, 10, len(paper))]
    german_mark = len(german[4][1]) - 1  # type: ignore[index]
    german_tags = {4: [(german_mark, german_mark + 1, "sup")]}
    # a title block with affiliation marks (#93), then text with a hidden run and an inline
    # page-break marker (#193)
    title = [
        Block(BlockKind.FURNITURE, "arXiv:2401.00002v1", role=FurnitureRole.SIDE_STAMP),
        (BlockKind.PARAGRAPH, "Listening to Papers"),
        (BlockKind.PARAGRAPH, "Jane Roe1,2, Ann Lee2\u2217"),
        (BlockKind.PARAGRAPH, "1Example University, 2Example Institute"),
        Block(BlockKind.FOOTNOTE, "\u2217Corresponding author.", label="\u2217"),
        (BlockKind.HEADING, "Abstract"),
        (BlockKind.PARAGRAPH, "We read 13 it aloud SECRET today."),
    ]
    title_tags: dict[int, list[tuple[int, int, str | tuple[str, ...]]]] = {
        2: [(8, 11, "sup"), (20, 21, "sup"), (21, 22, "sup")],
        3: [(0, 1, "sup"), (21, 22, "sup")],
        6: [(8, 10, ("span", "epub:pagebreak")), (20, 26, ("span", "hidden"))],
    }
    # placeholders whose printed text a step cleans, read when their notice is switched off:
    # a soft hyphen and a ligature in a formula, a ligature and a page-break marker in a
    # table, a zero-width space and a hidden run in code (#463), a line-end hyphen in a
    # figure (review B1 of PR #450, D-710); then a figure whose alt text holds a number, a
    # unit, a citation and a link, read as a paragraph is (#464)
    placeholders = [
        Block(BlockKind.FORMULA, "coe\u00adfﬁcient a = b (2)", label="2"),
        (BlockKind.TABLE, "eﬃciency n 14\nA 1 2 3"),
        (BlockKind.CODE, "x\u200b= 1 SECRET"),
        (BlockKind.FIGURE, "pre-\ntraining loss"),
        (BlockKind.PARAGRAPH, "The loss is shown above."),
        (BlockKind.FIGURE, ""),
    ]
    placeholder_tags: dict[int, list[tuple[int, int, str | tuple[str, ...]]]] = {
        1: [(11, 13, ("span", "epub:pagebreak"))],
        2: [(6, 12, ("span", "hidden"))],
    }
    placeholder_alt = {5: ["Share of 3.5 % at 12 m\u00b2 (Smith, 2019), see https://x.org"]}
    return (
        make_document([], name="empty.txt"),
        make_document(furniture, name="furniture.txt"),
        make_document(
            [*paper, *furniture],
            name="paper.txt",
            tags=tags,
            sections=sections,
            pictures={7: ["A bar chart of noise by age"]},  # a figure's alt text (#191)
        ),
        make_document(paper, "en-GB", name="paper-gb.txt", tags=tags, sections=sections),
        make_document(
            german,
            "de",
            name="german.txt",
            tags=german_tags,
            sections=[Section("Einleitung", 1, 0, 13), Section("Literatur", 1, 13, len(german))],
        ),
        make_document(title, name="title.txt", tags=title_tags),
        make_document(
            placeholders,
            name="placeholders.txt",
            tags=placeholder_tags,
            pictures=placeholder_alt,
        ),
        make_document(
            placeholders,
            "de",
            name="platzhalter.txt",
            tags=placeholder_tags,
            pictures=placeholder_alt,
        ),
    )


# documents every step is checked on: every block kind and furniture role, empty blocks,
# scientific notation, English, British English and German, a title block, hidden text, a
# figure's alt text and placeholders whose printed text a step cleans
SAMPLE_DOCUMENTS: tuple[Document, ...] = _sample_documents()


def check_text_step(
    step: TextStep,
    documents: Sequence[Document] = SAMPLE_DOCUMENTS,
    *,
    allow_ask: bool = True,
) -> None:
    """Raise ConformanceError unless the step keeps the text-step contract."""
    if problems := text_step_problems(step, documents, allow_ask=allow_ask):
        raise ConformanceError(step, problems)


def text_step_problems(
    step: TextStep,
    documents: Sequence[Document] = SAMPLE_DOCUMENTS,
    *,
    allow_ask: bool = True,
) -> list[str]:
    """Everything the step breaks on these documents; empty if it keeps the contract."""
    problems = step_problems(step)
    if problems:
        return problems  # without valid attributes the step cannot be run
    handled = [document for document in documents if step.handles(document.language)]
    if not handled:
        languages = sorted({document.language for document in documents})
        return [f"no sample document is in one of its languages {step.languages} ({languages})"]
    for document in handled:
        for off, said in ((frozenset(), ""), (frozenset(Category), ", every category off")):
            context = StepContext(document.language, switched_off=off)
            where = f"on {document.content.source.name}{said}"
            found = _run_problems(step, document, context, allow_ask)
            problems += [f"{where}: {problem}" for problem in found]
    return problems


def _run_problems(
    step: TextStep, document: Document, context: StepContext, allow_ask: bool
) -> list[str]:
    first, problems = _find(step, document, context)
    if first is None:
        return problems
    problems += _edit_problems(step, document, first, allow_ask)
    if problems:
        return problems  # later checks need valid edits
    again, more = _find(step, document, context)
    if more:
        return more
    if again != first:
        problems.append("the same document gave different edits the second time")
    script = apply_edits(document, first)
    rebuilt = rebuilt_from_script(document, script)
    second, more = _find(step, rebuilt, context)
    if second is None or more:
        return [*problems, *(f"on its own output: {problem}" for problem in more)]
    if more := _edit_problems(step, rebuilt, second, allow_ask):
        return [*problems, *(f"on its own output: {problem}" for problem in more)]
    before = _rendered(document, script)
    after = _rendered(rebuilt, apply_edits(rebuilt, second))
    # a placeholder the step edits inside came back as printed, without the run tags a
    # step may read (a hidden run, #463): the check below reads it on its own output
    inside = _edited_inside(document, first)
    for index, (was, now) in enumerate(zip(before, after, strict=True)):
        if was != now and index not in inside:
            problems.append(
                f"not idempotent: run on its own output, block {index} changed again "
                f"from {was!r} to {now!r}"
            )
    return problems + _inside_placeholder_problems(step, document, context, first, before)


def _edited_inside(document: Document, edits: Sequence[Edit]) -> set[int]:
    """The placeholders the edits change inside, not as a whole block (a notice)."""
    return {
        edit.span.block
        for edit in edits
        if (block := document.blocks[edit.span.block]).is_placeholder
        and (edit.span.start, edit.span.end) != (0, len(block.text))
    }


def _inside_placeholder_problems(
    step: TextStep,
    document: Document,
    context: StepContext,
    edits: Sequence[Edit],
    before: Sequence[str],
) -> list[str]:
    """Edits inside a placeholder that change it again when the step reads its own output.

    A second run rebuilds a placeholder as printed (D-707), so the idempotence check above
    never shows a step its own edits inside one. An edit of the whole block (a notice) is
    made from the printed block alone; an edit inside it, which cleans the text read when a
    notice is switched off (a soft hyphen, a ligature, a line-end hyphen), must change
    nothing more on a copy whose placeholder holds the step's own output (D-710).
    """
    inside = sorted(_edited_inside(document, edits))
    if not inside:
        return []
    own = rebuilt_from_script(document, apply_edits(document, edits), own_output=inside)
    again, problems = _find(step, own, context)
    if again is None or problems:
        return [f"inside a placeholder, on its own output: {problem}" for problem in problems]
    try:
        after = _rendered(own, apply_edits(own, again))
    except ValueError as error:  # SpanError and OverlappingEditsError
        return [f"inside a placeholder, on its own output: invalid edits: {error}"]
    return [
        f"an edit inside a placeholder is not idempotent: run on its own output, block "
        f"{index} changed again from {before[index]!r} to {after[index]!r} (D-710)"
        for index in inside
        if before[index] != after[index]
    ]


def _find(
    step: TextStep, document: Document, context: StepContext
) -> tuple[list[Edit] | None, list[str]]:
    with no_network() as attempts:
        try:
            edits = step.find(document, context)
        except NetworkUsedError:
            edits = None
        except Exception as error:
            return None, [f"find raised {type(error).__name__}: {error}"]
    if attempts:
        return None, [f"tried to reach the network: {', '.join(attempts)}"]
    if not isinstance(edits, list) or not all(isinstance(edit, Edit) for edit in edits):
        return None, [f"find must return a list of Edit, got {type(edits).__name__}"]
    return edits, []


def _edit_problems(
    step: TextStep, document: Document, edits: list[Edit], allow_ask: bool
) -> list[str]:
    problems = []
    for edit in edits:
        if edit.step != step.id:
            problems.append(f"an edit names step {edit.step!r}, not {step.id!r}")
        if edit.kind is EditKind.ASK and not allow_ask:
            problems.append(f"proposes an ask edit at {edit.span}; built-in steps may not")
    try:
        ordered = check_edits(document, edits)
    except ValueError as error:  # SpanError and OverlappingEditsError
        return [*problems, f"invalid edits: {error}"]
    for edit in ordered:
        if edit.kind is EditKind.MOVE and step.stage is not Stage.MOVE:
            problems.append(f"only a move step proposes moves, got one at {edit.span}")
        elif edit.kind is not EditKind.MOVE and step.stage is Stage.MOVE:
            problems.append(f"a move step proposes only moves, got a {edit.kind} edit")
    if step.stage is Stage.BLOCK:
        for edit in ordered:
            length = len(document.blocks[edit.span.block].text)
            if (edit.span.start, edit.span.end) != (0, length):
                problems.append(f"a block step's edit at {edit.span} does not cover its block")
    return problems


def _rendered(document: Document, script: Sequence[ScriptPiece]) -> list[str]:
    by_block: list[list[ScriptPiece]] = [[] for _ in document.blocks]
    for piece in script:
        by_block[piece.span.block].append(piece)
    return [spoken_text(pieces, show_pauses=True) for pieces in by_block]
