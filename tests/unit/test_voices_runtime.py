"""The one start-up function of the voices (F-15, VA-04)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from voice_fakes import isolate_environment

from sci2audio.voices import prepare_environment


def test_sets_mps_fallback_and_hugging_face_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_environment(monkeypatch)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    prepare_environment()
    assert os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] == "1"
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_adds_the_spacy_folder_to_the_end_of_the_path_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_environment(monkeypatch)
    before = list(sys.path)
    prepare_environment(tmp_path)
    prepare_environment(tmp_path)
    folder = str(tmp_path / "spacy" / "en_core_web_sm-3.8.0")
    # At the end, so a user-writable folder can never shadow the standard library.
    assert sys.path == [*before, folder]
