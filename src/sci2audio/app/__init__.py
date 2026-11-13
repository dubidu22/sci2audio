"""Application: the jobs and their settings; wires the pipeline stages together.

`JobRunner.run_script` runs the script job (#70): a file in, the listening script and the
pre-analysis report out. Each job gets its `JobSettings` and working folder passed in; the
settings file (`load_settings`, `save_settings`) is read and written only by the command
line and the server.
"""

from sci2audio.app.chapters import (
    REFERENCE_NAMES,
    Chapter,
    default_selection,
    document_title,
    find_chapters,
    is_reference_title,
)
from sci2audio.app.config import default_config_file, load_settings, save_settings
from sci2audio.app.job import (
    EXTRACTORS,
    JobBusyError,
    JobError,
    JobRunner,
    OutputExistsError,
    Phase,
    ScriptFiles,
    ScriptJob,
    UnsupportedFileError,
    run_script_job,
    script_files,
)
from sci2audio.app.report import Report, build_report, report_data, report_markdown, script_text
from sci2audio.app.script import ChapterScript, ScriptResult, prepare_script
from sci2audio.app.settings import JobSettings

__all__ = [
    "EXTRACTORS",
    "REFERENCE_NAMES",
    "Chapter",
    "ChapterScript",
    "JobBusyError",
    "JobError",
    "JobRunner",
    "JobSettings",
    "OutputExistsError",
    "Phase",
    "Report",
    "ScriptFiles",
    "ScriptJob",
    "ScriptResult",
    "UnsupportedFileError",
    "build_report",
    "default_config_file",
    "default_selection",
    "document_title",
    "find_chapters",
    "is_reference_title",
    "load_settings",
    "prepare_script",
    "report_data",
    "report_markdown",
    "run_script_job",
    "save_settings",
    "script_files",
    "script_text",
]
