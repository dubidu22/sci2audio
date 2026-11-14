"""`sci2audio convert` (#72, WI-03, WI-02) with the fake voice and the real ffmpeg (a few
seconds of audio, as #71's tests): the files, resume, the options, Ctrl-C (D-219), the
voice checks before any work (D-222) and one job per file (D-212)."""

from __future__ import annotations

import _thread
import json
import threading
import time
from pathlib import Path

import pytest
from audio_fakes import FakeVoice
from cli_helpers import Cli, files_in, small_pdf

from sci2audio import cli as cli_module
from sci2audio.app.lock import work_folder_lock
from sci2audio.voices import RemoteFile

LINES = (
    "The first sentence is here.",
    "A second sentence follows it.",
    "Then comes a third one.",
    "And a fourth to end with.",
)
BOOK = ["note - 01 note.mp3", "note.m4b", "note.readalong.json"]


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    return Cli(tmp_path)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return small_pdf(tmp_path / "in", LINES)


def audio_record(cli: Cli, source: Path) -> dict:
    return json.loads((cli.work(source) / "audio.json").read_text(encoding="utf-8"))


def test_writes_the_audiobook(cli: Cli, source: Path, tmp_path: Path) -> None:
    out = tmp_path / "book"
    result = cli("convert", source, "-o", out)
    assert result.code == 0, result.err
    assert files_in(out) == BOOK
    assert all((out / name).stat().st_size > 0 for name in BOOK)
    spoken = len(cli.voice.spoken)
    assert spoken > 0
    assert f"Spoke {spoken} of {spoken} sentences, reused 0 from the last run" in result.out
    for name in BOOK:
        assert str(out / name) in result.out
    assert "sci2audio clean note.pdf" in result.out  # the cache hint (D-210)
    assert "Speaking chapter 1, note:" in result.err


def test_running_again_reuses_every_sentence(cli: Cli, source: Path, tmp_path: Path) -> None:
    out = tmp_path / "book"
    assert cli("convert", source, "-o", out, "-q").code == 0
    spoken = len(cli.voice.spoken)
    again = cli("convert", source, "-o", out, "-q")
    assert again.code == 7
    assert "add --overwrite" in again.err
    assert len(cli.voice.spoken) == spoken  # refused before any speech
    replaced = cli("convert", source, "-o", out, "-q", "--overwrite")
    assert replaced.code == 0
    assert f"Spoke 0 of {spoken} sentences, reused {spoken}" in replaced.out
    assert len(cli.voice.spoken) == spoken
    assert cli.voice.made == 1  # the cached rerun never made the engine


def test_m4b_only(cli: Cli, source: Path, tmp_path: Path) -> None:
    assert cli("convert", source, "-o", tmp_path / "b", "-q", "--format", "m4b").code == 0
    assert files_in(tmp_path / "b") == ["note.m4b", "note.readalong.json"]


def test_mp3_only(cli: Cli, source: Path, tmp_path: Path) -> None:
    assert cli("convert", source, "-o", tmp_path / "b", "-q", "--format", "mp3").code == 0
    assert files_in(tmp_path / "b") == ["note - 01 note.mp3", "note.readalong.json"]


def test_with_script(cli: Cli, source: Path, tmp_path: Path) -> None:
    result = cli("convert", source, "-o", tmp_path / "b", "-q", "--with-script")
    assert result.code == 0, result.err
    assert files_in(tmp_path / "b") == sorted(
        [*BOOK, "note.report.json", "note.report.md", "note.script.txt"]
    )
    assert str(tmp_path / "b" / "note.script.txt") in result.out


def test_voice_and_speed_reach_the_job(cli: Cli, source: Path, tmp_path: Path) -> None:
    result = cli("convert", source, "-o", tmp_path, "-q", "--voice", "bm_george", "--speed", "1.5")
    assert result.code == 0, result.err
    assert {(voice, speed) for _, voice, speed in cli.voice.spoken} == {("bm_george", 1.5)}
    record = audio_record(cli, source)
    assert (record["voice"], record["speed"]) == ("bm_george", 1.5)


def test_the_letter_pace_reaches_the_voice(cli: Cli, source: Path, tmp_path: Path) -> None:
    """#295: --letter-pace slower asks the voice for letter_speed 0.7; without the flag
    the request is the one from before (no letter_speed)."""
    result = cli("convert", source, "-o", tmp_path, "-q", "--letter-pace", "slower")
    assert result.code == 0, result.err
    assert set(cli.voice.letter_speeds) == {0.7}
    assert audio_record(cli, source)["settings"]["letter_pace"] == "slower"


def test_without_the_flag_the_voice_gets_no_letter_speed(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    assert cli("convert", source, "-o", tmp_path, "-q").code == 0
    assert set(cli.voice.letter_speeds) == {None}


def test_an_unknown_letter_pace_is_a_usage_error(cli: Cli, source: Path) -> None:
    result = cli("convert", source, "--letter-pace", "fast")
    assert result.code == 2
    assert "invalid choice: 'fast'" in result.err


def test_the_settings_file_gives_the_voice(cli: Cli, source: Path, tmp_path: Path) -> None:
    cli.config.parent.mkdir(parents=True)
    cli.config.write_text('{"version": 1, "voice": "bm_george", "speed": 0.8}', encoding="utf-8")
    assert cli("convert", source, "-o", tmp_path, "-q").code == 0
    assert {(voice, speed) for _, voice, speed in cli.voice.spoken} == {("bm_george", 0.8)}


@pytest.mark.parametrize("value", ["0.4", "2.5", "fast", "nan", "inf"])
def test_a_speed_out_of_range_is_a_usage_error(cli: Cli, source: Path, value: str) -> None:
    result = cli("convert", source, "--speed", value)
    assert result.code == 2
    assert "the speed must be a number from 0.5 to 2.0" in result.err


def test_an_unknown_voice_is_a_usage_error(cli: Cli, source: Path, tmp_path: Path) -> None:
    result = cli("convert", source, "-o", tmp_path / "b", "--voice", "zz_nobody")
    assert result.code == 2
    assert result.err == (
        "sci2audio: there is no voice 'zz_nobody'; `sci2audio voices` lists the voices\n"
    )
    assert cli.voice.made == 0
    assert not (tmp_path / "b").exists()


def test_missing_voice_files_stop_before_the_file_is_read(tmp_path: Path, source: Path) -> None:
    cli = Cli(tmp_path, voice_installed=False)
    result = cli("convert", source, "--chapters", "all")
    assert result.code == 6
    assert result.err == (
        f"sci2audio: the voice files are not installed in {cli.models}; "
        "run `sci2audio voices download` first\n"
    )
    assert not cli.work(source).exists()
    assert cli.voice.made == 0


def test_one_missing_voice_pack_does_not_stop_a_book(tmp_path: Path, source: Path) -> None:
    """D-468: only a job whose own pack is missing stops (in the job, before any speech)."""
    german = RemoteFile("https://example.test/de", "de/model.pth", 1, "0" * 64, "MIT", pack="de")
    cli = Cli(tmp_path, missing=lambda models: [german])
    result = cli("convert", source, "-q", "-o", tmp_path / "out", "--chapters", "all")
    assert result.code == 0, result.err
    assert cli.voice.spoken


def test_the_models_folder_option(tmp_path: Path, source: Path) -> None:
    seen: list[Path] = []

    def missing(models: Path) -> list:
        seen.append(models)
        return []

    cli = Cli(tmp_path, missing=missing)
    assert cli("convert", source, "-q", "-o", tmp_path, "--models-folder", tmp_path / "m").code == 0
    assert seen == [tmp_path / "m"]


def test_busy_while_another_job_holds_the_work_folder(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    with work_folder_lock(cli.work(source)):
        result = cli("convert", source, "-o", tmp_path / "b", "-q")
    assert result.code == 8
    assert "another sci2audio job is working on this file" in result.err
    assert cli.voice.spoken == []


STOPPING = "stopping after the current sentence"


def wait_for_stopping(cli: Cli) -> None:
    """Wait until the main thread has taken the Ctrl-C (its line is on stderr), so a test
    never depends on how fast a loaded machine handles it."""
    deadline = time.monotonic() + 10
    while cli.env is None or STOPPING not in cli.env.err.getvalue():  # type: ignore[attr-defined]
        assert time.monotonic() < deadline, "the Ctrl-C was not taken within 10 s"
        time.sleep(0.01)


def test_ctrl_c_stops_after_the_current_sentence_and_the_rerun_continues(
    tmp_path: Path, source: Path
) -> None:
    interrupted = threading.Event()

    def press_ctrl_c(text: str) -> bool:
        if not interrupted.is_set():
            interrupted.set()
            _thread.interrupt_main()  # what Ctrl-C does: KeyboardInterrupt in the main thread
            wait_for_stopping(cli)  # the cancel event is set before this sentence ends
        return False

    cli = Cli(tmp_path, voice=FakeVoice(fail_on=press_ctrl_c))
    out = tmp_path / "b"
    result = cli("convert", source, "-o", out, "-q")
    assert result.code == 130
    assert "stopping after the current sentence; finished sentences are kept" in result.err
    assert result.err.endswith(
        "sci2audio: the job was cancelled; finished parts are kept for a rerun; "
        "run the same command again to continue\n"
    )
    first = len(cli.voice.spoken)
    assert first == 1  # the sentence being spoken was finished, then the job stopped
    assert files_in(out) == []

    again = Cli(tmp_path)
    result = again("convert", source, "-o", out, "-q")
    assert result.code == 0, result.err
    assert f"reused {first} from the last run" in result.out
    assert again.voice.texts == [text for text in LINES if text not in cli.voice.texts]


def test_a_second_ctrl_c_stops_at_once(tmp_path: Path, source: Path) -> None:
    """D-219: the first Ctrl-C asks the job to stop after the sentence; a second one does
    not wait for it (review round 1, S1)."""
    pressed = threading.Event()

    def press_twice_then_take_long(text: str) -> bool:
        if not pressed.is_set():
            pressed.set()
            _thread.interrupt_main()
            wait_for_stopping(cli)  # the first Ctrl-C is taken; now the second
            _thread.interrupt_main()
            threading.Event().wait(10)  # a sentence that takes long
        return False

    cli = Cli(tmp_path, voice=FakeVoice(fail_on=press_twice_then_take_long))
    started = time.monotonic()
    result = cli("convert", source, "-o", tmp_path / "b", "-q")
    assert time.monotonic() - started < 5  # it did not wait for the sentence to end
    assert result.code == 130
    assert result.err == (
        "sci2audio: stopping after the current sentence; finished sentences are kept\n"
        "sci2audio: stopped; run the same command again to continue\n"
    )
    assert not (tmp_path / "b").exists()


def test_an_unknown_voice_with_every_chapter_is_refused_before_reading(
    cli: Cli, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-222: the voice is checked before the file is read, also with --chapters all
    (review round 1, S2)."""
    read: list[Path] = []
    real = cli_module.read_document

    def reading(path: Path, *args: object) -> object:
        read.append(path)
        return real(path, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(cli_module, "read_document", reading)
    result = cli("convert", source, "--voice", "zz_nobody", "--chapters", "all")
    assert result.code == 2
    assert read == []
    assert cli("convert", source, "-q", "--chapters", "all").code == 0
    assert read == [source]  # `all` still reads the chapters, after the checks


def test_with_script_refuses_an_existing_audiobook_and_writes_no_script(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """All or nothing (review round 1, S3): the audiobook exists, the script doesn't."""
    out = tmp_path / "b"
    assert cli("convert", source, "-o", out, "-q").code == 0
    before = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}
    result = cli("convert", source, "-o", out, "-q", "--with-script")
    assert result.code == 7
    assert "note.m4b" in result.err
    assert {p.name: p.stat().st_mtime_ns for p in out.iterdir()} == before


def test_with_script_refuses_an_existing_script_before_any_speech(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """All or nothing (review round 1, S3): the script exists, the audiobook doesn't."""
    out = tmp_path / "b"
    assert cli("script", source, "-o", out, "-q").code == 0
    before = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}
    result = cli("convert", source, "-o", out, "-q", "--with-script")
    assert result.code == 7
    assert "note.script.txt" in result.err
    assert {p.name: p.stat().st_mtime_ns for p in out.iterdir()} == before
    assert cli.voice.spoken == []
    replaced = cli("convert", source, "-o", out, "-q", "--with-script", "--overwrite")
    assert replaced.code == 0, replaced.err
    assert files_in(out) == sorted([*BOOK, "note.report.json", "note.report.md", "note.script.txt"])


def test_progress_on_a_terminal(tmp_path: Path, source: Path) -> None:
    result = Cli(tmp_path, live=True)("convert", source, "-o", tmp_path / "b")
    assert result.code == 0
    assert "\rSpeaking chapter 1, note: 4 of 4 sentences" in result.err
    assert result.err.endswith("\n")


def test_nothing_to_read(cli: Cli, tmp_path: Path) -> None:
    source = small_pdf(tmp_path / "in", LINES)
    result = cli("convert", source, "-o", tmp_path / "b", "-q", "--chapters", "5")
    assert result.code == 1
    assert "there is nothing to read in the chosen chapters" in result.err
    assert "there is no chapter 5" not in result.out


def test_skipped_sentences_are_listed(tmp_path: Path, source: Path) -> None:
    cli = Cli(tmp_path, voice=FakeVoice(fail_on=lambda text: text.startswith("Then")))
    result = cli("convert", source, "-o", tmp_path / "b", "-q")
    assert result.code == 0, result.err
    assert (
        "sci2audio: warning: the voice could not say this sentence on page 1, so it is left "
        "out: 'Then comes a third one.'"
    ) in result.err


def test_a_guessed_encoding_is_named_when_converting(cli: Cli, tmp_path: Path) -> None:
    """D-346, as for `script`."""
    source = tmp_path / "in" / "old notes.txt"
    source.parent.mkdir()
    source.write_bytes("Café notes in an old file.\n".encode("cp1252"))
    result = cli("convert", source, "-o", tmp_path / "book", "-q")
    assert result.code == 0, result.err
    assert result.err.count("old notes.txt is not saved as UTF-8; it was read as Windows-1252") == 1
