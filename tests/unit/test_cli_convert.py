"""`sci2audio convert` (#72, WI-03, WI-02) with the fake voice and the real ffmpeg (a few
seconds of audio, as #71's tests): the files, resume, the options, Ctrl-C (D-219), the
voice checks before any work (D-222) and one job per file (D-212)."""

from __future__ import annotations

import _thread
import json
import threading
from pathlib import Path

import pytest
from audio_fakes import FakeVoice
from cli_helpers import Cli, files_in, small_pdf

from sci2audio.app.lock import work_folder_lock

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


def test_ctrl_c_stops_after_the_current_sentence_and_the_rerun_continues(
    tmp_path: Path, source: Path
) -> None:
    interrupted = threading.Event()

    def press_ctrl_c(text: str) -> bool:
        if not interrupted.is_set():
            interrupted.set()
            _thread.interrupt_main()  # what Ctrl-C does: KeyboardInterrupt in the main thread
            # let the main thread see it and set the cancel event before this sentence ends
            threading.Event().wait(0.5)
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
