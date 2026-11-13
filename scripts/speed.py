"""How fast sci2audio speaks on this machine: the speed script (#11, VA-02, WI-04).

    uv run python scripts/speed.py            # after `sci2audio voices download`
    uv run python scripts/speed.py --quick    # the short paper, one voice
    uv run python scripts/speed.py --help

Two measurements, offline (the network is blocked once the voice files are found):

A. The voice alone, per voice and device: a fixed English paragraph spoken sentence by
   sentence; characters per second and the real-time factor (seconds of audio per second
   of work; above 1 is faster than real time). The first sentence warms the voice up and
   is not counted.
B. The audio job on a corpus paper, per device, from a cold cache: the time of every
   phase, characters per second, the real-time factor, and how close the job's time
   estimate (D-159, D-380) came to the real remaining time (D-284), and the characters and
   seconds of every spoken chunk (#136).

It prints a summary, checks the performance budget in `docs/baseline.md` (D-286) and
always writes a JSON file (format "sci2audio-speed", version 1) with every number and
ready-to-paste Markdown rows for `docs/baseline.md` (D-285). The machine is named by its
model, processor, cores and memory; never by its host name.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import warnings
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from itertools import pairwise
from pathlib import Path
from typing import Any

from sci2audio import __version__
from sci2audio.app import (
    AudioProgress,
    JobError,
    JobSettings,
    Phase,
    VoiceSource,
    default_models_folder,
    kokoro_voice,
    run_audio_job,
)
from sci2audio.app.job import check_readable
from sci2audio.testing import no_network
from sci2audio.voices import (
    DEFAULT_VOICE,
    ENGLISH_VOICES,
    EngineConfig,
    EngineError,
    create_kokoro_engine,
    missing_files,
    speak_to_wav,
)

FORMAT = "sci2audio-speed"
VERSION = 1
REPOSITORY = Path(__file__).resolve().parents[1]
PAPERS = REPOSITORY / "tests" / "corpus" / "papers"
DEFAULT_PAPER = "acl2023-hardt-ellipsis"  # D-283
QUICK_PAPER = "joss2022-biggs-pymedphys"
DEVICE_ORDER = ("mps", "cuda", "cpu")  # the order the Kokoro engine picks by itself
STATS_MIN_LEFT = 10.0  # seconds; the last seconds divide by almost nothing (D-284)
BUDGET_MIN_LEFT = 60.0  # the estimate budget holds while at least a minute is left (D-286)
ESTIMATE_BUDGET = 0.25  # within ±25 % of the real remaining speaking time (D-286)
ENCODING_BUDGET = 50.0  # times faster than real time (D-286)
PREPARATION_BUDGET = 30.0 / 20  # seconds per page: a 20-page paper in under 30 s (D-286)

# Our own words (no third-party text): six sentences of the kind a paper holds.
PARAGRAPH = (
    "We measured the reaction time of forty volunteers in three sessions.",
    "Each session lasted about twenty minutes and began with a short practice block.",
    "The mean response was faster in the second session than in the first, "
    "although the difference was small.",
    "Participants who slept less than six hours responded more slowly and made more errors.",
    "These results suggest that practice and rest both shape performance on simple tasks.",
    "Further work should test whether the effect holds for older adults "
    "and for more demanding tasks.",
)

Clock = Callable[[], float]
VoiceFor = Callable[[Path, str], VoiceSource]  # models folder, device -> voice


class SpeedError(Exception):
    """The script cannot run; the message says what to do."""


# ---- the estimate's accuracy (pure) ------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """One progress event of the audio job, time-stamped by the script."""

    at: float
    phase: str
    characters_done: int = 0
    characters_total: int = 0
    seconds_left: float | None = None


def phase_times(events: Sequence[Event]) -> dict[str, float]:
    """Seconds from the first event of each phase to the first event of the next one."""
    starts: dict[str, float] = {}
    for event in events:
        starts.setdefault(event.phase, event.at)
    order = sorted(starts.items(), key=lambda item: item[1])
    return {phase: round(order[i + 1][1] - start, 3) for i, (phase, start) in enumerate(order[:-1])}


def chunk_times(events: Sequence[Event]) -> list[dict[str, Any]]:
    """The characters and seconds of every chunk the voice spoke, in order (#136).

    Taken between consecutive progress events of the speaking phase (the job sends one as
    the phase starts and one after every chunk); a chunk taken from the cache adds no
    characters and is left out. The first chunk includes the voice's warm-up.
    """
    speaking = [event for event in events if event.phase == Phase.SPEAKING]
    return [
        {
            "characters": now.characters_done - before.characters_done,
            "seconds": round(now.at - before.at, 4),
        }
        for before, now in pairwise(speaking)
        if now.characters_done > before.characters_done
    ]


def estimate_accuracy(events: Sequence[Event], speaking_end: float) -> dict[str, Any]:
    """How far each shown estimate was from the real remaining speaking time (D-284).

    error = (estimate - actual) / actual, so +0.2 means the job said 20 % too long. The
    summary: the first estimate, the first at or after 25, 50 and 75 % of the characters,
    and the median and largest absolute error over the estimates with at least
    STATS_MIN_LEFT seconds still to go; every sample is kept.
    """
    samples = []
    for event in events:
        if event.phase != Phase.SPEAKING or event.seconds_left is None:
            continue
        actual = speaking_end - event.at
        done = event.characters_done / event.characters_total if event.characters_total else 1
        samples.append(
            {
                "done": round(done, 4),
                "estimate": round(event.seconds_left, 3),
                "actual": round(actual, 3),
                "error": round((event.seconds_left - actual) / actual, 4) if actual > 0 else None,
            }
        )
    if not samples:
        return {"shown": False, "samples": []}
    judged = [s for s in samples if s["actual"] >= STATS_MIN_LEFT and s["error"] is not None]
    within_budget = [
        s for s in samples if s["actual"] >= BUDGET_MIN_LEFT and s["error"] is not None
    ]

    def at(fraction: float) -> dict[str, Any] | None:
        return next((s for s in samples if s["done"] >= fraction), None)

    errors = [abs(s["error"]) for s in judged]
    return {
        "shown": True,
        "first": samples[0],
        "at_25": at(0.25),
        "at_50": at(0.50),
        "at_75": at(0.75),
        "judged": len(judged),
        "median_abs_error": round(statistics.median(errors), 4) if errors else None,
        "largest_abs_error": round(max(errors), 4) if errors else None,
        "largest_abs_error_with_a_minute_left": (
            round(max(abs(s["error"]) for s in within_budget), 4) if within_budget else None
        ),
        "samples": samples,
    }


# ---- the machine -----------------------------------------------------------------------


def _run(*command: str) -> str:
    """The trimmed output of a local program, or "" (never fails)."""
    exe = shutil.which(command[0])
    if exe is None:
        return ""
    try:
        done = subprocess.run(  # noqa: S603 (a fixed local program, no shell)
            [exe, *command[1:]], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _processor() -> str:
    if sys.platform == "darwin":
        return _run("sysctl", "-n", "machdep.cpu.brand_string")
    if sys.platform.startswith("linux"):
        with contextlib.suppress(OSError):
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    return platform.processor()


def _memory_gb() -> float | None:
    if sys.platform == "darwin":
        size = _run("sysctl", "-n", "hw.memsize")
        return round(int(size) / 2**30, 1) if size.isdigit() else None
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (AttributeError, ValueError, OSError):
        return None


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "missing"


def machine_info() -> dict[str, Any]:
    """What the numbers were measured on (no host name, no user name)."""
    system = platform.system()
    release = platform.mac_ver()[0] if system == "Darwin" else platform.release()
    return {
        "system": "macOS" if system == "Darwin" else system,
        "release": release,
        "model": _run("sysctl", "-n", "hw.model") if system == "Darwin" else "",
        "processor": _processor(),
        "architecture": platform.machine(),
        "cores": os.cpu_count(),
        "memory_gb": _memory_gb(),
    }


def versions() -> dict[str, str]:
    commit = _run("git", "-C", str(REPOSITORY), "rev-parse", "--short=12", "HEAD")
    return {
        "sci2audio": __version__,
        "commit": commit or "unknown",
        "python": platform.python_version(),
        "torch": _version("torch"),
        "kokoro": _version("kokoro"),
        "misaki": _version("misaki"),
    }


def machine_label(machine: dict[str, Any]) -> str:
    parts = [f"{machine['system']} {machine['release']}".strip()]
    if machine.get("model"):
        parts.append(machine["model"])
    if machine.get("processor"):
        parts.append(machine["processor"])
    if machine.get("cores"):
        parts.append(f"{machine['cores']} cores")
    if machine.get("memory_gb"):
        parts.append(f"{machine['memory_gb']:g} GB")
    return ", ".join(parts)


def available_devices() -> list[str]:
    """The devices torch can use here, in the order the engine picks by itself (D-282)."""
    import torch

    found = []
    if torch.backends.mps.is_available():
        found.append("mps")
    if torch.cuda.is_available():
        found.append("cuda")
    return [*found, "cpu"]


def kokoro_on(models: Path, device: str) -> VoiceSource:
    """The app's Kokoro voice, made on one named device."""
    return dataclasses.replace(
        kokoro_voice(models),
        make=lambda: create_kokoro_engine(models, EngineConfig(device=device)),
    )


# ---- measuring ---------------------------------------------------------------------------


def measure_voices(
    voice: VoiceSource, voices: Sequence[str], folder: Path, clock: Clock
) -> dict[str, Any]:
    """Part A on one device: model load once, then each voice on the paragraph."""
    started = clock()
    engine = voice.make()
    load = clock() - started
    session = engine.createSession()
    results = []
    try:
        for voice_id in voices:
            speak_to_wav(session, PARAGRAPH[0], voice_id, folder / "warm-up.wav")
            characters, audio, work = 0, 0.0, 0.0
            for n, sentence in enumerate(PARAGRAPH):
                started = clock()
                audio += speak_to_wav(session, sentence, voice_id, folder / f"{voice_id}-{n}.wav")
                work += clock() - started
                characters += len(sentence)
            results.append(
                {
                    "voice": voice_id,
                    "characters": characters,
                    "seconds": round(work, 3),
                    "audio_seconds": round(audio, 3),
                    "characters_per_second": round(characters / work, 1) if work else None,
                    "realtime_factor": round(audio / work, 2) if work else None,
                }
            )
    finally:
        session.dispose()
        voice.release(engine)
    return {"model_load_seconds": round(load, 2), "voices": results}


class _Watcher:
    """The audio job's progress callback: time-stamps every event, prints a line now and
    then so a long run is seen to be alive."""

    def __init__(self, clock: Clock, say: Callable[[str], None]) -> None:
        self.clock = clock
        self.say = say
        self.events: list[Event] = []
        self._tenth = -1

    def __call__(self, progress: AudioProgress) -> None:
        event = Event(
            self.clock(),
            str(progress.phase),
            progress.characters_done,
            progress.characters_total,
            progress.seconds_left,
        )
        if not self.events or self.events[-1].phase != event.phase:
            self.say(f"    {event.phase}")
        self.events.append(event)
        if event.phase == Phase.SPEAKING and event.characters_total:
            tenth = event.characters_done * 10 // event.characters_total
            if tenth != self._tenth and tenth < 10:
                self._tenth = tenth
                left = (
                    "measuring"
                    if event.seconds_left is None
                    else f"about {event.seconds_left:.0f} s left"
                )
                self.say(f"      {tenth * 10:3d} % of the characters, {left}")


def measure_job(
    voice: VoiceSource, paper: Path, folder: Path, clock: Clock, say: Callable[[str], None]
) -> dict[str, Any]:
    """Part B on one device: the audio job on `paper` from a cold cache."""
    watcher = _Watcher(clock, say)
    settings = JobSettings(output_folder=folder / "out")
    started = clock()
    job = run_audio_job(
        paper, settings, folder / "work", voice=voice, progress=watcher, clock=clock
    )
    whole = clock() - started
    events = watcher.events
    times = phase_times(events)
    speaking_start = next(e.at for e in events if e.phase == Phase.SPEAKING)
    speaking_end = next(e.at for e in events if e.phase == Phase.ENCODING)
    speaking = speaking_end - speaking_start
    characters = max((e.characters_total for e in events if e.phase == Phase.SPEAKING), default=0)
    preparation = sum(times.get(p, 0.0) for p in (Phase.READING, Phase.LAYOUT, Phase.TEXT_STEPS))
    encoding = times.get(Phase.ENCODING, 0.0)
    return {
        "paper": paper.stem,
        "pages": len(job.result.document.content.pages),
        "characters": characters,
        "chunks": job.spoken + job.reused,
        "skipped": len(job.skipped),
        "whole_seconds": round(whole, 2),
        "phases": times,
        "preparation_seconds": round(preparation, 3),
        "voice_load_seconds": times.get(Phase.LOADING_VOICE, 0.0),
        "speaking_seconds": round(speaking, 2),
        "encoding_seconds": encoding,
        "characters_per_second_job": (
            None if job.characters_per_second is None else round(job.characters_per_second, 1)
        ),
        "characters_per_second_speaking": round(characters / speaking, 1) if speaking else None,
        "audio_seconds": round(job.duration, 2),
        "realtime_factor_speaking": round(job.duration / speaking, 2) if speaking else None,
        "realtime_factor_whole": round(job.duration / whole, 2) if whole else None,
        "encoding_times_realtime": round(job.duration / encoding, 1) if encoding else None,
        "estimate": estimate_accuracy(events, speaking_end),
        "chunk_times": chunk_times(events),
    }


# ---- budget and rows ---------------------------------------------------------------------


def budget(jobs: Sequence[dict[str, Any]], app_device: str) -> list[dict[str, Any]]:
    """The performance budget (D-286), checked on this run; None = not judged here."""
    lines = []
    for job in jobs:
        device = job["device"]
        prep = job["preparation_seconds"] / max(job["pages"], 1)
        lines.append(
            {
                "device": device,
                "target": "a 20-page paper prepared in under 30 s (enforced nightly)",
                "measured": f"{prep:.2f} s per page ({prep * 20:.1f} s for 20 pages)",
                "met": prep <= PREPARATION_BUDGET,
            }
        )
        rtf = job["realtime_factor_speaking"]
        own = device == app_device  # D-286 holds the app's own device to it, no other
        lines.append(
            {
                "device": device,
                "target": "speech faster than real time on the MacBook Pro M4, app's device",
                "measured": f"real-time factor {rtf}"
                + ("" if own else f" (the app uses {app_device} here)"),
                "met": None if rtf is None or not own else rtf >= 1,
                "reference": own,
            }
        )
        worst = job["estimate"].get("largest_abs_error_with_a_minute_left")
        lines.append(
            {
                "device": device,
                "target": "the time estimate within ±25 % while a minute or more is left",
                "measured": "less than a minute of speech after the first estimate"
                if worst is None
                else f"largest error {worst:+.0%}".replace("+", "±"),
                "met": None if worst is None else worst <= ESTIMATE_BUDGET,
            }
        )
        times = job["encoding_times_realtime"]
        lines.append(
            {
                "device": device,
                "target": "encoding at least 50 times faster than real time",
                "measured": f"{times} times",
                "met": None if times is None else times >= ENCODING_BUDGET,
            }
        )
    return lines


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.0%}"


def _estimate_cell(estimate: dict[str, Any]) -> str:
    if not estimate["shown"]:
        return "never shown"
    first = estimate["first"]
    median = estimate["median_abs_error"]
    largest = estimate["largest_abs_error"]
    return (
        f"first at {first['done']:.0%} done: {_percent(first['error'])}; "
        f"at 25/50/75 %: "
        + "/".join(
            _percent(s["error"]) if s else "n/a"
            for s in (estimate["at_25"], estimate["at_50"], estimate["at_75"])
        )
        + f"; median {'n/a' if median is None else f'{median:.0%}'}, "
        f"largest {'n/a' if largest is None else f'{largest:.0%}'}"
    )


def markdown_rows(result: dict[str, Any]) -> dict[str, list[str]]:
    """Rows for the two speed-script tables of `docs/baseline.md`."""
    machine = machine_label(result["machine"])
    date = result["date"][:10]
    torch = result["versions"]["torch"]
    commit = result["versions"]["commit"]
    voices = [
        f"| {machine} | {part['device']}, torch {torch} | {v['voice']} | "
        f"{v['characters_per_second']} | {v['realtime_factor']} | "
        f"{part['model_load_seconds']} s | {date} | {commit} |"
        for part in result["voice"]
        for v in part["voices"]
    ]
    jobs = [
        f"| {machine} | {job['device']}, torch {torch} | {job['paper']} ({job['pages']} pages, "
        f"{job['characters']:,} characters) | {job['whole_seconds']} s | "
        f"{job['preparation_seconds']:.2f} s | {job['voice_load_seconds']:.1f} s | "
        f"{job['speaking_seconds']} s ({job['characters_per_second_job']} characters per "
        f"second) | {job['encoding_seconds']:.1f} s | {job['audio_seconds']} s | "
        f"{job['realtime_factor_speaking']} | {_estimate_cell(job['estimate'])} | "
        f"{date} | {commit} |"
        for job in result["job"]
    ]
    return {"voice": voices, "job": jobs}


# ---- the command -------------------------------------------------------------------------


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scripts/speed.py",
        description="Measure how fast sci2audio speaks on this machine (offline).",
    )
    parser.add_argument(
        "--models-folder",
        type=Path,
        help="where `sci2audio voices download` put the voice files (default: the app's)",
    )
    parser.add_argument(
        "--device",
        action="append",
        choices=("auto", *DEVICE_ORDER),
        help="a torch device; repeat for several (default: every device this machine has)",
    )
    parser.add_argument(
        "--voice",
        action="append",
        help=f"a voice id; repeat for several (default: {DEFAULT_VOICE})",
    )
    parser.add_argument(
        "--all-voices", action="store_true", help="every English voice (the voice part only)"
    )
    parser.add_argument(
        "--paper",
        help=f"a corpus paper name or a file (default: {DEFAULT_PAPER})",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help=f"the short paper {QUICK_PAPER} instead of {DEFAULT_PAPER}",
    )
    parser.add_argument("--skip-job", action="store_true", help="only the voice part")
    parser.add_argument(
        "--json",
        type=Path,
        help="where to write the results (default: speed-<date and time>.json here)",
    )
    return parser.parse_args(argv)


def resolve_paper(name: str) -> Path:
    """A corpus paper by name, or a file of a type the job reads (the job's own check, so
    every format it learns is accepted here too); SpeedError or JobError otherwise."""
    corpus = PAPERS / f"{name}.pdf"
    if corpus.is_file():
        return corpus
    given = Path(name)
    if given.is_file():
        check_readable(given)
        return given
    names = ", ".join(sorted(p.stem for p in PAPERS.glob("*.pdf")))
    raise SpeedError(f"there is no paper {name!r}; give a file or one of: {names}")


def json_target(asked: Path | None) -> Path:
    """Where the results go, checked before any work: its folder is made if missing and
    must be writable, and the path must not be a folder."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    target = asked or Path(f"speed-{stamp}.json")
    if target.is_dir():
        raise SpeedError(f"{target} is a folder; give a file name for --json")
    folder = target.parent
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SpeedError(f"cannot make the folder {folder}: {error.strerror or error}") from error
    if not os.access(folder, os.W_OK):
        raise SpeedError(f"cannot write into {folder}; give another --json path")
    return target


def resolve_devices(asked: Sequence[str] | None, available: Sequence[str]) -> list[str]:
    if not asked:
        return list(available)
    devices = []
    for device in asked:
        named = available[0] if device == "auto" else device
        if named not in available:
            raise SpeedError(
                f"this machine has no {named} device for torch; it has: {', '.join(available)}"
            )
        if named not in devices:
            devices.append(named)
    return devices


def resolve_voices(args: argparse.Namespace) -> list[str]:
    known = [voice.id for voice in ENGLISH_VOICES]
    if args.all_voices:
        return known
    asked = args.voice or [DEFAULT_VOICE]
    if unknown := [v for v in asked if v not in known]:
        raise SpeedError(f"unknown voice {unknown[0]!r}; the voices are: {', '.join(known)}")
    return list(dict.fromkeys(asked))


@contextlib.contextmanager
def _offline(attempts: list[str]) -> Iterator[None]:
    with no_network() as seen:
        try:
            yield
        finally:
            attempts.extend(seen)


def measure(
    args: argparse.Namespace,
    *,
    voice_for: VoiceFor,
    devices: Sequence[str],
    clock: Clock,
    say: Callable[[str], None],
) -> dict[str, Any]:
    """Both parts on every device; the result as written to the JSON file."""
    models = args.models_folder or default_models_folder()
    voices = resolve_voices(args)
    paper = resolve_paper(args.paper or (QUICK_PAPER if args.quick else DEFAULT_PAPER))
    app_device = devices[0]
    result: dict[str, Any] = {
        "format": FORMAT,
        "version": VERSION,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "machine": machine_info(),
        "versions": versions(),
        "app_device": app_device,
        "options": {
            "devices": list(devices),
            "voices": voices,
            "paper": None if args.skip_job else paper.stem,
        },
        "voice": [],
        "job": [],
    }
    attempts: list[str] = []
    with tempfile.TemporaryDirectory(prefix="sci2audio-speed-") as temp, _offline(attempts):
        for device in devices:
            folder = Path(temp) / device
            folder.mkdir()
            say(f"{device}: the voice alone ({len(voices)} voice{'s' * (len(voices) > 1)})")
            part = measure_voices(voice_for(models, device), voices, folder, clock)
            result["voice"].append({"device": device, **part})
            for v in part["voices"]:
                say(
                    f"    {v['voice']}: {v['characters_per_second']} characters per second, "
                    f"{v['realtime_factor']} times real time"
                )
            if args.skip_job:
                continue
            say(f"{device}: the audio job on {paper.stem}")
            job = measure_job(voice_for(models, device), paper, folder / "job", clock, say)
            result["job"].append({"device": device, **job})
    result["network_attempts"] = attempts
    result["budget"] = budget(result["job"], app_device)
    result["markdown"] = markdown_rows(result)
    return result


def summary(result: dict[str, Any]) -> list[str]:
    lines = [
        "",
        f"Machine: {machine_label(result['machine'])}",
        f"sci2audio {result['versions']['sci2audio']} ({result['versions']['commit']}), "
        f"torch {result['versions']['torch']}, kokoro {result['versions']['kokoro']}; "
        f"the app picks {result['app_device']} by itself",
    ]
    for job in result["job"]:
        lines += [
            "",
            f"Audio job on {job['device']}: {job['paper']}, {job['pages']} pages, "
            f"{job['characters']:,} characters, {job['audio_seconds']:.0f} s of audio",
            f"  whole job {job['whole_seconds']:.1f} s: preparation "
            f"{job['preparation_seconds']:.2f} s, voice load {job['voice_load_seconds']:.1f} s, "
            f"speaking {job['speaking_seconds']:.1f} s, encoding {job['encoding_seconds']:.1f} s",
            f"  {job['characters_per_second_job']} characters per second (the job's own "
            f"measure), {job['realtime_factor_speaking']} times real time while speaking",
            f"  estimate: {_estimate_cell(job['estimate'])}",
        ]
    lines += ["", "Performance budget (docs/baseline.md):"]
    for line in result["budget"]:
        mark = {True: "met", False: "NOT met", None: "not judged"}[line["met"]]
        lines.append(f"  [{mark}] {line['device']}: {line['target']}: {line['measured']}")
    if result["network_attempts"]:
        lines += ["", f"Blocked network attempts: {result['network_attempts']}"]
    lines += ["", "Rows for docs/baseline.md:", *result["markdown"]["voice"]]
    lines += result["markdown"]["job"]
    return lines


def main(
    argv: Sequence[str] | None = None,
    *,
    voice_for: VoiceFor | None = None,
    devices: Callable[[], list[str]] = available_devices,
    clock: Clock = time.perf_counter,
    say: Callable[[str], None] = lambda line: print(line, flush=True),
) -> int:
    """Run the script; 0 when it measured, 1 with a message when it could not."""
    args = parse(argv)
    try:
        if voice_for is None:
            models = args.models_folder or default_models_folder()
            if missing := missing_files(models):
                raise SpeedError(
                    f"{len(missing)} voice file(s) are missing in {models}; run "
                    "`uv run sci2audio voices download` (or give --models-folder)"
                )
            voice_for = kokoro_on
            # torch and kokoro warn about their own internals on every load; not ours to fix
            warnings.filterwarnings("ignore", category=UserWarning, module=r"torch\.")
            warnings.filterwarnings("ignore", category=FutureWarning, module=r"torch\.")
        target = json_target(args.json)
        chosen = resolve_devices(args.device, devices())
        result = measure(args, voice_for=voice_for, devices=chosen, clock=clock, say=say)
    except (SpeedError, JobError) as error:
        say(f"speed: {error}")
        return 1
    except EngineError as error:  # the voice itself failed in the voice part
        say(f"speed: the voice failed: {error}")
        return 1
    for line in summary(result):  # on screen first: a failing write never loses the rows
        say(line)
    try:
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as error:
        say(f"\nspeed: could not write {target}: {error.strerror or error}")
        return 1
    say(f"\nAll numbers: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
