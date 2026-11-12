"""The one start-up function of the voices (F-15, VA-04).

`prepare_environment` must run before torch, transformers, huggingface_hub or kokoro are
imported, because they read these settings at import time. `create_kokoro_engine` calls
it first, so a caller cannot forget it; the app calls it again at job start (harmless).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sci2audio.voices.download import spacy_dir

ENVIRONMENT = {
    # Apple GPU: run the few operations MPS lacks on the CPU instead of failing
    # ("MPS requested but fallback not enabled", F-12, F-15).
    "PYTORCH_ENABLE_MPS_FALLBACK": "1",
    # huggingface_hub never goes online. sci2audio downloads the voice files itself
    # (`download.py`), so this stays set even during that download (refines D-104).
    "HF_HUB_OFFLINE": "1",
}


def prepare_environment(models_dir: Path | None = None) -> None:
    """Set the process settings the voices need and make the spaCy model findable.

    With `models_dir`, the folder holding the unpacked spaCy English model goes to the
    front of `sys.path` (once), so misaki finds it and never tries to download it.
    """
    os.environ.update(ENVIRONMENT)
    if models_dir is not None:
        folder = str(spacy_dir(models_dir))
        if folder not in sys.path:
            sys.path.insert(0, folder)
