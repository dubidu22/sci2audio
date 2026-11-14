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
    extract_epub,
    extract_epub_cover,
    extract_markdown,
    extract_pdf,
    extract_pdf_cover,
    extract_text,
)
from sci2audio.layout import LayoutSettings, build_document
from sci2audio.output.names import clean
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


class OutputExistsError(JobError):
    """An output file exists and `overwrite` was not given."""


class JobBusyError(JobError):
    """The runner, or another process on the same working folder, is already running a job
    (one job at a time)."""


class JobCancelledError(JobError):
    """The person cancelled the job; what was finished is kept for a rerun."""


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
    """The files a script job of `source` writes."""
    folder = settings.output_folder or source.absolute().parent
    name = clean(PurePath(source.name).stem, "document")
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
        "chapters": None if settings.chapters is None else sorted(settings.chapters),
        "voice": settings.voice,
        "speed": settings.speed,
        "letter_pace": settings.letter_pace,
    }


def run_script_job(
    source: Path,
    settings: JobSettings,
    work: Path,
    *,
    overwrite: bool = False,
    progress: Callable[[Phase], None] | None = None,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> ScriptJob:
    """Read `source`, prepare its listening script and report, and write them.

    `work` is the job's own working folder (made if missing). Existing output files are
    replaced only with `overwrite`; that is checked before any work starts. Raises
    JobError (or a subclass) when the job cannot go on; nothing half-written is left.
    """
    report: Callable[[Phase], None] = progress or (lambda phase: None)
    check_readable(source)
    files = script_files(source, settings, work)
    check_folders((files.script.parent, files.record.parent))
    if not overwrite and (existing := [path for path in files.outputs if path.exists()]):
        names = ", ".join(path.name for path in existing)
        raise OutputExistsError(f"these files exist already: {names}; choose to replace them")

    document = read_document(source, settings, report)

    report(Phase.TEXT_STEPS)
    result = prepare_script(document, settings, steps, max_chars)
    job_report = build_report(result, settings_data(settings))

    report(Phase.WRITING)
    _write(files, result, job_report, settings, overwrite)
    report(Phase.DONE)
    return ScriptJob(result, job_report, files)


def _write(
    files: ScriptFiles,
    result: ScriptResult,
    job_report: Report,
    settings: JobSettings,
    overwrite: bool,
) -> None:
    texts = {
        files.script: script_text(result),
        files.report_json: json_text(report_data(job_report)),
        files.report_markdown: report_markdown(job_report),
    }
    for folder in (files.script.parent, files.record.parent):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise _folder_error(folder, error) from error
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


def check_readable(source: Path) -> None:
    """Refuse before any work a file type the job can't read."""
    if source.suffix.lower() not in EXTRACTORS:
        known = ", ".join(sorted(EXTRACTORS))
        raise UnsupportedFileError(f"{source.name}: sci2audio can read {known} files only")


def read_document(source: Path, settings: JobSettings, report: Callable[[Phase], None]) -> Document:
    """Extraction (picked by file type) and layout; JobError if the file can't be read."""
    check_readable(source)
    extract = EXTRACTORS[source.suffix.lower()]
    report(Phase.READING)
    try:
        content = extract(source)
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
