"""`sci2audio convert` end to end with the real voice, as a person runs it (#72, PE-02,
WI-02, D-224). Nightly, on all three systems.

The installed command runs in a process of its own on a corpus paper with the voice files
fetched by `prepare_models.py` (SCI2AUDIO_TEST_MODELS). The first run is killed after its
first sentences and run again, which must continue from the speech cache; a third run with
`--overwrite` must speak nothing. The processes get proxies that point at a closed local
port, so any HTTP request they tried would fail. An EPUB (#73) is converted too: the corpus
book cut to three short spine documents (the whole book is about 70 minutes of speech on a
CPU), and its M4B must carry the book's cover.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from sci2audio.output import find_ffmpeg

CORPUS = Path(__file__).parents[1] / "corpus"
PYMEDPHYS = CORPUS / "papers" / "joss2022-biggs-pymedphys.pdf"
TIME_MACHINE = CORPUS / "epub" / "wells-the-time-machine.epub"
KEPT = ("titlepage.xhtml", "imprint.xhtml", "epilogue.xhtml")  # spine documents kept


def models_dir() -> Path:
    folder = os.environ.get("SCI2AUDIO_TEST_MODELS")
    if not folder:
        pytest.skip("SCI2AUDIO_TEST_MODELS is not set (run tests/integration/prepare_models.py)")
    return Path(folder)


def command() -> Path:
    name = "sci2audio.exe" if sys.platform == "win32" else "sci2audio"
    return Path(sys.executable).parent / name


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def offline_env() -> dict[str, str]:
    proxy = f"http://127.0.0.1:{closed_port()}"
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        env[name] = proxy
    return env


def convert_args(out: Path, work: Path, *extra: str, source: Path = PYMEDPHYS) -> list[str]:
    return [
        str(command()),
        "convert",
        str(source),
        "-o",
        str(out),
        "--work-folder",
        str(work),
        "--models-folder",
        str(models_dir()),
        "--ignore-settings",
        *extra,
    ]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=offline_env(),
        check=False,
        timeout=1800,
    )


def spoken_and_reused(stdout: str) -> tuple[int, int, int]:
    found = re.search(r"Spoke (\d+) of (\d+) sentences, reused (\d+)", stdout)
    assert found, stdout
    spoke, total, reused = (int(n) for n in found.groups())
    return spoke, total, reused


@pytest.mark.slow
def test_convert_is_killed_resumes_and_reruns_from_the_cache(tmp_path: Path) -> None:
    out, work = tmp_path / "out", tmp_path / "work"
    chunks = work / "chunks"

    # 1. killed after its first sentences are in the cache
    killed = subprocess.Popen(
        convert_args(out, work, "-q"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=offline_env(),
    )
    deadline = time.monotonic() + 600
    while len(list(chunks.rglob("*.wav"))) < 3:
        assert killed.poll() is None, "the run ended before it could be killed"
        assert time.monotonic() < deadline, "no sentence was spoken in ten minutes"
        time.sleep(0.5)
    killed.kill()
    killed.wait(timeout=60)
    cached = len(list(chunks.rglob("*.wav")))
    assert not out.exists() or not list(out.glob("*.m4b"))

    # 2. the same command again continues from the cache
    resumed = run(convert_args(out, work))
    assert resumed.returncode == 0, resumed.stderr
    spoke, total, reused = spoken_and_reused(resumed.stdout)
    assert reused >= cached >= 3
    assert spoke + reused == total
    books = sorted(p.name for p in out.iterdir())
    assert len([name for name in books if name.endswith(".m4b")]) == 1
    assert len([name for name in books if name.endswith(".readalong.json")]) == 1
    assert len([name for name in books if name.endswith(".mp3")]) == 4
    assert all((out / name).stat().st_size > 0 for name in books)
    assert "Traceback" not in resumed.stderr

    # 3. a rerun speaks nothing; without --overwrite it refuses first
    refused = run(convert_args(out, work, "-q"))
    assert refused.returncode == 7, refused.stderr
    again = run(convert_args(out, work, "-q", "--overwrite"))
    assert again.returncode == 0, again.stderr
    assert spoken_and_reused(again.stdout) == (0, total, total)


def short_book(folder: Path) -> Path:
    """The corpus EPUB with only the `KEPT` documents in its reading order."""
    path = folder / "short-book.epub"
    with zipfile.ZipFile(TIME_MACHINE) as source, zipfile.ZipFile(path, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "epub/content.opf":
                data = re.sub(
                    rb'\s*<itemref idref="([^"]+)"/>',
                    lambda m: m.group(0) if m.group(1).decode() in KEPT else b"",
                    data,
                )
            target.writestr(info, data)
    return path


@pytest.mark.slow
def test_convert_reads_an_epub_and_keeps_its_cover(tmp_path: Path) -> None:
    out, work = tmp_path / "out", tmp_path / "work"
    converted = run(convert_args(out, work, source=short_book(tmp_path)))
    assert converted.returncode == 0, converted.stderr
    assert "Traceback" not in converted.stderr
    spoke, total, reused = spoken_and_reused(converted.stdout)
    assert spoke == total > 0
    assert reused == 0
    (m4b,) = out.glob("*.m4b")
    with zipfile.ZipFile(TIME_MACHINE) as book:
        assert (work / "cover.jpg").read_bytes() == book.read("epub/images/cover.jpg")
    probe = subprocess.run(
        [str(find_ffmpeg()), "-hide_banner", "-i", str(m4b)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert "attached pic" in probe.stderr
