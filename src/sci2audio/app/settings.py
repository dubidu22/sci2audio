"""The settings of one job, passed in for each job (no global state; CLAUDE.md)."""

from __future__ import annotations

import math
import re
from collections.abc import Set
from dataclasses import dataclass
from pathlib import Path

from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category

MIN_SPEED = 0.5
MAX_SPEED = 2.0
# The paces of letters the voice spells out ("NLP"), as factors of the speed (#295, D-554):
# measured English letters a second at speed 1.0: 5.8 to 7.0, 4.2 to 4.8, 2.9 to 3.5.
LETTER_PACES: dict[str, float] = {"normal": 1.0, "slower": 0.7, "slowest": 0.5}
_LANGUAGE = re.compile(r"\A[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")


@dataclass(frozen=True)
class JobSettings:
    """What the person chose for one job.

    `chapters` are indices into the job's chapter list (`find_chapters`), in the order they
    are read (#119; a set given here, which has no order, is read in printed order); None
    means the default choice: every chapter but the reference list (Q6). `voice` and `speed` are for
    the audio job (#71), `letter_pace` too: how fast the voice says letters it spells out,
    one of LETTER_PACES (#295). `subtitles` adds SRT and WebVTT files to the audiobook
    (#214, D-606). `plugins` false runs the built-in text steps only, without the
    installed text-step plugins (#667); like the chapters it belongs to one job and is not
    kept in the settings file. Without an `output_folder`, files go next to the source file.
    """

    # BCP 47 tag ("en", "en-GB"); "" = the file's own, else guessed from the text ("en" or
    # "de", D-495)
    language: str = ""
    # UC-02 switches; "Footnote texts" starts off (D-142), so notes are read by default
    switched_off: frozenset[Category] = DEFAULT_SWITCHED_OFF
    chapters: tuple[int, ...] | None = None
    voice: str = ""  # "" = the default voice (#71)
    speed: float = 1.0  # MIN_SPEED to MAX_SPEED (#71)
    letter_pace: str = "normal"  # a key of LETTER_PACES (#295)
    subtitles: bool = False  # .srt and .vtt next to the audio files (#214)
    plugins: bool = True  # the installed text-step plugins run too (#667)
    output_folder: Path | None = None

    def __post_init__(self) -> None:
        if self.language and not _LANGUAGE.match(self.language):
            raise ValueError(f"language must be a tag like 'en' or 'en-GB', got {self.language!r}")
        switched_off = frozenset(self.switched_off)
        if not all(isinstance(category, Category) for category in switched_off):
            raise ValueError(f"switched_off must hold categories, got {sorted(switched_off)}")
        object.__setattr__(self, "switched_off", switched_off)
        if self.chapters is not None:
            given = self.chapters
            if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in given):
                raise ValueError(f"chapters must be indices >= 0, got {sorted(given, key=str)}")
            # a set has no order: printed order; else the person's order, each chapter once
            ordered = sorted(given) if isinstance(given, Set) else dict.fromkeys(given)
            object.__setattr__(self, "chapters", tuple(ordered))
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
        if not isinstance(self.letter_pace, str) or self.letter_pace not in LETTER_PACES:
            raise ValueError(
                f"letter_pace must be one of {', '.join(LETTER_PACES)}, got {self.letter_pace!r}"
            )
        if not isinstance(self.subtitles, bool):
            raise ValueError(f"subtitles must be true or false, got {self.subtitles!r}")
        if not isinstance(self.plugins, bool):
            raise ValueError(f"plugins must be true or false, got {self.plugins!r}")
        if self.output_folder is not None:
            object.__setattr__(self, "output_folder", Path(self.output_folder))

    @property
    def letter_speed(self) -> float:
        """The voice's `letter_speed` for the chosen `letter_pace` (#295)."""
        return LETTER_PACES[self.letter_pace]
