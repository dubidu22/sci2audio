"""Helpers for the command-line tests: a `CliEnv` with its folders in `tmp_path`, text
streams the test reads back, a fake voice and a fake download."""

from __future__ import annotations

import io
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf

from sci2audio.cli import CliEnv, run
from sci2audio.voices import RemoteFile
from sci2audio.voices.download import Fetch

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
SEABORN = CORPUS / "papers" / "joss2021-waskom-seaborn.pdf"
PYMEDPHYS = CORPUS / "papers" / "joss2022-biggs-pymedphys.pdf"
BROKEN = Path(__file__).resolve().parents[1] / "fixtures" / "broken"


@dataclass
class Result:
    code: int
    out: str
    err: str


@dataclass
class Cli:
    """Runs the command line with its folders under `root`; nothing touches the person's."""

    root: Path
    voice: FakeVoice = field(default_factory=FakeVoice)
    voice_installed: bool = True
    interactive: bool = False
    live: bool = False
    answers: list[str] = field(default_factory=list)  # EOFError once used up
    fetch: Fetch | None = None
    missing: Callable[[Path], list[RemoteFile]] | None = None
    asked: list[str] = field(default_factory=list)
    env: CliEnv | None = None

    @property
    def config(self) -> Path:
        return self.root / "config" / "settings.json"

    @property
    def models(self) -> Path:
        return self.root / "models"

    def work(self, source: Path) -> Path:
        return self.root / "work" / source.stem

    def make_env(self, out: io.StringIO, err: io.StringIO) -> CliEnv:
        def ask(question: str) -> str:
            self.asked.append(question)
            if not self.answers:
                raise EOFError
            return self.answers.pop(0)

        def missing(models: Path) -> list[RemoteFile]:
            if self.missing is not None:
                return self.missing(models)
            if self.voice_installed:
                return []
            return [RemoteFile("https://example.test/x", "x", 1, "0" * 64, "MIT")]

        return CliEnv(
            out=out,
            err=err,
            ask=ask,
            interactive=self.interactive,
            live=self.live,
            config_file=lambda: self.config,
            models_folder=lambda: self.models,
            work_folder=self.work,
            voice_source=lambda models: self.voice.source(),
            missing_voice_files=missing,
            fetch=self.fetch,
        )

    def __call__(self, *argv: str | Path) -> Result:
        out, err = io.StringIO(), io.StringIO()
        self.env = self.make_env(out, err)
        try:
            code = run([str(a) for a in argv], self.env)
        except SystemExit as exit_:  # argparse: --help, --version, a bad option
            code = exit_.code if isinstance(exit_.code, int) else 2
        return Result(code, out.getvalue(), err.getvalue())


def small_pdf(folder: Path, lines: Sequence[str] = (), name: str = "note.pdf") -> Path:
    """A one-page PDF with one line per text, in a folder of its own."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    texts: Iterable[str] = lines or ("A short note.", "It has two lines.")
    path.write_bytes(
        make_pdf([Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(texts)])
    )
    return path


def files_in(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []
