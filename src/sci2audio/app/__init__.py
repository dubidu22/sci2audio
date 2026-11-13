"""Application: the jobs and their settings; wires the pipeline stages together.

`JobRunner.run_script` runs the script job (#70): a file in, the listening script and the
pre-analysis report out. `JobRunner.run_audio` runs the audio job (#71): a file in, the
audiobook out, resuming from the working folder's chunk cache. Each job gets its
`JobSettings` and working folder passed in; the settings file (`load_settings`,
`save_settings`) and the default folders are used only by the command line and the server.
"""

from sci2audio.app.audio import (
    AudioJob,
    AudioPlan,
    AudioProgress,
    PlannedChunk,
    SkippedUtterance,
    plan_audio,
    run_audio_job,
)
from sci2audio.app.chapters import (
    REFERENCE_NAMES,
    Chapter,
    default_selection,
    document_title,
    find_chapters,
    is_reference_title,
)
from sci2audio.app.chunks import chunk_key, clean_work_folder
from sci2audio.app.config import (
    default_config_file,
    default_models_folder,
    default_work_folder,
    load_settings,
    save_settings,
)
from sci2audio.app.job import (
    EXTRACTORS,
    JobBusyError,
    JobCancelledError,
    JobError,
    OutputExistsError,
    Phase,
    ScriptFiles,
    ScriptJob,
    UnreadableFileError,
    UnsupportedFileError,
    run_script_job,
    script_files,
)
from sci2audio.app.report import Report, build_report, report_data, report_markdown, script_text
from sci2audio.app.runner import JobRunner
from sci2audio.app.script import ChapterScript, ScriptResult, prepare_script
from sci2audio.app.settings import JobSettings
from sci2audio.app.voice import VoiceSource, kokoro_voice

__all__ = [
    "EXTRACTORS",
    "REFERENCE_NAMES",
    "AudioJob",
    "AudioPlan",
    "AudioProgress",
    "Chapter",
    "ChapterScript",
    "JobBusyError",
    "JobCancelledError",
    "JobError",
    "JobRunner",
    "JobSettings",
    "OutputExistsError",
    "Phase",
    "PlannedChunk",
    "Report",
    "ScriptFiles",
    "ScriptJob",
    "ScriptResult",
    "SkippedUtterance",
    "UnreadableFileError",
    "UnsupportedFileError",
    "VoiceSource",
    "build_report",
    "chunk_key",
    "clean_work_folder",
    "default_config_file",
    "default_models_folder",
    "default_selection",
    "default_work_folder",
    "document_title",
    "find_chapters",
    "is_reference_title",
    "kokoro_voice",
    "load_settings",
    "plan_audio",
    "prepare_script",
    "report_data",
    "report_markdown",
    "run_audio_job",
    "run_script_job",
    "save_settings",
    "script_files",
    "script_text",
]
