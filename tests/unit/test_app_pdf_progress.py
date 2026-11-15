"""The jobs pass a PDF's page progress on (#343) and a cancel stops its reader (#344).

A cancel while a PDF is read ends the reader child at once, frees its reader slot, and ends
the job as cancelled, never as a damaged file.
"""

from __future__ import annotations

import multiprocessing
import threading
import time
from pathlib import Path

import pypdfium2 as pdfium
import pytest
import reader_targets
from audio_fakes import FakeVoice

from sci2audio.app import (
    AudioProgress,
    JobCancelledError,
    JobSettings,
    Phase,
    UnreadableFileError,
    run_audio_job,
    run_script_job,
)
from sci2audio.app.job import CANCELLED_WHILE_READING
from sci2audio.extraction import isolate, pdf

pytestmark = pytest.mark.timeout(120)

PYMEDPHYS = (
    Path(__file__).resolve().parents[1] / "corpus" / "papers" / "joss2022-biggs-pymedphys.pdf"
)


def page_count(path: Path) -> int:
    document = pdfium.PdfDocument(path)
    try:
        return len(document)
    finally:
        document.close()


def settings(folder: Path) -> JobSettings:
    return JobSettings(output_folder=folder / "out")


def test_the_script_job_hands_on_each_page_in_order(tmp_path: Path) -> None:
    seen: list[tuple[int, int]] = []
    phases: list[Phase] = []
    run_script_job(
        PYMEDPHYS,
        settings(tmp_path),
        tmp_path / "work",
        progress=phases.append,
        pages=lambda page, total: seen.append((page, total)),
    )
    total = page_count(PYMEDPHYS)
    assert total > 1
    assert seen == [(page, total) for page in range(1, total + 1)]
    assert phases[:2] == [Phase.READING, Phase.LAYOUT]


def test_the_audio_job_sends_each_page_while_reading(tmp_path: Path) -> None:
    events: list[AudioProgress] = []
    run_audio_job(
        PYMEDPHYS,
        settings(tmp_path),
        tmp_path / "work",
        voice=FakeVoice().source(),
        progress=events.append,
    )
    total = page_count(PYMEDPHYS)
    reading = [event for event in events if event.phase is Phase.READING]
    assert reading == [AudioProgress(Phase.READING)] + [
        AudioProgress(Phase.READING, page=page, pages=total) for page in range(1, total + 1)
    ]
    assert events.index(reading[-1]) < next(
        index for index, event in enumerate(events) if event.phase is Phase.LAYOUT
    )
    assert all(event.pages == 0 for event in events if event.phase is not Phase.READING)


@pytest.mark.every_pdf_read
def test_a_cancel_on_a_page_ends_the_audio_job_as_cancelled(tmp_path: Path) -> None:
    cancel = threading.Event()

    def progress(event: AudioProgress) -> None:
        if event.page == 2:
            cancel.set()

    voice = FakeVoice()
    with pytest.raises(JobCancelledError) as caught:
        run_audio_job(
            PYMEDPHYS,
            settings(tmp_path),
            tmp_path / "work",
            voice=voice.source(),
            progress=progress,
            cancel=cancel,
        )
    assert str(caught.value) == CANCELLED_WHILE_READING
    assert not isinstance(caught.value, UnreadableFileError)
    assert voice.made == 0
    assert multiprocessing.active_children() == []


@pytest.mark.every_pdf_read
def test_a_cancel_during_a_hanging_read_stops_the_reader_and_the_next_job_reads_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance test of #344: a read that would hang for 30 s, cancelled."""
    readers = isolate.Readers(pdf.MAX_PDF_READERS)
    monkeypatch.setattr(pdf, "_READERS", readers)
    with monkeypatch.context() as patch:
        patch.setattr(pdf, "_read_file", reader_targets.hanging_read)
        book = tmp_path / "book" / "book.pdf"
        book.parent.mkdir()
        book.write_bytes(PYMEDPHYS.read_bytes())
        cancel = threading.Event()
        outcome: dict[str, object] = {}

        def job() -> None:
            try:
                run_audio_job(
                    book,
                    settings(tmp_path),
                    tmp_path / "work",
                    voice=FakeVoice().source(),
                    cancel=cancel,
                )
            except BaseException as error:
                outcome["error"] = error
            outcome["ended"] = time.monotonic()

        thread = threading.Thread(target=job, daemon=True)
        thread.start()
        deadline = time.monotonic() + 60
        while not (book.parent / "started").exists():
            assert thread.is_alive()
            assert time.monotonic() < deadline
            time.sleep(0.02)
        cancelled = time.monotonic()
        cancel.set()
        thread.join(10)
        error = outcome["error"]
        assert isinstance(error, JobCancelledError)
        assert str(error) == CANCELLED_WHILE_READING
        assert outcome["ended"] - cancelled < 1.0  # type: ignore[operator]
        assert multiprocessing.active_children() == []
        assert readers.alive == 0
    began = time.monotonic()
    run_script_job(PYMEDPHYS, settings(tmp_path), tmp_path / "work")
    assert time.monotonic() - began < 30  # it did not wait for the hanging read
    assert readers.most == 1
    assert not (book.parent / "finished").exists()
