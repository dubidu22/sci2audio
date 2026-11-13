"""The speed script (#11, D-281 to D-287) with the fake voice and a ticking clock: the
estimate's accuracy, the budget, the arguments, and a whole run on the short paper with
the real ffmpeg (a few seconds of audio, allowed in the fast suite, D-118). The real voice
runs it nightly (`--quick --device cpu`, D-287)."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import Phase

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "speed.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sci2audio_speed_script", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up
    spec.loader.exec_module(module)
    return module


speed = _load()
Event = speed.Event
SPEAKING = str(Phase.SPEAKING)


def ticking(step: float = 0.25) -> Iterator[float]:
    now = 0.0
    while True:
        now += step
        yield now


def clock_of(ticks: Iterator[float]):  # type: ignore[no-untyped-def]
    return lambda: next(ticks)


def speaking(at: float, done: int, left: float | None, total: int = 1000) -> object:
    return Event(at, SPEAKING, done, total, left)


# ---- the estimate's accuracy -------------------------------------------------------------


def test_the_estimate_is_compared_with_the_real_remaining_time() -> None:
    events = [
        Event(0.0, SPEAKING, 0, 1000, None),  # the speaking phase starts
        speaking(10, 100, None),  # still measuring
        speaking(20, 200, 100.0),  # 80 s were left: +25 %
        speaking(40, 400, 54.0),  # 60 s: -10 %
        speaking(60, 600, 44.0),  # 40 s: +10 %
        speaking(80, 800, 18.0),  # 20 s: -10 %
        speaking(95, 950, 4.0),  # 5 s: -20 %, too close to the end to judge
        speaking(100, 1000, 0.0),  # the end: nothing to compare
    ]
    accuracy = speed.estimate_accuracy(events, speaking_end=100.0)

    assert accuracy["shown"] is True
    assert accuracy["first"] == {"done": 0.2, "estimate": 100.0, "actual": 80.0, "error": 0.25}
    assert accuracy["at_25"]["error"] == -0.1  # the first at or after 25 %: 40 %
    assert accuracy["at_50"]["error"] == 0.1  # 60 %
    assert accuracy["at_75"]["error"] == -0.1  # 80 %
    assert accuracy["judged"] == 4  # 10 s or more to go
    assert accuracy["median_abs_error"] == 0.1
    assert accuracy["largest_abs_error"] == 0.25
    assert accuracy["largest_abs_error_with_a_minute_left"] == 0.25  # 80 s and 60 s left
    assert len(accuracy["samples"]) == 6
    assert accuracy["samples"][-1]["error"] is None


def test_an_estimate_that_never_appears_is_reported_as_never_shown() -> None:
    events = [Event(0.0, SPEAKING, 0, 300, None), speaking(5, 300, None, total=300)]
    accuracy = speed.estimate_accuracy(events, speaking_end=6.0)
    assert accuracy == {"shown": False, "samples": []}
    assert speed._estimate_cell(accuracy) == "never shown"


def test_other_phases_never_count_as_estimates() -> None:
    events = [Event(0.0, str(Phase.ENCODING), 0, 1000, 50.0)]
    assert speed.estimate_accuracy(events, speaking_end=100.0)["shown"] is False


def test_each_phase_lasts_until_the_next_one_starts() -> None:
    events = [
        Event(1.0, str(Phase.READING)),
        Event(1.5, str(Phase.LAYOUT)),
        Event(2.0, str(Phase.TEXT_STEPS)),
        Event(2.25, str(Phase.LOADING_VOICE)),
        Event(10.0, SPEAKING),
        Event(20.0, SPEAKING),
        Event(70.0, str(Phase.ENCODING)),
        Event(72.0, str(Phase.DONE)),
    ]
    assert speed.phase_times(events) == {
        "reading": 0.5,
        "layout": 0.5,
        "text-steps": 0.25,
        "loading-voice": 7.75,
        "speaking": 60.0,
        "encoding": 2.0,
    }


# ---- the budget --------------------------------------------------------------------------


def job_numbers(**changes: object) -> dict[str, object]:
    numbers: dict[str, object] = {
        "device": "cpu",
        "pages": 8,
        "preparation_seconds": 4.0,
        "realtime_factor_speaking": 3.2,
        "encoding_times_realtime": 120.0,
        "estimate": {"largest_abs_error_with_a_minute_left": 0.12},
    }
    numbers.update(changes)
    return numbers


def test_the_budget_is_checked_line_by_line() -> None:
    lines = speed.budget([job_numbers()], app_device="cpu")
    assert [line["met"] for line in lines] == [True, True, True, True]
    assert lines[0]["measured"] == "0.50 s per page (10.0 s for 20 pages)"
    assert lines[1]["reference"] is True
    assert lines[2]["measured"] == "largest error ±12%"


def test_a_missed_budget_says_not_met_and_an_unjudged_one_says_so() -> None:
    slow = job_numbers(
        preparation_seconds=16.0,  # 2 s per page: 40 s for 20 pages
        realtime_factor_speaking=0.8,
        encoding_times_realtime=20.0,
        estimate={"largest_abs_error_with_a_minute_left": None},
    )
    lines = speed.budget([slow], app_device="cpu")
    assert [line["met"] for line in lines] == [False, False, None, False]
    assert "less than a minute" in lines[2]["measured"]


def test_speech_speed_is_judged_on_the_apps_own_device_only() -> None:
    # D-286: "faster than real time" is about the device the app picks by itself
    slow_cpu = job_numbers(realtime_factor_speaking=0.8)
    fast_mps = job_numbers(device="mps", realtime_factor_speaking=6.0)
    lines = speed.budget([fast_mps, slow_cpu], app_device="mps")
    speech = [line for line in lines if line["target"].startswith("speech")]
    assert [(line["device"], line["met"], line["reference"]) for line in speech] == [
        ("mps", True, True),
        ("cpu", None, False),
    ]
    assert speech[1]["measured"] == "real-time factor 0.8 (the app uses mps here)"


# ---- the arguments -----------------------------------------------------------------------


def test_devices_default_to_every_device_and_auto_means_the_apps_own() -> None:
    assert speed.resolve_devices(None, ["mps", "cpu"]) == ["mps", "cpu"]
    assert speed.resolve_devices(["auto", "mps", "cpu"], ["mps", "cpu"]) == ["mps", "cpu"]
    with pytest.raises(speed.SpeedError, match="no cuda device"):
        speed.resolve_devices(["cuda"], ["mps", "cpu"])


def test_an_unknown_paper_or_voice_names_the_choices() -> None:
    with pytest.raises(speed.SpeedError, match="joss2022-biggs-pymedphys"):
        speed.resolve_paper("no-such-paper")
    assert speed.resolve_paper("acl2023-hardt-ellipsis").name == "acl2023-hardt-ellipsis.pdf"
    with pytest.raises(speed.SpeedError, match="af_heart"):
        speed.resolve_voices(speed.parse(["--voice", "xx_nobody"]))
    with pytest.raises(speed.SpeedError, match="af_heart"):
        speed.resolve_voices(speed.parse(["--quick", "--voice", "xx_nobody"]))
    assert speed.resolve_voices(speed.parse(["--quick", "--voice", "bm_george"])) == ["bm_george"]
    assert speed.resolve_voices(speed.parse(["--quick"])) == ["af_heart"]
    assert len(speed.resolve_voices(speed.parse(["--all-voices"]))) == 28


def test_missing_voice_files_stop_before_any_work(tmp_path: Path) -> None:
    said: list[str] = []
    asked: list[int] = []
    out = tmp_path / "result.json"

    def devices() -> list[str]:
        asked.append(1)
        return ["cpu"]

    code = speed.main(
        ["--models-folder", str(tmp_path / "empty"), "--json", str(out)],
        devices=devices,
        say=said.append,
    )
    assert code == 1
    assert "sci2audio voices download" in said[-1]
    assert (asked, out.exists()) == ([], False)


def test_a_device_this_machine_lacks_is_refused(tmp_path: Path) -> None:
    said: list[str] = []
    code = speed.main(
        ["--device", "mps", "--json", str(tmp_path / "r.json")],
        voice_for=lambda models, device: FakeVoice().source(),
        devices=lambda: ["cpu"],
        say=said.append,
    )
    assert code == 1
    assert said == ["speed: this machine has no mps device for torch; it has: cpu"]


# ---- a whole run -------------------------------------------------------------------------


def test_a_quick_run_writes_every_number_offline(tmp_path: Path) -> None:
    fake = FakeVoice()
    devices_asked: list[str] = []

    def voice_for(models: Path, device: str):  # type: ignore[no-untyped-def]
        devices_asked.append(device)
        return fake.source()

    said: list[str] = []
    out = tmp_path / "speed.json"
    code = speed.main(
        ["--quick", "--json", str(out)],
        voice_for=voice_for,
        devices=lambda: ["mps", "cpu"],
        clock=clock_of(ticking()),
        say=said.append,
    )
    assert code == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert (result["format"], result["version"]) == ("sci2audio-speed", 1)
    assert result["app_device"] == "mps"
    assert result["network_attempts"] == []
    assert "host" not in json.dumps(result["machine"]).lower()
    assert devices_asked == ["mps", "mps", "cpu", "cpu"]  # each device: voice part, job

    assert [part["device"] for part in result["voice"]] == ["mps", "cpu"]
    voice = result["voice"][0]["voices"][0]
    assert voice["voice"] == "af_heart"
    assert voice["characters"] == sum(len(s) for s in speed.PARAGRAPH)
    assert voice["characters_per_second"] > 0
    assert voice["realtime_factor"] > 0

    job = result["job"][1]
    assert (job["device"], job["paper"], job["skipped"]) == ("cpu", "joss2022-biggs-pymedphys", 0)
    assert job["pages"] == 4
    assert job["characters"] > 5000
    assert set(job["phases"]) >= {"reading", "layout", "text-steps", "speaking", "encoding"}
    assert job["speaking_seconds"] > 0
    assert job["audio_seconds"] > 0
    assert job["estimate"]["shown"] is True
    assert job["estimate"]["samples"]

    assert len(result["budget"]) == 8  # four lines per device
    assert len(result["markdown"]["voice"]) == 2
    assert len(result["markdown"]["job"]) == 2
    assert all(row.startswith("| ") and row.endswith(" |") for row in result["markdown"]["job"])
    assert result["markdown"]["job"][1].count(" | ") == 12  # 13 columns
    assert said[-1] == f"\nAll numbers: {out}"
    assert any(line.startswith("Performance budget") for line in said)


# ---- review round 1: nothing is lost after a long run, errors are messages -----------------


def never_called(models: Path, device: str):  # type: ignore[no-untyped-def]
    raise AssertionError("no work may start")


def test_the_json_folder_is_made_before_any_work(tmp_path: Path) -> None:
    out = tmp_path / "results" / "m4" / "speed.json"
    code = speed.main(
        ["--quick", "--skip-job", "--json", str(out)],
        voice_for=lambda models, device: FakeVoice().source(),
        devices=lambda: ["cpu"],
        clock=clock_of(ticking()),
        say=lambda line: None,
    )
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["format"] == "sci2audio-speed"


@pytest.mark.parametrize("where", ["a folder", "under a file"])
def test_a_json_path_that_cannot_be_written_stops_before_any_work(
    tmp_path: Path, where: str
) -> None:
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    out = tmp_path if where == "a folder" else tmp_path / "file.txt" / "speed.json"
    said: list[str] = []
    code = speed.main(
        ["--quick", "--json", str(out)],
        voice_for=never_called,
        devices=lambda: ["cpu"],
        say=said.append,
    )
    assert code == 1
    assert said[0].startswith("speed: ")
    assert ("is a folder" in said[0]) == (where == "a folder")


def test_a_paper_the_job_cannot_read_is_refused_before_any_work(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("# Notes", encoding="utf-8")
    said: list[str] = []
    code = speed.main(
        ["--paper", str(notes), "--json", str(tmp_path / "r.json")],
        voice_for=never_called,
        devices=lambda: ["cpu"],
        say=said.append,
    )
    assert code == 1
    assert said == ["speed: notes.md: sci2audio can read .pdf files only"]
    assert not (tmp_path / "r.json").exists()


def test_a_job_that_fails_ends_with_a_message_not_a_traceback(tmp_path: Path) -> None:
    sources = iter([FakeVoice().source(), FakeVoice(fail_on=lambda text: True).source()])
    said: list[str] = []
    code = speed.main(
        ["--quick", "--json", str(tmp_path / "r.json")],
        voice_for=lambda models, device: next(sources),
        devices=lambda: ["cpu"],
        clock=clock_of(ticking()),
        say=said.append,
    )
    assert code == 1
    assert said[-1].startswith("speed: the voice failed on 5 sentences in a row")


def test_a_voice_that_fails_in_the_voice_part_ends_with_a_message(tmp_path: Path) -> None:
    said: list[str] = []
    code = speed.main(
        ["--quick", "--json", str(tmp_path / "r.json")],
        voice_for=lambda models, device: FakeVoice(fail_on=lambda text: True).source(),
        devices=lambda: ["cpu"],
        clock=clock_of(ticking()),
        say=said.append,
    )
    assert code == 1
    assert said[-1].startswith("speed: the voice failed: cannot say")
