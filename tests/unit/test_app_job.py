"""The script job on files (#70): extraction by file type, the files it writes, one job at
a time, progress, and the errors a person can act on."""

import json
import threading
from pathlib import Path

import pytest
from pdf_maker import Text, make_pdf

from sci2audio.app import (
    EXTRACTORS,
    JobBusyError,
    JobError,
    JobRunner,
    JobSettings,
    OutputExistsError,
    Phase,
    UnreadableFileError,
    UnsupportedFileError,
    run_script_job,
    script_files,
)
from sci2audio.textprep import Category

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
SEABORN = CORPUS / "papers" / "joss2021-waskom-seaborn.pdf"
TIME_MACHINE = CORPUS / "epub" / "wells-the-time-machine.epub"
OWN_MARKDOWN = CORPUS / "markdown" / "sci2audio-sample-note.md"
OWN_TEXT = CORPUS / "text" / "sci2audio-sample-plain.txt"


def small_pdf(folder: Path, name: str = "note.pdf") -> Path:
    path = folder / name
    path.write_bytes(
        make_pdf(
            [Text("A short note.", 72, 100, size=11), Text("It has two lines.", 72, 114, size=11)]
        )
    )
    return path


def test_a_pdf_becomes_a_script_a_report_and_a_job_record(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)
    work = tmp_path / "work" / "job1"
    job = run_script_job(source, JobSettings(), work)
    assert job.files.script == tmp_path / "note.script.txt"
    assert job.files.report_json == tmp_path / "note.report.json"
    assert job.files.report_markdown == tmp_path / "note.report.md"
    assert job.files.record == work / "job.json"
    assert job.files.script.read_text(encoding="utf-8") == (
        "sci2audio listening script\nSource: note.pdf\nLanguage: en\n\n"
        "# 1. note\n\nA short note.\nIt has two lines.\n"
    )
    report = json.loads(job.files.report_json.read_text(encoding="utf-8"))
    assert (report["format"], report["version"]) == ("sci2audio-report", 1)
    assert report["chapters"][0]["title"] == "note"
    record = json.loads(job.files.record.read_text(encoding="utf-8"))
    assert record["format"] == "sci2audio-job"
    assert record["version"] == 1
    assert record["source"]["sha256"] == job.result.document.content.source.sha256
    assert record["files"] == {
        "script": "note.script.txt",
        "report_json": "note.report.json",
        "report_markdown": "note.report.md",
    }
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "note.pdf", "note.report.json", "note.report.md", "note.script.txt", "work",
    ]  # fmt: skip


def test_the_output_folder_and_settings_are_used(tmp_path: Path) -> None:
    out = tmp_path / "new" / "folder"
    settings = JobSettings(
        language="en-GB",
        switched_off=frozenset({Category.LINKS}),
        chapters=frozenset({0}),
        output_folder=out,
    )
    job = run_script_job(small_pdf(tmp_path), settings, tmp_path / "w")
    assert job.files.script.parent == out
    assert job.result.document.language == "en-GB"
    data = json.loads(job.files.record.read_text(encoding="utf-8"))
    assert data["settings"] == {
        "language": "en-GB",
        "switched_off": ["links"],
        "chapters": [0],
        "voice": "",
        "speed": 1.0,
    }
    assert str(tmp_path) not in job.files.record.read_text(encoding="utf-8")
    assert str(tmp_path) not in job.files.report_json.read_text(encoding="utf-8")


def test_extraction_is_picked_by_the_file_suffix_in_any_case(tmp_path: Path) -> None:
    assert set(EXTRACTORS) == {".epub", ".markdown", ".md", ".pdf", ".txt"}  # D-350
    source = small_pdf(tmp_path, "UPPER.PDF")
    job = run_script_job(source, JobSettings(), tmp_path / "w")
    assert job.files.script.name == "UPPER.script.txt"


@pytest.mark.parametrize("name", ["paper.docx", "notes.rtf", "notes.text", "no-suffix"])
def test_a_file_type_it_cannot_read_is_refused_before_anything_runs(
    tmp_path: Path, name: str
) -> None:
    source = tmp_path / name
    source.write_text("text", encoding="utf-8")
    phases: list[Phase] = []
    with pytest.raises(
        UnsupportedFileError, match=r"can read \.epub, \.markdown, \.md, \.pdf, \.txt files only"
    ):
        run_script_job(source, JobSettings(), tmp_path / "w", progress=phases.append)
    assert phases == []
    assert not (tmp_path / "w").exists()


def test_an_epub_becomes_a_script(tmp_path: Path) -> None:
    job = run_script_job(TIME_MACHINE, JobSettings(output_folder=tmp_path / "out"), tmp_path / "w")
    script = job.files.script.read_text(encoding="utf-8")
    assert job.files.script.name == "wells-the-time-machine.script.txt"
    assert "Source: wells-the-time-machine.epub\nLanguage: en-GB\n" in script
    assert "The Time Traveller (for so it will be convenient to speak of him)" in script
    assert job.result.document.content.metadata.authors == ("H. G. Wells",)


@pytest.mark.parametrize(
    ("sample", "said"),
    [
        (OWN_MARKDOWN, "Spoken text runs at about 150 words per minute"),
        (OWN_TEXT, "This note describes a made-up pilot study and no real data."),
    ],
)
def test_markdown_and_text_become_a_script(tmp_path: Path, sample: Path, said: str) -> None:
    """Read, not refused (D-350); since #75 layout reads their structure from the tags."""
    job = run_script_job(sample, JobSettings(output_folder=tmp_path / "out"), tmp_path / "w")
    script = job.files.script.read_text(encoding="utf-8")
    assert f"Source: {sample.name}\n" in script
    assert said in script
    assert job.report.warnings == ()
    assert json.loads(job.files.report_json.read_text(encoding="utf-8"))["warnings"] == []


def test_pasted_text_reads_as_a_text_file(tmp_path: Path) -> None:
    source = tmp_path / "pasted text.txt"  # as the web keeps it (D-350)
    source.write_text("Pasted words.\n\nA second paragraph.\n", encoding="utf-8")
    job = run_script_job(source, JobSettings(), tmp_path / "w")
    assert "Pasted words." in job.files.script.read_text(encoding="utf-8")
    assert job.result.document.content.source.format == "text"


def test_a_guessed_encoding_is_a_report_warning(tmp_path: Path) -> None:
    """A text file that is not UTF-8 is read as Windows-1252, and the report says so (D-346)."""
    source = tmp_path / "old notes.md"
    source.write_bytes("# Caf\u00e9 notes\n\nSome \u201cquoted\u201d text.\n".encode("cp1252"))
    job = run_script_job(source, JobSettings(), tmp_path / "w")
    warning = (
        "old notes.md is not saved as UTF-8; it was read as Windows-1252, a guess. "
        "If letters look wrong, save it as UTF-8 and open it again."
    )
    assert job.report.warnings == (warning,)
    assert json.loads(job.files.report_json.read_text(encoding="utf-8"))["warnings"] == [warning]
    assert warning in job.files.report_markdown.read_text(encoding="utf-8")
    assert "Caf\u00e9 notes" in job.files.script.read_text(encoding="utf-8")


def test_a_damaged_epub_fails_with_a_message_naming_the_file(tmp_path: Path) -> None:
    source = tmp_path / "broken.EPUB"
    source.write_bytes(b"PK\x03\x04 not really")
    with pytest.raises(UnreadableFileError, match=r"broken\.EPUB: not an EPUB"):
        run_script_job(source, JobSettings(), tmp_path / "w")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.EPUB"]


def test_a_damaged_pdf_fails_with_a_message_naming_the_file(tmp_path: Path) -> None:
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"%PDF-1.7\nnot really")
    with pytest.raises(UnreadableFileError, match=r"broken\.pdf"):  # D-223
        run_script_job(source, JobSettings(), tmp_path / "w")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.pdf"]


def test_a_missing_file_fails_with_a_message_naming_the_file(tmp_path: Path) -> None:
    with pytest.raises(UnreadableFileError, match=r"gone\.pdf: cannot be opened"):
        run_script_job(tmp_path / "gone.pdf", JobSettings(), tmp_path / "w")


def test_existing_outputs_are_replaced_only_when_asked(tmp_path: Path) -> None:
    source = small_pdf(tmp_path)
    (tmp_path / "note.report.md").write_text("mine", encoding="utf-8")
    phases: list[Phase] = []
    with pytest.raises(OutputExistsError, match=r"note\.report\.md"):
        run_script_job(source, JobSettings(), tmp_path / "w", progress=phases.append)
    assert phases == []  # refused before any work
    assert (tmp_path / "note.report.md").read_text(encoding="utf-8") == "mine"
    assert not (tmp_path / "note.script.txt").exists()
    run_script_job(source, JobSettings(), tmp_path / "w", overwrite=True)
    assert (tmp_path / "note.report.md").read_text(encoding="utf-8").startswith("# What")


def test_progress_reports_each_phase_in_order(tmp_path: Path) -> None:
    phases: list[Phase] = []
    run_script_job(small_pdf(tmp_path), JobSettings(), tmp_path / "w", progress=phases.append)
    # the audio job's phases (loading the voice, speaking, encoding) never come here
    assert phases == [Phase.READING, Phase.LAYOUT, Phase.TEXT_STEPS, Phase.WRITING, Phase.DONE]


def test_the_files_a_job_writes_are_known_before_it_runs(tmp_path: Path) -> None:
    files = script_files(Path("in/My: Paper.pdf"), JobSettings(output_folder=tmp_path), tmp_path)
    assert files.script == tmp_path / "My Paper.script.txt"
    files = script_files(tmp_path / " .pdf", JobSettings(), tmp_path / "w")
    assert files.script == tmp_path / "document.script.txt"


def test_one_runner_runs_one_job_at_a_time(tmp_path: Path) -> None:
    runner = JobRunner()
    started, release = threading.Event(), threading.Event()
    errors: list[BaseException] = []

    def hold(phase: Phase) -> None:
        if phase is Phase.LAYOUT:
            started.set()
            release.wait(30)

    def first() -> None:
        try:
            runner.run_script(small_pdf(tmp_path, "a.pdf"), JobSettings(), tmp_path / "wa",
                              progress=hold)  # fmt: skip
        except BaseException as error:  # pragma: no cover - reported below
            errors.append(error)

    thread = threading.Thread(target=first)
    thread.start()
    assert started.wait(30)
    assert runner.busy
    with pytest.raises(JobBusyError, match="another job is running"):
        runner.run_script(small_pdf(tmp_path, "b.pdf"), JobSettings(), tmp_path / "wb")
    # another runner is another program part (a test, a second window): not blocked
    JobRunner().run_script(small_pdf(tmp_path, "c.pdf"), JobSettings(), tmp_path / "wc")
    release.set()
    thread.join(30)
    assert errors == []
    assert not runner.busy
    runner.run_script(small_pdf(tmp_path, "b.pdf"), JobSettings(), tmp_path / "wb")


def test_a_failed_job_frees_the_runner(tmp_path: Path) -> None:
    runner = JobRunner()
    with pytest.raises(JobError):
        runner.run_script(tmp_path / "gone.pdf", JobSettings(), tmp_path / "w")
    assert not runner.busy


def test_the_reference_list_of_a_paper_is_not_spoken_by_default(tmp_path: Path) -> None:
    job = run_script_job(SEABORN, JobSettings(output_folder=tmp_path), tmp_path / "w")
    last = job.result.chapters[-1]
    assert last.chapter.title == "References"
    assert not last.selected
    assert "# 7. References (not spoken)\n" in job.files.script.read_text(encoding="utf-8")
    chosen = run_script_job(
        SEABORN,
        JobSettings(output_folder=tmp_path, chapters=frozenset({6})),
        tmp_path / "w",
        overwrite=True,
    )
    assert [c.selected for c in chosen.result.chapters] == [False] * 6 + [True]
