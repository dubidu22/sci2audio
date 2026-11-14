"""The pre-analysis report (UC-01) and the listening script as files a person reads.

The report lists every edit the text steps proposed: its category, step, reason, the
original text and what is said instead, the page it is printed on, its chapter and what
became of it (applied, set aside by the overlap rule with the edit that won, switched off),
and whether it is spoken (not when its chapter is not chosen). It counts the edits per
category and names the chapters, the steps that failed and the steps not run for the
language. JSON format "sci2audio-report", version 1, owned by the app; a Markdown version
for reading. Chapters are counted from 0 in the JSON (as `JobSettings.chapters`) and
numbered from 1 for people.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sci2audio import __version__
from sci2audio.app.chapters import Chapter
from sci2audio.app.script import ScriptResult
from sci2audio.core import Document, EditKind, LanguageGuess, LanguageSource, Source, Span
from sci2audio.textprep import PAUSE_MARK, Category, Outcome, Status

FORMAT = "sci2audio-report"
VERSION = 1
SCRIPT_TITLE = "sci2audio listening script"
_SPACES = re.compile(r"\s+")
LINE_BREAK = "\u21b5"  # "↵": how a quote shows a line break in an edit's original text
_MARKDOWN = re.compile(r"([\\`*_\[\]<>|#])")


@dataclass(frozen=True)
class Where:
    """A span, the page its first character is printed on and that page's printed label."""

    span: Span
    page: int | None  # counted from 1; None when the block has no items
    printed_page: str  # "" when the page prints none or the page is unknown


@dataclass(frozen=True)
class ReportEdit:
    """One proposed edit as the report shows it."""

    category: Category
    step: str
    kind: EditKind
    reason: str
    status: Status
    spoken: bool  # applied in a chosen chapter
    original: str  # the original text of its span, as printed
    said: str  # what is read instead; "" for a removal, PAUSE_MARK for a pause
    where: Where
    chapter: int
    won_by: tuple[str, EditKind, Where] | None = None  # set aside: step, kind, place


@dataclass(frozen=True)
class CategoryCount:
    category: Category
    applied: int = 0  # accepted, in chosen chapters: changes what is heard
    not_spoken: int = 0  # accepted, but its chapter is not chosen
    set_aside: int = 0
    switched_off: int = 0


@dataclass(frozen=True)
class ChapterEntry:
    chapter: Chapter
    selected: bool
    first_page: int | None
    utterances: int


@dataclass(frozen=True)
class Report:
    source_name: str
    source_format: str
    sha256: str
    language: str
    settings: dict[str, Any]
    chapters: tuple[ChapterEntry, ...]
    counts: tuple[CategoryCount, ...]
    edits: tuple[ReportEdit, ...]
    problems: tuple[tuple[str, str], ...]  # step id, message
    not_run: tuple[str, ...]
    warnings: tuple[str, ...]
    # where the language came from and what the text said (D-494); None: not recorded
    language_source: LanguageSource | None = None
    language_guess: LanguageGuess | None = None


def build_report(result: ScriptResult, settings: dict[str, Any]) -> Report:
    """The report of a prepared script; `settings` as the job records them."""
    document = result.document
    pages = Pages(document)
    edits = tuple(_edit(result, outcome, pages) for outcome in result.run.outcomes)
    counts = []
    for category in Category:
        mine = [edit for edit in edits if edit.category is category]
        accepted = [edit for edit in mine if edit.status is Status.ACCEPTED]
        counts.append(
            CategoryCount(
                category,
                applied=sum(edit.spoken for edit in accepted),
                not_spoken=sum(not edit.spoken for edit in accepted),
                set_aside=sum(edit.status is Status.SET_ASIDE for edit in mine),
                switched_off=sum(edit.status is Status.SWITCHED_OFF for edit in mine),
            )
        )
    chapters = tuple(
        ChapterEntry(
            script.chapter,
            script.selected,
            pages.first_page(script.chapter),
            script.spoken,
        )
        for script in result.chapters
    )
    source = document.content.source
    warnings = tuple(  # numbered from 1, as the chapter table and the command line (#104)
        f"chapter {index + 1} was chosen, but the document has chapters 1 to "
        f"{len(chapters)} only; ignored"
        for index in result.ignored_chapters
    )
    if guessed := encoding_warning(source):
        warnings = (guessed, *warnings)
    if language := language_warning(document):
        warnings = (language, *warnings)
    return Report(
        source_name=source.name,
        source_format=str(source.format),
        sha256=source.sha256,
        language=document.language,
        settings=settings,
        chapters=chapters,
        counts=tuple(counts),
        edits=edits,
        problems=tuple((p.step, p.message) for p in result.run.problems),
        not_run=result.run.not_run,
        warnings=warnings,
        language_source=document.language_source,
        language_guess=document.language_guess,
    )


def encoding_warning(source: Source) -> str | None:
    """The warning for a text file whose encoding was a guess (D-346), else None."""
    if not source.encoding_guessed:
        return None
    name = _ENCODING_NAMES.get(source.encoding, source.encoding)
    return (
        f"{source.name} is not saved as UTF-8; it was read as {name}, a guess. "
        "If letters look wrong, save it as UTF-8 and open it again."
    )


_ENCODING_NAMES = {"windows-1252": "Windows-1252"}  # as people know it
LANGUAGE_NAMES = {"en": "English", "de": "German"}  # the languages the text can be guessed as


def language_warning(document: Document) -> str | None:
    """The warning when the text did not tell its language, or when it overruled the
    language the file states (D-495, D-496), else None."""
    stated = document.content.metadata.language
    if document.language_source is LanguageSource.FALLBACK:
        return (
            "sci2audio could not tell from the text whether it is English or German, so it "
            "is read in English. If it is German, set the language to de (on the command "
            "line: --language de)."
        )
    if document.language_source is LanguageSource.TEXT and stated:
        name = LANGUAGE_NAMES[document.language]
        return (
            f"The file says its language is {stated}, but its text is {name}, so it is read "
            f"in {name}. To read it as {stated}, set the language to {stated} (on the "
            f"command line: --language {stated})."
        )
    return None


def language_line(report: Report) -> str:
    """The report's language line: the language and where it came from (D-494)."""
    guess = report.language_guess
    match report.language_source:
        case LanguageSource.SETTING:
            return f"Language: {report.language}, chosen in the settings."
        case LanguageSource.FILE:
            return f"Language: {report.language}, as the file states."
        case LanguageSource.TEXT if guess is not None:
            return (
                f"Language: {report.language}, guessed from the text ({guess.german:,} German "
                f"and {guess.english:,} English common words in {guess.words:,})."
            )
        case LanguageSource.FALLBACK:
            return (
                f"Language: {report.language}; the text does not show whether it is English "
                "or German, so it is read as English."
            )
    return f"Language: {report.language}."


def report_data(report: Report) -> dict[str, Any]:
    """The report as JSON data, keys in a fixed order."""
    return {
        "format": FORMAT,
        "version": VERSION,
        "sci2audio": __version__,
        "source": {
            "name": report.source_name,
            "format": report.source_format,
            "sha256": report.sha256,
        },
        "language": report.language,
        "language_source": None if report.language_source is None else str(report.language_source),
        "language_guess": None
        if report.language_guess is None
        else {
            "language": report.language_guess.language,
            "words": report.language_guess.words,
            "german": report.language_guess.german,
            "english": report.language_guess.english,
        },
        "settings": report.settings,
        "chapters": [
            {
                "index": entry.chapter.index,
                "title": entry.chapter.title,
                "blocks": [entry.chapter.start, entry.chapter.end],
                "first_page": entry.first_page,
                "references": entry.chapter.references,
                "selected": entry.selected,
                "utterances": entry.utterances,
            }
            for entry in report.chapters
        ],
        "counts": {
            str(count.category): {
                "label": count.category.label,
                "applied": count.applied,
                "not_spoken": count.not_spoken,
                "set_aside": count.set_aside,
                "switched_off": count.switched_off,
            }
            for count in report.counts
        },
        "edits": [_edit_data(edit) for edit in report.edits],
        "problems": [{"step": step, "message": message} for step, message in report.problems],
        "not_run": list(report.not_run),
        "warnings": list(report.warnings),
    }


def report_markdown(report: Report) -> str:
    """The report for reading."""
    out = [
        f"# What sci2audio will read: {_md(report.source_name)}",
        "",
        f"{language_line(report)} The text steps looked at the whole document; edits "
        "in chapters that are not chosen are listed but not spoken.",
        "",
        "## Chapters",
        "",
        "| No. | Chapter | Page | Read | Utterances |",
        "|---|---|---|---|---|",
    ]
    for entry in report.chapters:
        read = "yes" if entry.selected else "no"
        if entry.chapter.references:
            read += " (reference list)"
        page = "" if entry.first_page is None else str(entry.first_page)
        out.append(
            f"| {entry.chapter.index + 1} | {_md(entry.chapter.title)} | {page} | {read} "
            f"| {entry.utterances} |"
        )
    out += [
        "",
        "## Edits per category",
        "",
        "| Category | Applied | Not spoken (chapter not chosen) | Set aside | Switched off |",
        "|---|---|---|---|---|",
    ]
    for count in report.counts:
        out.append(
            f"| {count.category.label} | {count.applied} | {count.not_spoken} "
            f"| {count.set_aside} | {count.switched_off} |"
        )
    for count in report.counts:
        mine = [edit for edit in report.edits if edit.category is count.category]
        if mine:
            out += ["", f"## {count.category.label} ({len(mine)})", ""]
            out += [_edit_line(edit) for edit in mine]
    if report.problems or report.not_run or report.warnings:
        out += ["", "## Problems", ""]
        out += [
            f"- Step {_md(step)} failed and was left out: {_md(message)}"
            for step, message in report.problems
        ]
        out += [f"- Step {_md(step)} does not handle this language." for step in report.not_run]
        out += [f"- {_md(warning)}" for warning in report.warnings]
    return "\n".join(out) + "\n"


def script_text(result: ScriptResult) -> str:
    """The listening script: one utterance per line, a blank line between blocks.

    For people to read: an utterance that reads "[pause]" or starts with "# " looks like a
    pause or a chapter heading here. Programs read the report JSON and the job's data.
    """
    source = result.document.content.source
    out = [SCRIPT_TITLE, f"Source: {source.name}", f"Language: {result.document.language}"]
    for script in result.chapters:
        number = script.chapter.index + 1
        title = _one_line(script.chapter.title)
        if not script.selected:
            out += ["", f"# {number}. {title} (not spoken)"]
            continue
        out += ["", f"# {number}. {title}", ""]
        if not script.utterances:
            out.append("(nothing to read)")
        block = None
        for utterance in script.utterances:
            if block is not None and utterance.span.block != block:
                out.append("")
            block = utterance.span.block
            out.append(PAUSE_MARK if utterance.pause else utterance.text)
    return "\n".join(out) + "\n"


class Pages:
    """Where blocks and spans are printed."""

    def __init__(self, document: Document) -> None:
        self.document = document
        self.items = {item: page.number for item, (page, _) in document.content.items().items()}

    def where(self, span: Span) -> Where:
        part = self.document.blocks[span.block].part_at(span.start)
        page = self.items[part.item] if part else None
        printed = self.document.page_label(page) if page is not None else ""
        return Where(span, page, printed)

    def first_page(self, chapter: Chapter) -> int | None:
        for block in self.document.blocks[chapter.start : chapter.end]:
            if block.parts:
                return self.items[block.parts[0].item]
        return None


def _edit(result: ScriptResult, outcome: Outcome, pages: Pages) -> ReportEdit:
    edit = outcome.edit
    chapter = result.chapter_of(edit.span.block)
    won_by = None
    if outcome.won_by is not None:
        won_by = (outcome.won_by.step, outcome.won_by.kind, pages.where(outcome.won_by.span))
    original = result.document.text_of(edit.span)
    said = {
        EditKind.REMOVE: "",
        EditKind.REPLACE: edit.replacement,
        EditKind.PAUSE: PAUSE_MARK,
        EditKind.ASK: original,
    }[edit.kind]
    return ReportEdit(
        category=outcome.category,
        step=edit.step,
        kind=edit.kind,
        reason=edit.reason,
        status=outcome.status,
        spoken=outcome.status is Status.ACCEPTED and chapter.selected,
        original=original,
        said=said,
        where=pages.where(edit.span),
        chapter=chapter.chapter.index,
        won_by=won_by,
    )


def where_data(where: Where) -> dict[str, Any]:
    return {
        "block": where.span.block,
        "start": where.span.start,
        "end": where.span.end,
        "page": where.page,
        "printed_page": where.printed_page,
    }


def _edit_data(edit: ReportEdit) -> dict[str, Any]:
    data: dict[str, Any] = {
        "category": str(edit.category),
        "step": edit.step,
        "kind": str(edit.kind),
        "reason": edit.reason,
        "status": str(edit.status),
        "spoken": edit.spoken,
        "original": edit.original,
        "said": edit.said,
        "chapter": edit.chapter,
        **where_data(edit.where),
    }
    if edit.won_by is not None:
        step, kind, where = edit.won_by
        data["won_by"] = {"step": step, "kind": str(kind), **where_data(where)}
    return data


def _edit_line(edit: ReportEdit) -> str:
    place = _page_text(edit.where)
    said = {
        EditKind.REMOVE: "left out",
        EditKind.REPLACE: f"read as “{_md(_one_line(edit.said))}”",
        EditKind.PAUSE: "a pause",
        EditKind.ASK: "read as printed until you decide",
    }[edit.kind]
    what = f"“{_md(shown_original(edit.original))}”" if edit.original else "(position)"
    if edit.status is Status.SET_ASIDE and edit.won_by is not None:
        step, kind, where = edit.won_by
        status = f"set aside: the {kind} edit of step {_md(step)} ({_page_text(where)}) won"
    elif edit.status is Status.SWITCHED_OFF:
        status = "switched off"
    elif not edit.spoken:
        status = "not spoken (chapter not chosen)"
    else:
        status = "applied"
    return (
        f"- {place}, chapter {edit.chapter + 1}, {status}: {what} → {said}. "
        f"Reason: {_md(edit.reason.rstrip('.'))}. Step: {_md(edit.step)}."
    )


def _page_text(where: Where) -> str:
    if where.page is None:
        return "page unknown"
    if where.printed_page and where.printed_page != str(where.page):
        return f"page {where.page} (printed {_md(where.printed_page)})"
    return f"page {where.page}"


def _one_line(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def shown_original(text: str) -> str:
    """An edit's original text on one line, as a quote shows it (#118).

    Line breaks count as spaces, except in a text without a letter or digit: there each one
    shows as "↵". An edit of a line-end hyphen holds only a line break, or a hyphen and one,
    and would otherwise look empty ("“” → left out"); in running text a "↵" would only get
    in the way of reading."""
    if "\n" in text and not any(char.isalnum() for char in text):
        return LINE_BREAK.join(_one_line(line) for line in text.split("\n"))
    return _one_line(text)


def _md(text: str) -> str:
    """Text shown as itself in Markdown: its special characters escaped."""
    return _MARKDOWN.sub(r"\\\1", text)
