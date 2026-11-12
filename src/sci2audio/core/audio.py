"""Audio the voice made, pointing back at the original text it reads."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

from sci2audio.core.document import Span


@dataclass(frozen=True)
class AudioChunk:
    """One audio file of the voice and the original span it reads.

    `file` is relative to the job's working folder, with forward slashes, so a job folder
    can move and snapshots hold no machine-specific paths. Output uses the spans for
    chapters and the durations for read-along timing.
    """

    span: Span
    file: str
    duration: float  # seconds

    def __post_init__(self) -> None:
        object.__setattr__(self, "duration", float(self.duration))
        posix, windows = PurePosixPath(self.file), PureWindowsPath(self.file)
        if (
            not self.file
            or "\\" in self.file
            or posix.is_absolute()
            or windows.drive
            or ".." in posix.parts
        ):
            raise ValueError(
                f"audio file must be a relative path inside the job folder: {self.file!r}"
            )
        if not math.isfinite(self.duration) or self.duration < 0:
            raise ValueError(f"audio duration must be a finite number >= 0, got {self.duration}")
