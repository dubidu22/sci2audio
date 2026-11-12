"""Fetch the models the slow voice tests need (nightly workflow step; network allowed).

    uv run python tests/integration/prepare_models.py VOICE_DIR WHISPER_DIR

The voice files come through sci2audio's own user-started download, so the nightly run
also proves that download works. The tests themselves then run with the network blocked.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sci2audio.voices import download_plan, download_voice_files, missing_files

WHISPER_MODEL = "Systran/faster-whisper-small"
WHISPER_REVISION = "536b0662742c02347bc0e980a01041f333bce120"


def main(voice_dir: Path, whisper_dir: Path) -> None:
    plan = download_plan()
    print(f"voice files: {len(missing_files(voice_dir))} of {len(plan.files)} to fetch")
    last = -1

    def progress(done: int, total: int, target: str) -> None:
        nonlocal last
        percent = done * 100 // max(total, 1)
        if percent // 10 != last:
            last = percent // 10
            print(f"  {percent:3d} %  {target}", flush=True)

    download_voice_files(voice_dir, progress=progress)

    from faster_whisper import download_model

    download_model(WHISPER_MODEL, output_dir=str(whisper_dir), revision=WHISPER_REVISION)
    print("models ready")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
