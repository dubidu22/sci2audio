"""The installers' entry point for `sci2audio-app`, the app (#215)."""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):  # always true in the installers; the check keeps it plain
    # the bundle's own audio-only FFmpeg (D-798), not imageio-ffmpeg's, which is left out
    program = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    os.environ["IMAGEIO_FFMPEG_EXE"] = str(Path(sys._MEIPASS) / "ffmpeg" / program)

from sci2audio.web.window import main

raise SystemExit(main())
