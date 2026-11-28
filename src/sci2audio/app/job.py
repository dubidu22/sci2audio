"""The script job: a file in, the listening script and the pre-analysis report out (#70).

file → extraction (picked by file type) → layout → text steps on the whole document →
chapters → utterances of the chosen chapters → script and report. The job gets its
settings and its working folder passed in and keeps no state between jobs. It never stops
to ask (D-61 (3)): a failing text step, an `ask` edit or an unknown chapter is reported and
the run goes on. It fails, with a `JobError` a person can act on and nothing half-written,
only when it cannot go on: a file type it can't read, a file it can't open or that is
damaged, or a write that fails (a full disk).

Files: `<name>.script.txt`, `<name>.report.json` and `<name>.report.md` in the output folder
(`<name>` is the source's file name without its extension), and `job.json` in the working
folder, written last: the record the audio job (#71) resumes from.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Any

from sci2audio import __version__
from sci2audio.app.files import write_text_atomically, write_texts
from sci2audio.app.report import (
    Report,
    build_report,
    report_data,
    report_markdown,
    script_text,
)
from sci2audio.app.script import ScriptResult, prepare_script
from sci2audio.app.settings import JobSettings
from sci2audio.core import Content, Document
from sci2audio.extraction import (
    Cover,
    ExtractionError,
    ReadCancelled,
    extract_epub,
    extract_epub_cover,
    extract_markdown,
    extract_pdf,
    extract_pdf_cover,
    extract_text,
)
from sci2audio.layout import LayoutSettings, build_document
from sci2audio.output.names import clean, refused, retried
from sci2audio.textprep import BUILT_IN_STEPS, DEFAULT_MAX_CHARS, TextStep

RECORD = "job.json"
RECORD_FORMAT = "sci2audio-job"
RECORD_VERSION = 1

# extraction by file suffix (D-350); pasted text is kept as a .txt file, so it reads as text
EXTRACTORS: Mapping[str, Callable[[Path], Content]] = {
    ".epub": extract_epub,
    ".markdown": extract_markdown,
    ".md": extract_markdown,
    ".pdf": extract_pdf,
    ".txt": extract_text,
}
# the cover image a file type gives, or None (D-313); a type without one has no entry
COVERS: Mapping[str, Callable[[Path], Cover | None]] = {
    ".epub": extract_epub_cover,
    ".pdf": extract_pdf_cover,
}


class Phase(StrEnum):
    """What the job is doing; `progress` is called as each one starts."""

    READING = "reading"  # extraction
    LAYOUT = "layout"
    TEXT_STEPS = "text-steps"  # the steps, chapters and cutting into utterances
    LOADING_VOICE = "loading-voice"  # audio job: the voice model loads (skipped if all cached)
    SPEAKING = "speaking"  # audio job: the voice speaks the chunks not yet in the cache
    ENCODING = "encoding"  # audio job: output writes the MP3s, the M4B and the read-along
    WRITING = "writing"  # script job: its three files
    DONE = "done"


class JobError(Exception):
    """The job could not go on; the message says why in words a person can act on."""


class UnsupportedFileError(JobError):
    """A file type the job can't read."""


class UnreadableFileError(JobError):
    """A file of a type the job reads that can't be opened or is damaged (D-223)."""


class UnreadableTextError(UnreadableFileError):
    """A PDF whose text can't be read: most of it is its fonts' glyph numbers (#442). The
    audio job stops before the voice; the message names the pages."""


class OutputExistsError(JobError):
    """An output file exists and `overwrite` was not given."""


class SettingsChangedError(OutputExistsError):
    """The project's chapters were made under other settings than this job's (#726):
    chapters made with these would not match them. The person keeps the settings the
    chapters were made with (`keep_settings`) or replaces every chapter (`overwrite`).
    `old` and `new` are the two settings as the chapter record keeps them, `changes` the
    choices that differ, in words."""

    def __init__(self, old: dict[str, Any], new: dict[str, Any]) -> None:
        self.old, self.new = old, new
        self.changes = settings_changes(old, new)
        listed = "; ".join(self.changes) or "the settings"
        super().__init__(
            f"the chapters made so far were made with other settings ({listed}); keep the "
            "settings they were made with, or choose to replace them all"
        )


def settings_changes(old: dict[str, Any], new: dict[str, Any], where: str = "") -> list[str]:
    """The choices that differ between two settings records, as "speed: 1.0, now 1.2"."""
    out: list[str] = []
    for name in sorted({*old, *new}):
        label = f"{where}{name}"
        before, after = old.get(name), new.get(name)
        if isinstance(before, dict) and isinstance(after, dict):
            out.extend(settings_changes(before, after, f"{label} "))
        elif before != after:
            out.append(f"{label}: {_shown(before)}, now {_shown(after)}")
    return out


def _shown(value: Any) -> str:
    if value is None or value == "":
        return "default"
    if isinstance(value, list):
        return ", ".join(_shown(v) for v in value) or "none"
    return str(value)


class JobBusyError(JobError):
    """The runner, or another process on the same working folder, is already running a job
    (one job at a time)."""


class JobCancelledError(JobError):
    """The person cancelled the job; what was finished is kept for a rerun."""


CANCELLED_WHILE_READING = "the job was cancelled while the file was read"


@dataclass(frozen=True)
class ScriptFiles:
    """Where the script job writes."""

    script: Path
    report_json: Path
    report_markdown: Path
    record: Path  # in the working folder

    @property
    def outputs(self) -> tuple[Path, Path, Path]:
        return (self.script, self.report_json, self.report_markdown)


@dataclass(frozen=True)
class ScriptJob:
    """What a finished script job worked out and wrote."""

    result: ScriptResult
    report: Report
    files: ScriptFiles


def script_files(source: Path, settings: JobSettings, work: Path) -> ScriptFiles:
    """The files a script job of `source` writes. A name the output folder's file system
    refuses is made again from its old characters (#493); in a folder that does not exist
    yet no name is tried, and `_write` names the files again once it made the folder."""
    folder = settings.output_folder or source.absolute().parent
    stem = PurePath(source.name).stem
    name = clean(stem, "document")
    if refused(folder, f"{name}.script.txt"):
        name = retried(stem, "document")
    return ScriptFiles(
        script=folder / f"{name}.script.txt",
        report_json=folder / f"{name}.report.json",
        report_markdown=folder / f"{name}.report.md",
        record=work / RECORD,
    )


def settings_data(settings: JobSettings) -> dict[str, Any]:
    """The settings as the report and the job record keep them (no folders: those are
    machine-specific and not part of what the job decides)."""
    return {
        "language": settings.language,
        "switched_off": sorted(str(category) for category in settings.switched_off),
        "chapters": None if settings.chapters is None else list(settings.chapters),
        "voice": settings.voice,
        "speed": settings.speed,
        "letter_pace": settings.letter_pace,
        # only when off, so every record made with the plugins reads as before (#667)
        **({} if settings.plugins else {"plugins": False}),
    }


def run_script_job(
    source: Path,
    settings: JobSettings,
    work: Path,
    *,
    overwrite: bool = False,
    progress: Callable[[Phase], None] | None = None,
    pages: Callable[[int, int], None] | None = None,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    max_chars: int = DEFAULT_MAX_CHARS,
    finish: bool = False,
) -> ScriptJob:
    """Read `source`, prepare its listening script and report, and write them.

    `work` is the job's own working folder (made if missing). Existing output files are
    replaced only with `overwrite`; that is checked before any work starts. Raises
    JobError (or a subclass) when the job cannot go on; nothing half-written is left.
    `pages(number, total)` follows the pages of a PDF as they are read (#343).

    `finish` completes a set of files a run killed between its renames left (#1253):
    when some but not all of them exist, each holding just what this job writes, those
    are kept as they are and only the others written. Any other existing file is refused,
    after the text steps and before any file is written.
    """
    report: Callable[[Phase], None] = progress or (lambda phase: None)
    check_readable(source)
    files = script_files(source, settings, work)
    check_folders((files.script.parent, files.record.parent))
    existing = [path for path in files.outputs if path.exists()]
    finish = finish and 0 < len(existing) < len(files.outputs)
    if not overwrite and existing and not finish:
        names = ", ".join(path.name for path in existing)
        raise OutputExistsError(f"these files exist already: {names}; choose to replace them")

    document = read_document(source, settings, report, pages=pages)

    report(Phase.TEXT_STEPS)
    result = prepare_script(document, settings, steps, max_chars)
    job_report = build_report(result, settings_data(settings))

    report(Phase.WRITING)
    files = _write(source, files, result, job_report, settings, (overwrite, finish))
    report(Phase.DONE)
    return ScriptJob(result, job_report, files)


def _write(
    source: Path,
    files: ScriptFiles,
    result: ScriptResult,
    job_report: Report,
    settings: JobSettings,
    choices: tuple[bool, bool],  # overwrite, finish a set left half in place
) -> ScriptFiles:
    """Write the three files and the record; returns the files as written."""
    overwrite, finish = choices
    made = not files.script.parent.is_dir()
    for folder in (files.script.parent, files.record.parent):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise _folder_error(folder, error) from error
    if made:  # a new folder: its names can be tried only now (#493)
        files = script_files(source, settings, files.record.parent)
    texts = {
        files.script: script_text(result),
        files.report_json: json_text(report_data(job_report)),
        files.report_markdown: report_markdown(job_report),
    }
    if finish and not overwrite:
        texts = _not_in_place(texts)
    try:
        write_texts(texts, overwrite=overwrite)
        record = _record(files, result, settings)
        write_text_atomically(files.record, json_text(record), overwrite=True)
    except FileExistsError as error:
        target = error.filename2 or error.filename
        name = PurePath(str(target)).name if target else "an output file"
        raise OutputExistsError(f"{name} appeared during the run; choose to replace it") from error
    except OSError as error:
        where = PurePath(str(error.filename)).name if error.filename else "the output"
        raise JobError(f"could not write {where}: {error.strerror or error}") from error
    return files


def _not_in_place(texts: dict[Path, str]) -> dict[Path, str]:
    """The texts whose files are not in place yet. A file in place that holds anything but
    this text is the person's, never replaced: OutputExistsError, and nothing written."""
    other = []
    for target, text in texts.items():
        try:
            held = target.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise JobError(f"could not read {target.name}: {error.strerror or error}") from error
        if held != text.encode("utf-8"):
            other.append(target.name)
    if other:
        raise OutputExistsError(
            f"these files exist already: {', '.join(other)}; choose to replace them"
        )
    return {target: text for target, text in texts.items() if not target.exists()}


def check_readable(source: Path) -> None:
    """Refuse before any work a file type the job can't read."""
    if source.suffix.lower() not in EXTRACTORS:
        known = ", ".join(sorted(EXTRACTORS))
        raise UnsupportedFileError(f"{source.name}: sci2audio can read {known} files only")


def read_document(
    source: Path,
    settings: JobSettings,
    report: Callable[[Phase], None],
    *,
    pages: Callable[[int, int], None] | None = None,
    cancel: threading.Event | None = None,
) -> Document:
    """Extraction (picked by file type) and layout; JobError if the file can't be read.

    A PDF calls `pages(number, total)` as its reader starts each page (#343) and ends its
    reader at once when `cancel` is set, raising JobCancelledError (#344). The other file
    types read in a fraction of a second and take neither."""
    check_readable(source)
    suffix = source.suffix.lower()
    extract = EXTRACTORS[suffix]
    report(Phase.READING)
    try:
        if suffix == ".pdf":
            content = extract_pdf(source, pages=pages, cancel=cancel)
        else:
            content = extract(source)
    except ReadCancelled as error:  # not a damaged file (#344)
        raise JobCancelledError(CANCELLED_WHILE_READING) from error
    except ExtractionError as error:
        raise UnreadableFileError(str(error)) from error
    except OSError as error:
        raise UnreadableFileError(f"{source.name}: cannot be opened ({error.strerror})") from error
    report(Phase.LAYOUT)
    return build_document(content, LayoutSettings(language=settings.language))


def check_folders(folders: Sequence[Path]) -> None:
    """Refuse before any work an output or working folder that is a file."""
    for folder in folders:
        for path in (folder, *folder.parents):
            if path.exists():
                if not path.is_dir():
                    raise JobError(f"{path.name} is not a folder; choose another output folder")
                break


def _folder_error(folder: Path, error: OSError) -> JobError:
    if isinstance(error, FileExistsError | NotADirectoryError):
        return JobError(f"{folder.name} is not a folder; choose another output folder")
    return JobError(f"could not make the folder {folder.name}: {error.strerror or error}")


def _record(files: ScriptFiles, result: ScriptResult, settings: JobSettings) -> dict[str, Any]:
    source = result.document.content.source
    return {
        "format": RECORD_FORMAT,
        "version": RECORD_VERSION,
        "sci2audio": __version__,
        "source": {"name": source.name, "format": str(source.format), "sha256": source.sha256},
        "settings": settings_data(settings),
        "chapters": [
            {
                "index": chapter.chapter.index,
                "title": chapter.chapter.title,
                "selected": chapter.selected,
                "utterances": chapter.spoken,
            }
            for chapter in result.chapters
        ],
        "files": {
            "script": files.script.name,
            "report_json": files.report_json.name,
            "report_markdown": files.report_markdown.name,
        },
    }


def json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
