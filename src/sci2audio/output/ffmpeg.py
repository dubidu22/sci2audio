"""The one place that finds and runs ffmpeg (Q5).

ffmpeg comes from the `imageio-ffmpeg` wheel (BSD-2-Clause wrapper around a GPL build of
ffmpeg, see THIRD_PARTY_LICENSES.md); an ffmpeg on PATH is the fallback. The wheel ships no
ffprobe, so nothing here uses it. Every input is opened with `-protocol_whitelist file,pipe`,
so ffmpeg reads only local files and our own pipe and never opens a network address
(CLAUDE.md: no network calls).
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

LOCAL_ONLY = ("-protocol_whitelist", "file,pipe")
_QUIET = ("-hide_banner", "-nostats", "-loglevel", "error")
_STDERR_LINES = 12


class FfmpegNotFoundError(RuntimeError):
    """Neither the bundled ffmpeg nor one on PATH could be found."""

    def __init__(self) -> None:
        super().__init__(
            "ffmpeg was not found. sci2audio normally uses the copy that comes with the "
            "imageio-ffmpeg package: reinstall sci2audio to get it back, or install ffmpeg "
            "and put it on your PATH, or set IMAGEIO_FFMPEG_EXE to the ffmpeg program."
        )


class FfmpegError(RuntimeError):
    """ffmpeg stopped with an error; the message holds the last lines it printed."""

    def __init__(self, returncode: int, stderr: str) -> None:
        self.returncode = returncode
        self.stderr = stderr
        tail = "\n".join(stderr.strip().splitlines()[-_STDERR_LINES:])
        super().__init__(f"ffmpeg failed (exit code {returncode}): {tail or 'no message'}")


def find_ffmpeg() -> Path:
    """The ffmpeg program: imageio-ffmpeg's bundled copy, else the one on PATH."""
    try:
        import imageio_ffmpeg  # here, so a broken install still falls back to PATH

        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError, OSError):
        pass
    found = shutil.which("ffmpeg")
    if found is None:
        raise FfmpegNotFoundError
    return Path(found)


@dataclass(frozen=True)
class Ffmpeg:
    """Runs one ffmpeg program. Tests replace `run` to simulate failures."""

    exe: Path

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        """Run ffmpeg with `args`, writing each piece of `feed` to its standard input.

        Returns what ffmpeg printed on standard output. Raises FfmpegError on a non-zero
        exit; an exception raised while feeding stops ffmpeg and is raised again.
        """
        command = [str(self.exe), *_QUIET, *args]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        # stdout and stderr go to files, so a chatty ffmpeg never blocks on a full pipe
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen(  # noqa: S603 (our own argument list, no shell)
                command,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                creationflags=flags,
            )
            stdin = process.stdin
            assert stdin is not None  # noqa: S101 (set by stdin=PIPE)
            stopped_early = False
            try:
                for piece in feed:  # an error while reading the feed stops ffmpeg (below)
                    try:
                        stdin.write(piece)
                    except OSError:  # a broken pipe (EINVAL on Windows): ffmpeg stopped
                        stopped_early = True
                        break
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                with contextlib.suppress(OSError):
                    stdin.close()
            code = process.wait()
            out.seek(0)
            err.seek(0)
            printed = out.read().decode("utf-8", "replace")
            message = err.read().decode("utf-8", "replace")
        if code == 0 and stopped_early:
            code, message = -1, f"ffmpeg stopped reading its input early\n{message}"
        if code != 0:
            raise FfmpegError(code, message)
        return printed
