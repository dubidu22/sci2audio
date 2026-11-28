"""What the command line and the app window print of Python's logging (#143, #1258):
sci2audio's own warnings and errors as before, a library's errors but never its warnings,
also from the reader child, and the app's log file as before."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from sci2audio import cli
from sci2audio.app import own_warnings_only
from sci2audio.web import window


@pytest.fixture(autouse=True)
def root_handlers() -> Iterator[None]:
    root = logging.getLogger()
    before = root.handlers[:]
    yield
    root.handlers[:] = before


def test_a_librarys_warning_is_dropped_and_sci2audios_own_is_printed_as_before(
    capsys: pytest.CaptureFixture[str],
) -> None:
    own_warnings_only()
    logging.getLogger("pypdfium2._helpers.document").warning("A circular bookmark reference")
    logging.getLogger("uvicorn.something").warning("not ours either")
    logging.getLogger("sci2audio.web.tasks").warning("ours, %s", "as Python printed it")
    logging.getLogger("sci2audio").error("ours too")
    logging.getLogger("sci2audio.app.updates").info("below a warning: never printed")
    logging.getLogger("sci2audiox").warning("only a name that starts alike")
    assert capsys.readouterr().err == "ours, as Python printed it\nours too\n"


def test_a_librarys_error_is_printed_as_python_printed_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#143 hides a library's warnings only; an error is still the person's to see (#1258)."""
    own_warnings_only()
    logging.getLogger("asyncio").error("Task exception was never retrieved")
    logging.getLogger("pypdfium2").critical("and %s", "worse")
    assert capsys.readouterr().err == "Task exception was never retrieved\nand worse\n"


@pytest.mark.every_pdf_read
def test_the_reader_childs_lines_follow_the_same_choice(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """sci2audio's own warning in the reader child is printed, once; a library's warning
    there is not, its error is (#1258)."""
    import reader_targets

    from sci2audio.extraction import isolate

    own_warnings_only()
    result = isolate.run(
        reader_targets.logs_then_returns,
        (5,),
        memory=1024**3,
        step_seconds=60,
        readers=isolate.Readers(1),
    )
    assert result == 5
    assert capfd.readouterr().err == (
        "own warning in the reader child\nlibrary error in the reader child\n"
    )


def test_setting_it_up_twice_prints_each_line_once(capsys: pytest.CaptureFixture[str]) -> None:
    own_warnings_only()
    own_warnings_only()
    logging.getLogger("sci2audio.web").warning("once")
    assert capsys.readouterr().err == "once\n"


def test_the_app_windows_log_file_keeps_what_it_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    own_warnings_only()
    path = tmp_path / "app.log"
    window.open_log(path)
    try:
        window.log.warning("the server stopped")
    finally:
        for handler in window.log.handlers:
            handler.close()
        window.log.handlers.clear()
        window.log.propagate = True
    assert path.read_text(encoding="utf-8").endswith("WARNING the server stopped\n")
    assert capsys.readouterr().err == ""  # the window's own lines go to its file only


@pytest.mark.parametrize("main", [cli.main, window.main], ids=["sci2audio", "sci2audio-app"])
def test_both_programs_set_it_up_before_anything_else(main: object) -> None:
    """Each entry point decides once, at start-up; the pipeline stages never do (#143)."""
    body = inspect.getsource(main)  # type: ignore[arg-type]
    assert "own_warnings_only()" in body
    assert body.index("own_warnings_only()") < body.index("freeze_support()")
