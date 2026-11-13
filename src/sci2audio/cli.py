"""The command line (#72, WI-03): `script`, `convert`, `voices` and `clean`.

    sci2audio script FILE           the listening script and the report; no voice needed
    sci2audio convert FILE          the audiobook; running it again continues (WI-02)
    sci2audio voices                the voices, and whether their files are installed
    sci2audio voices download       shows what it fetches, then asks first (VA-03)
    sci2audio clean FILE            removes FILE's speech cache

Every command is one row of `COMMANDS`: a function that adds its arguments and a function
that runs it (D-211). `main` builds the real `CliEnv`; tests call `run` with their own. The
command line reads the settings file as defaults and never writes it (D-213), counts
chapters from 1 (D-214), prints progress on stderr and the result on stdout (D-220), and
ends with one of the exit codes in `Exit` (D-212), never with a traceback.

Nothing here opens a network connection except `voices download`, after consent, through
`voices.download_voice_files` (Q12, D-221). `sci2audio.web` and the voice engine are only
imported when a command needs them, so `sci2audio --version` starts at once.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import IntEnum
from pathlib import Path
from typing import IO, Any, TextIO
from urllib.parse import urlsplit

from sci2audio import __version__
from sci2audio.app import (
    AudioJob,
    AudioProgress,
    JobBusyError,
    JobCancelledError,
    JobError,
    JobRunner,
    JobSettings,
    OutputExistsError,
    Phase,
    ScriptJob,
    UnreadableFileError,
    UnsupportedFileError,
    VoiceSource,
    clean_work_folder,
    default_config_file,
    default_models_folder,
    default_work_folder,
    find_chapters,
    kokoro_voice,
    load_settings,
    script_files,
)
from sci2audio.app.chunks import CHUNKS, cache_size
from sci2audio.app.job import read_document
from sci2audio.app.settings import MAX_SPEED, MIN_SPEED
from sci2audio.output import OutputSettings
from sci2audio.textprep import Category
from sci2audio.voices import (
    DEFAULT_VOICE,
    ENGLISH_VOICES,
    DownloadError,
    DownloadPlan,
    NetworkError,
    RemoteFile,
    download_plan,
    download_voice_files,
    missing_files,
)
from sci2audio.voices.download import Fetch

PROG = "sci2audio"


class Exit(IntEnum):
    """The exit codes (D-212); the README lists them."""

    OK = 0
    FAILED = 1  # any other failure: a write, the disk, ffmpeg, the voice, the download
    USAGE = 2  # a bad option or value (argparse uses 2 too)
    NOT_FOUND = 3  # FILE does not exist or is not a file
    UNSUPPORTED = 4  # a file type sci2audio can't read
    UNREADABLE = 5  # damaged, password-protected or can't be opened
    NO_VOICE = 6  # the voice files are not installed
    EXISTS = 7  # output files exist and --overwrite was not given
    BUSY = 8  # another sci2audio job is working on this file
    INTERRUPTED = 130  # Ctrl-C (128 + SIGINT)


EXIT_CODES_HELP = """\
exit codes:
  0    done (problems listed in the report do not change it)
  1    failed for another reason (a write, the disk, ffmpeg, the voice, the download)
  2    a bad option or value
  3    the file does not exist or is not a file
  4    a file type sci2audio can't read
  5    the file is damaged, protected or can't be opened
  6    the voice files are not installed (run: sci2audio voices download)
  7    output files exist (add --overwrite to replace them)
  8    another sci2audio job is working on this file
  130  stopped with Ctrl-C
"""

# Where the two download hosts send the files (D-141); shown before consent.
REDIRECT_HOSTS = {
    "huggingface.co": "its CDN and its LFS/Xet storage",
    "github.com": "objects.githubusercontent.com",
}


class CliError(Exception):
    """Stops a command with a message and an exit code."""

    def __init__(self, message: str, code: Exit) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class CliEnv:
    """Everything a command touches outside its arguments, so tests can replace it."""

    out: TextIO
    err: TextIO
    ask: Callable[[str], str]  # asks a question on the terminal; EOFError without one
    interactive: bool  # a person can answer questions (stdin is a terminal)
    live: bool  # stderr is a terminal: progress is rewritten in one line
    runner: JobRunner = field(default_factory=JobRunner)
    config_file: Callable[[], Path] = default_config_file
    models_folder: Callable[[], Path] = default_models_folder
    work_folder: Callable[[Path], Path] = default_work_folder
    voice_source: Callable[[Path], VoiceSource] = kokoro_voice
    missing_voice_files: Callable[[Path], list[RemoteFile]] = missing_files
    fetch: Fetch | None = None  # the download's fetch; None = the real one

    @classmethod
    def real(cls) -> CliEnv:
        for stream in (sys.stdout, sys.stderr):
            _never_fail_on_characters(stream)
        return cls(
            out=sys.stdout,
            err=sys.stderr,
            ask=_ask,
            interactive=_is_terminal(sys.stdin),
            live=_is_terminal(sys.stderr),
        )


def _ask(question: str) -> str:
    """Ask on stderr and read the answer from stdin; EOFError at the end of input."""
    sys.stderr.write(question)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line


def _never_fail_on_characters(stream: IO[str]) -> None:
    """A console that can't show a character prints "?" instead of failing (D-225).

    A redirected stdout on Windows uses the locale's code page (cp1252), which lacks many
    letters of names and maths; the encoding stays as it is, so pipes and files keep the
    system's choice."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        with contextlib.suppress(ValueError, OSError):
            reconfigure(errors="replace")


def _is_terminal(stream: IO[str] | None) -> bool:
    try:
        return stream is not None and stream.isatty()
    except (ValueError, OSError):
        return False


# ---- parsing --------------------------------------------------------------------------


class _Formatter(argparse.HelpFormatter):
    """Wraps one-paragraph texts; keeps texts with line breaks (the epilogs) as written."""

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        if "\n" in text.strip():
            return text
        return super()._fill_text(text, width, indent)


class _Parser(argparse.ArgumentParser):
    """argparse, writing to the env's streams instead of sys.stdout and sys.stderr."""

    def __init__(self, *args: Any, env: CliEnv, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", _Formatter)
        super().__init__(*args, **kwargs)
        self.env = env

    def _print_message(self, message: str, file: IO[str] | None = None) -> None:
        if not message:
            return
        if file is None or file is sys.stdout:
            file = self.env.out
        elif file is sys.stderr:
            file = self.env.err
        file.write(message)

    def subcommands(self, **kwargs: Any) -> argparse._SubParsersAction[_Parser]:
        return self.add_subparsers(parser_class=_parser_class(self.env), **kwargs)


def _parser_class(env: CliEnv) -> Callable[..., _Parser]:
    def make(**kwargs: Any) -> _Parser:
        return _Parser(env=env, **kwargs)

    return make


def chapter_numbers(text: str) -> frozenset[int] | None:
    """`--chapters`: "all" (None here, resolved once the chapters are known) or numbers
    and ranges counted from 1 ("1,3-5"), as `JobSettings.chapters` indices from 0."""
    if text.strip().lower() == "all":
        return None
    numbers: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        first, dash, last = part.partition("-")
        try:
            low = int(first)
            high = int(last) if dash else low
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"{part!r} is not a chapter number; use numbers and ranges like 1,3-5, or all"
            ) from None
        if low < 1 or high < low:
            raise argparse.ArgumentTypeError(
                f"{part!r}: chapters are counted from 1, and a range goes upwards"
            )
        if high - low > 10_000:
            raise argparse.ArgumentTypeError(f"{part!r}: that range is too long")
        numbers.update(range(low - 1, high))
    return frozenset(numbers)


def categories(text: str) -> frozenset[Category]:
    """`--on` / `--off`: one or more category names, comma-separated."""
    found = set()
    for name in text.split(","):
        name = name.strip().lower()
        try:
            found.add(Category(name))
        except ValueError:
            known = ", ".join(category.value for category in Category)
            raise argparse.ArgumentTypeError(
                f"unknown category {name!r}; the categories are: {known}"
            ) from None
    return frozenset(found)


def speed(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = float("nan")
    if not MIN_SPEED <= value <= MAX_SPEED:  # also false for nan
        raise argparse.ArgumentTypeError(
            f"the speed must be a number from {MIN_SPEED} to {MAX_SPEED}, got {text!r}"
        )
    return value


def _categories_help() -> str:
    lines = ["text-step categories (for --on and --off):"]
    for category in Category:
        start = "on" if category.on_by_default else "off"
        lines.append(f"  {category.value:<20} {category.label} (starts {start})")
    lines.append(
        '  "on" means sci2audio handles that kind of text (e.g. citations are left out);\n'
        '  "off" means it is read as printed.'
    )
    return "\n".join(lines)


def _add_job_options(parser: _Parser) -> None:
    """The options `script` and `convert` share."""
    parser.add_argument("file", type=Path, metavar="FILE", help="the file to read")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FOLDER",
        help="where the files go (default: next to FILE)",
    )
    parser.add_argument(
        "--chapters",
        type=chapter_numbers,
        metavar="LIST",
        default=argparse.SUPPRESS,
        help="chapters to read, counted from 1 as `script` lists them: 1,3-5 or all "
        "(default: every chapter but the reference list)",
    )
    parser.add_argument(
        "--on",
        type=categories,
        action="append",
        default=[],
        metavar="CATEGORY",
        help="switch a text-step category on (repeat, or separate with commas)",
    )
    parser.add_argument(
        "--off",
        type=categories,
        action="append",
        default=[],
        metavar="CATEGORY",
        help="switch a text-step category off: its text is read as printed",
    )
    parser.add_argument(
        "--language", metavar="TAG", help="en, en-GB, ... (default: the file's own)"
    )
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    parser.add_argument(
        "--work-folder",
        type=Path,
        metavar="FOLDER",
        help="the job's working folder (default: in the cache folder)",
    )
    parser.add_argument(
        "--ignore-settings",
        action="store_true",
        help="use the built-in defaults, not the settings saved by the interface",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="no progress lines")


def _add_models_option(parser: _Parser, *, default: Any = None) -> None:
    parser.add_argument(
        "--models-folder",
        type=Path,
        metavar="FOLDER",
        default=default,
        help="where the voice files are (default: in the user's data folder)",
    )


def add_script(parser: _Parser) -> None:
    _add_job_options(parser)


def add_convert(parser: _Parser) -> None:
    _add_job_options(parser)
    parser.add_argument(
        "--voice", metavar="ID", help=f"a voice from `{PROG} voices` (default: {DEFAULT_VOICE})"
    )
    parser.add_argument(
        "--speed", type=speed, metavar="X", help=f"{MIN_SPEED} to {MAX_SPEED} (default: 1.0)"
    )
    parser.add_argument(
        "--format",
        choices=("both", "m4b", "mp3"),
        default="both",
        help="M4B with chapter marks, one MP3 per chapter, or both (default: both)",
    )
    parser.add_argument(
        "--with-script",
        action="store_true",
        help="also write the listening script and the report",
    )
    _add_models_option(parser)


def add_voices(parser: _Parser) -> None:
    _add_models_option(parser)
    actions = parser.subcommands(dest="action", metavar="ACTION")
    download = actions.add_parser(
        "download",
        help="download the voice files (about 355 MB), after showing what and asking",
        description="Download the voice files: the Kokoro model with its English voices and "
        "the spaCy English model. Shows every source, size and licence first, then asks.",
    )
    _add_models_option(download, default=argparse.SUPPRESS)  # keeps `voices --models-folder`
    download.add_argument(
        "-y", "--yes", action="store_true", help="agree to the download without being asked"
    )


def add_clean(parser: _Parser) -> None:
    parser.add_argument("file", type=Path, metavar="FILE", help="the file whose speech cache goes")
    parser.add_argument(
        "--work-folder",
        type=Path,
        metavar="FOLDER",
        help="the job's working folder (default: in the cache folder)",
    )


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    description: str
    add_arguments: Callable[[_Parser], None]
    run: Callable[[argparse.Namespace, CliEnv], Exit]
    epilog: Callable[[], str] | None = None


def build_parser(env: CliEnv) -> _Parser:
    parser = _Parser(
        prog=PROG,
        env=env,
        description="Turn scientific texts into faithful, offline audiobooks.",
        epilog=EXIT_CODES_HELP,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    commands = parser.subcommands(dest="command", metavar="COMMAND")
    for command in COMMANDS:
        sub = commands.add_parser(
            command.name,
            help=command.help,
            description=command.description,
            epilog=command.epilog() if command.epilog else None,
        )
        command.add_arguments(sub)
        sub.set_defaults(run=command.run)
    return parser


# ---- the shared job set-up --------------------------------------------------------------


def _source(file: Path) -> Path:
    if not file.exists():
        raise CliError(f"{file}: no such file", Exit.NOT_FOUND)
    if not file.is_file():
        raise CliError(f"{file}: not a file", Exit.NOT_FOUND)
    return file


def _work_folder(args: argparse.Namespace, env: CliEnv, source: Path) -> Path:
    if args.work_folder is not None:
        return args.work_folder
    try:
        return env.work_folder(source)
    except OSError as error:
        raise CliError(
            f"{source}: cannot be read ({error.strerror or error})", Exit.UNREADABLE
        ) from error


def _settings(args: argparse.Namespace, env: CliEnv) -> JobSettings:
    """The settings file's choices (D-213), with this run's options on top. `--chapters
    all` is left empty here: the caller resolves it with `_all_chapters` once every check
    that needs no reading is done (D-222)."""
    base = JobSettings()
    if not args.ignore_settings:
        base, warnings = load_settings(env.config_file())
        for warning in warnings:
            env.err.write(f"{PROG}: warning: {warning}\n")
    on = frozenset().union(*args.on)
    off = frozenset().union(*args.off)
    if both := on & off:
        names = ", ".join(sorted(category.value for category in both))
        raise CliError(f"{names}: switched both on and off; choose one", Exit.USAGE)
    changes: dict[str, Any] = {"switched_off": (base.switched_off - on) | off}
    if args.output is not None:
        changes["output_folder"] = args.output
    if args.language is not None:
        changes["language"] = args.language
    if hasattr(args, "chapters"):
        changes["chapters"] = args.chapters if args.chapters is not None else frozenset()
    for name in ("voice", "speed"):
        if getattr(args, name, None) is not None:
            changes[name] = getattr(args, name)
    try:
        settings = replace(base, **changes)  # checks every value again
    except ValueError as error:
        raise CliError(str(error), Exit.USAGE) from error
    return settings


def _every_chapter_asked(args: argparse.Namespace) -> bool:
    return hasattr(args, "chapters") and args.chapters is None  # --chapters all


def _all_chapters(source: Path, settings: JobSettings) -> JobSettings:
    """`--chapters all`: the chapter count is only known once the file is read. (The job
    reads it again; Issue #112 lets `JobSettings` say "every chapter" instead.)"""
    document = read_document(source, settings, lambda phase: None)
    chapters = frozenset(chapter.index for chapter in find_chapters(document))
    return replace(settings, chapters=chapters)


def _ignored(env: CliEnv, ignored: Sequence[int], count: int) -> None:
    for index in ignored:
        env.err.write(
            f"{PROG}: warning: there is no chapter {index + 1} (the document has chapters "
            f"1 to {count}); ignored\n"
        )


# ---- progress ---------------------------------------------------------------------------

PHASE_TEXT = {
    Phase.READING: "Reading the file",
    Phase.LAYOUT: "Finding the reading order",
    Phase.TEXT_STEPS: "Preparing the text",
    Phase.LOADING_VOICE: "Loading the voice",
    Phase.SPEAKING: "Speaking",
    Phase.ENCODING: "Writing the audio files",
    Phase.WRITING: "Writing the script and the report",
}


class Progress:
    """Progress lines on stderr (D-220): one line rewritten in place on a terminal; one
    line per phase and per chapter otherwise; nothing with --quiet. Thread-safe."""

    def __init__(self, env: CliEnv, quiet: bool) -> None:
        self.env = env
        self.quiet = quiet
        self.width = 0  # of the line shown in place
        self.last = ""  # the last line written without a terminal
        self.lock = threading.Lock()

    def show(self, text: str, *, key: str | None = None) -> None:
        """Show `text`; without a terminal only when `key` (default: the text) changed."""
        if self.quiet:
            return
        with self.lock:
            if self.env.live:
                pad = " " * max(0, self.width - len(text))
                self.env.err.write(f"\r{text}{pad}")
                self.width = len(text)
            else:
                key = text if key is None else key
                if key != self.last:
                    self.env.err.write(text + "\n")
                    self.last = key
            self.env.err.flush()

    def end(self) -> None:
        """Finish the line shown in place, before other output."""
        with self.lock:
            if self.width:
                self.env.err.write("\n")
                self.env.err.flush()
                self.width = 0

    def phase(self, phase: Phase) -> None:
        if phase in PHASE_TEXT:
            self.show(PHASE_TEXT[phase] + " ...")

    def audio(self, event: AudioProgress) -> None:
        if event.phase is not Phase.SPEAKING or event.chapter is None:
            self.phase(event.phase)
            return
        left = _minutes(event.seconds_left)
        text = (
            f"Speaking chapter {event.chapter + 1}, {_short(event.chapter_title)}: "
            f"{event.chunks_done} of {event.chunks_total} sentences, {left}"
        )
        self.show(text, key=f"chapter {event.chapter}")

    def download(self, done: int, total: int, target: str) -> None:
        name = target.rsplit("/", 1)[-1]
        tenth = done * 10 // total if total else 10
        self.show(f"Downloading: {_mb(done)} of {_mb(total)} ({name})", key=f"{name} {tenth}")


def _minutes(seconds: float | None) -> str:
    if seconds is None:
        return "measuring the speed"
    if seconds < 90:
        return "about a minute left"
    if seconds < 90 * 60:
        return f"about {round(seconds / 60)} min left"
    return f"about {seconds / 3600:.1f} hours left"


def _short(title: str, limit: int = 40) -> str:
    title = " ".join(title.split())
    return title if len(title) <= limit else title[: limit - 3] + "..."


def _mb(size: int) -> str:
    return f"{size / 1_000_000:,.1f} MB" if size < 10_000_000 else f"{size / 1_000_000:,.0f} MB"


def _duration(seconds: float) -> str:
    whole = round(seconds)
    hours, rest = divmod(whole, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}"


# ---- script -----------------------------------------------------------------------------


def run_script_command(args: argparse.Namespace, env: CliEnv) -> Exit:
    source = _source(args.file)
    settings = _settings(args, env)
    if _every_chapter_asked(args):
        settings = _all_chapters(source, settings)
    work = _work_folder(args, env, source)
    progress = Progress(env, args.quiet)
    try:
        job = env.runner.run_script(
            source, settings, work, overwrite=args.overwrite, progress=progress.phase
        )
    finally:
        progress.end()
    _print_script(env, job)
    return Exit.OK


def _print_script(env: CliEnv, job: ScriptJob) -> None:
    out = env.out
    report = job.report
    _ignored(env, job.result.ignored_chapters, len(report.chapters))
    out.write("Chapters (choose with --chapters):\n")
    for entry in report.chapters:
        mark = "x" if entry.selected else " "
        note = "  (reference list)" if entry.chapter.references else ""
        said = f"{entry.utterances} sentences" if entry.selected else "not read"
        title = _short(entry.chapter.title, 60)
        out.write(f"  {entry.chapter.index + 1:>3}  [{mark}]  {title}  {said}{note}\n")
    applied = [(count.category.label, count.applied) for count in report.counts if count.applied]
    if applied:
        out.write("Edits that change what is heard:\n")
        for label, number in applied:
            out.write(f"  {label}: {number}\n")
    for step, message in report.problems:
        env.err.write(f"{PROG}: warning: the text step {step} failed and was left out: {message}\n")
    out.write("Wrote:\n")
    for path in job.files.outputs:
        out.write(f"  {path}\n")


# ---- convert ----------------------------------------------------------------------------


def run_convert_command(args: argparse.Namespace, env: CliEnv) -> Exit:
    source = _source(args.file)
    models = args.models_folder or env.models_folder()
    if env.missing_voice_files(models):
        raise CliError(
            f"the voice files are not installed in {models}; run `{PROG} voices download` first",
            Exit.NO_VOICE,
        )
    voice = env.voice_source(models)
    settings = _settings(args, env)
    voice_id = settings.voice or voice.default_voice
    if voice_id not in voice.voices:
        raise CliError(
            f"there is no voice {voice_id!r}; `{PROG} voices` lists the voices", Exit.USAGE
        )
    if _every_chapter_asked(args):
        settings = _all_chapters(source, settings)
    work = _work_folder(args, env, source)
    output = OutputSettings(mp3=args.format != "m4b", m4b=args.format != "mp3")
    if args.with_script and not args.overwrite:
        # all or nothing: refuse an existing script before any work, as the audio job
        # refuses an existing audiobook before any speech (D-163); the audio job runs
        # first, so a refused audiobook leaves no new script behind
        targets = script_files(source, settings, work).outputs
        if existing := [path.name for path in targets if path.exists()]:
            raise OutputExistsError(
                f"these files exist already: {', '.join(existing)}; choose to replace them"
            )
    progress = Progress(env, args.quiet)
    script: ScriptJob | None = None
    try:
        job = _audio_in_thread(env, progress, source, settings, work, voice, output, args.overwrite)
        if args.with_script:
            script = env.runner.run_script(
                source, settings, work, overwrite=args.overwrite, progress=progress.phase
            )
    finally:
        progress.end()
    _print_audio(env, job, script, work)
    return Exit.OK


def _audio_in_thread(
    env: CliEnv,
    progress: Progress,
    source: Path,
    settings: JobSettings,
    work: Path,
    voice: VoiceSource,
    output: OutputSettings,
    overwrite: bool,
) -> AudioJob:
    """Run the audio job in a worker thread, so the first Ctrl-C can ask it to stop at its
    next cancel point (D-219); a second Ctrl-C stops at once."""
    cancel = threading.Event()
    finished = threading.Event()
    outcome: dict[str, Any] = {}

    def work_on() -> None:
        try:
            outcome["job"] = env.runner.run_audio(
                source,
                settings,
                work,
                voice=voice,
                output_settings=output,
                overwrite=overwrite,
                progress=progress.audio,
                cancel=cancel,
            )
        except BaseException as error:  # handed to the main thread
            outcome["error"] = error
        finally:
            finished.set()

    worker = threading.Thread(target=work_on, name="sci2audio-audio-job", daemon=True)
    try:
        worker.start()  # inside the try: a Ctrl-C while it starts is a first Ctrl-C too
        _wait(finished)
    except KeyboardInterrupt:
        if worker.ident is None:  # it never started: nothing to stop politely
            raise
        cancel.set()
        progress.end()
        env.err.write(f"{PROG}: stopping after the current sentence; finished sentences are kept\n")
        env.err.flush()
        _wait(finished)  # a second Ctrl-C ends the program here
    if "error" in outcome:
        raise outcome["error"]
    job: AudioJob = outcome["job"]
    return job


def _wait(finished: threading.Event) -> None:
    """Wait in short steps, so Ctrl-C is seen at once on every system. (Thread.join can't
    be used: interrupted, it may report a running thread as finished before Python 3.13.)"""
    while not finished.wait(0.1):
        pass


def _print_audio(env: CliEnv, job: AudioJob, script: ScriptJob | None, work: Path) -> None:
    out = env.out
    _ignored(env, job.result.ignored_chapters, len(job.result.chapters))
    total = job.spoken + job.reused
    out.write(
        f"Spoke {job.spoken} of {total} sentences, reused {job.reused} from the last run; "
        f"the book is {_duration(job.duration)} long.\n"
    )
    for item in job.skipped:
        page = f" on page {item.printed_page or item.page}" if item.page else ""
        env.err.write(
            f"{PROG}: warning: the voice could not say this sentence{page}, so it is left out: "
            f"{_short(item.text, 60)!r} ({item.error})\n"
        )
    out.write("Wrote:\n")
    files = [
        *([job.written.m4b] if job.written.m4b else []),
        *job.written.mp3s,
        job.written.readalong,
    ]
    if script is not None:
        files += list(script.files.outputs)
    for path in files:
        out.write(f"  {path}\n")
    if cache := cache_size(work):
        out.write(
            f"The speech cache in {work} holds {_mb(cache)}; it makes a rerun quick. "
            f"`{PROG} clean {_quoted(job.result.document.content.source.name)}` removes it.\n"
        )


def _quoted(name: str) -> str:
    return f'"{name}"' if any(c.isspace() or c in "'\"$&|;<>()" for c in name) else name


# ---- voices -----------------------------------------------------------------------------


def run_voices_command(args: argparse.Namespace, env: CliEnv) -> Exit:
    models = args.models_folder or env.models_folder()
    if args.action == "download":
        return _download(args, env, models)
    out = env.out
    out.write("Voices (Kokoro-82M, English):\n")
    out.write(f"  {'ID':<12} {'NAME':<10} {'ACCENT':<7} GENDER\n")
    for voice in ENGLISH_VOICES:
        default = "  (default)" if voice.id == DEFAULT_VOICE else ""
        out.write(
            f"  {voice.id:<12} {voice.name:<10} {voice.language:<7} {voice.gender}{default}\n"
        )
    missing = env.missing_voice_files(models)
    if missing:
        size = sum(f.size for f in missing)
        out.write(
            f"The voice files are not installed in {models} ({_mb(size)} to download).\n"
            f"Run `{PROG} voices download` to see what is fetched and to agree to it.\n"
        )
    else:
        out.write(f"The voice files are installed in {models}.\n")
    return Exit.OK


def describe_download(plan: DownloadPlan, missing: Sequence[RemoteFile], models: Path) -> str:
    """What the download fetches, from where and under which licence (VA-03, D-221)."""
    lines = [f"The voice download puts these files into {models}:"]
    groups: dict[str, list[RemoteFile]] = {}
    for file in plan.files:
        groups.setdefault(file.licence, []).append(file)
    for licence, files in groups.items():
        hosts = sorted({urlsplit(f.url).hostname or "?" for f in files})
        size = sum(f.size for f in files)
        noun = "file" if len(files) == 1 else "files"
        lines.append(f"- {len(files)} {noun}, {_mb(size)}, from {', '.join(hosts)}")
        lines.append(f"  {licence}")
    lines.append(f"In total {_mb(plan.total_bytes)}.")
    hosts = sorted({urlsplit(f.url).hostname or "" for f in plan.files} & REDIRECT_HOSTS.keys())
    if hosts:
        served = "; ".join(f"{host} from {REDIRECT_HOSTS[host]}" for host in hosts)
        lines.append(f"The hosts hand the files out from their download servers: {served}.")
    lines.append(
        "Every file is checked against its SHA-256 checksum. Nothing about you or your "
        "files is sent."
    )
    if len(missing) < len(plan.files):
        lines.append(
            f"{len(plan.files) - len(missing)} files are in place already; "
            f"{_mb(sum(f.size for f in missing))} remain."
        )
    return "\n".join(lines) + "\n"


def _download(args: argparse.Namespace, env: CliEnv, models: Path) -> Exit:
    plan = download_plan()
    missing = env.missing_voice_files(models)
    if not missing:
        env.out.write(f"The voice files are installed in {models}; nothing to download.\n")
        return Exit.OK
    # the plan and the question go to stderr, beside the progress: with stdout redirected
    # to a file the person still sees what they are asked to agree to
    env.err.write(describe_download(plan, missing, models))
    env.err.flush()
    if not args.yes:
        if not env.interactive:
            raise CliError(
                "the voice download needs your agreement: run it in a terminal, "
                "or add --yes to agree on the command line",
                Exit.USAGE,
            )
        size = _mb(sum(f.size for f in missing))
        try:
            answer = env.ask(f"Download about {size} now? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            env.out.write("Nothing was downloaded.\n")
            return Exit.FAILED
    progress = Progress(env, quiet=False)
    try:
        download_voice_files(models, progress=progress.download, fetch=env.fetch)
    except (NetworkError, DownloadError) as error:
        progress.end()
        raise CliError(
            f"{error}; the files finished so far are kept, so running the download again continues",
            Exit.FAILED,
        ) from error
    finally:
        progress.end()
    env.out.write(f"The voice files are installed in {models}.\n")
    return Exit.OK


# ---- clean ------------------------------------------------------------------------------


def run_clean_command(args: argparse.Namespace, env: CliEnv) -> Exit:
    source = _source(args.file)
    work = _work_folder(args, env, source)
    if not (work / CHUNKS).exists():
        env.out.write(f"{source.name} has no speech cache; nothing to remove.\n")
        return Exit.OK
    freed = clean_work_folder(work)
    env.out.write(f"Removed the speech cache of {source.name} ({_mb(freed)}).\n")
    return Exit.OK


COMMANDS: tuple[Command, ...] = (
    Command(
        "script",
        "write the listening script and the report (no voice needed)",
        "Read FILE and write what the voice would say (FILE.script.txt) and the report of "
        "every change (FILE.report.json, FILE.report.md). Lists the chapters to choose from.",
        add_script,
        run_script_command,
        _categories_help,
    ),
    Command(
        "convert",
        "make the audiobook: an M4B with chapters, an MP3 per chapter and a read-along file",
        "Make the audiobook of FILE. Running the same command again continues an interrupted "
        "run: sentences already spoken are taken from the speech cache.",
        add_convert,
        run_convert_command,
        _categories_help,
    ),
    Command(
        "voices",
        "list the voices; `voices download` installs their files",
        "List the voices and whether their files are installed. `voices download` shows "
        "what it fetches and asks before anything is downloaded.",
        add_voices,
        run_voices_command,
    ),
    Command(
        "clean",
        "remove the speech cache of FILE",
        "Remove the speech cache of FILE (the spoken sentences kept for a quick rerun). The "
        "audiobook and the records stay.",
        add_clean,
        run_clean_command,
    ),
)


# ---- running ----------------------------------------------------------------------------

_JOB_ERRORS: tuple[tuple[type[JobError], Exit, str], ...] = (
    (UnsupportedFileError, Exit.UNSUPPORTED, ""),
    (UnreadableFileError, Exit.UNREADABLE, ""),
    (OutputExistsError, Exit.EXISTS, " (add --overwrite)"),
    (JobBusyError, Exit.BUSY, ""),
    (JobCancelledError, Exit.INTERRUPTED, "; run the same command again to continue"),
)


def _job_error(error: JobError) -> tuple[str, Exit]:
    for kind, code, hint in _JOB_ERRORS:
        if isinstance(error, kind):
            return f"{error}{hint}", code
    return str(error), Exit.FAILED


def run(argv: Sequence[str] | None, env: CliEnv) -> int:
    """Parse `argv`, run the command and return its exit code (argparse may exit with 0
    for --help and --version, or 2 for a bad option)."""
    parser = build_parser(env)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(env.err)
        return int(Exit.USAGE)
    try:
        return int(args.run(args, env))
    except CliError as error:
        return _fail(env, str(error), error.code)
    except JobError as error:
        message, code = _job_error(error)
        return _fail(env, message, code)
    except KeyboardInterrupt:
        return _fail(env, "stopped; run the same command again to continue", Exit.INTERRUPTED)
    except Exception as error:  # a bug: one line, never a traceback (D-212)
        return _fail(
            env,
            f"unexpected error, this is a bug in sci2audio ({type(error).__name__}: {error})",
            Exit.FAILED,
        )


def _fail(env: CliEnv, message: str, code: Exit) -> int:
    env.err.write(f"{PROG}: {message}\n")
    env.err.flush()
    return int(code)


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv, CliEnv.real())


if __name__ == "__main__":
    raise SystemExit(main())
