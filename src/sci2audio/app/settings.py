"""The settings of one job, passed in for each job (no global state; CLAUDE.md)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category

MIN_SPEED = 0.5
MAX_SPEED = 2.0
_LANGUAGE = re.compile(r"\A[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")


@dataclass(frozen=True)
class JobSettings:
    """What the person chose for one job.

    `chapters` are indices into the job's chapter list (`find_chapters`); None means the
    default choice: every chapter but the reference list (Q6). `voice` and `speed` are for
    the audio job (#71). Without an `output_folder`, files go next to the source file.
    """

    # BCP 47 tag ("en", "en-GB"); "" = the file's own, else guessed from the text ("en" or
    # "de", D-495)
    language: str = ""
    # UC-02 switches; "Footnote texts" starts off (D-142), so notes are read by default
    switched_off: frozenset[Category] = DEFAULT_SWITCHED_OFF
    chapters: frozenset[int] | None = None
    voice: str = ""  # "" = the default voice (#71)
    speed: float = 1.0  # MIN_SPEED to MAX_SPEED (#71)
    output_folder: Path | None = None

    def __post_init__(self) -> None:
        if self.language and not _LANGUAGE.match(self.language):
            raise ValueError(f"language must be a tag like 'en' or 'en-GB', got {self.language!r}")
        switched_off = frozenset(self.switched_off)
        if not all(isinstance(category, Category) for category in switched_off):
            raise ValueError(f"switched_off must hold categories, got {sorted(switched_off)}")
        object.__setattr__(self, "switched_off", switched_off)
        if self.chapters is not None:
            chapters = frozenset(self.chapters)
            if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in chapters):
                raise ValueError(f"chapters must be indices >= 0, got {sorted(chapters, key=str)}")
            object.__setattr__(self, "chapters", chapters)
        if not isinstance(self.voice, str):
            raise ValueError(f"voice must be a name, got {self.voice!r}")
        speed = self.speed
        if (
            isinstance(speed, bool)
            or not isinstance(speed, int | float)
            or not math.isfinite(speed)
            or not MIN_SPEED <= speed <= MAX_SPEED
        ):
            raise ValueError(f"speed must be between {MIN_SPEED} and {MAX_SPEED}, got {speed!r}")
        object.__setattr__(self, "speed", float(speed))
        if self.output_folder is not None:
            object.__setattr__(self, "output_folder", Path(self.output_folder))
