"""Fakes for the voice tests: a kokoro-like pipeline without torch, model or network."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sci2audio.voices import ENGLISH_VOICES, KokoroEngine, create_kokoro_engine
from sci2audio.voices import kokoro_engine as kokoro_module


@dataclass
class FakeToken:
    text: str
    whitespace: str
    start_ts: float | None
    end_ts: float | None


@dataclass
class FakeResult:
    graphemes: str
    audio: Any
    tokens: list[FakeToken] = field(default_factory=list)


@dataclass
class FakePipeline:
    """Speaks 100 samples per character at speed 1, a quiet sine, one result per line."""

    lang_code: str
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(
        self, text: str, *, voice: str, speed: float, split_pattern: str | None
    ) -> Iterator[FakeResult]:
        self.calls.append({"text": text, "voice": voice, "speed": speed, "split": split_pattern})
        for line in text.split("\n"):
            n = int(len(line) * 100 / speed)
            audio = 0.5 * np.sin(np.arange(n, dtype=np.float32) / 7.0) if n else None
            words = line.split()
            tokens = [FakeToken(w, " ", i * 0.1, i * 0.1 + 0.08) for i, w in enumerate(words)]
            yield FakeResult(graphemes=line, audio=audio, tokens=tokens)


class FakeFactory:
    def __init__(self) -> None:
        self.pipelines: dict[str, FakePipeline] = {}

    def __call__(self, lang_code: str) -> FakePipeline:
        self.pipelines[lang_code] = FakePipeline(lang_code)
        return self.pipelines[lang_code]


def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo what `prepare_environment` changes in the process after the test."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in ("PYTORCH_ENABLE_MPS_FALLBACK", "HF_HUB_OFFLINE"):
        monkeypatch.delenv(name, raising=False)


def fake_models_dir(tmp_path: Path) -> Path:
    """A models folder with an (empty) voice pack for every English voice."""
    voices = kokoro_module.kokoro_dir(tmp_path) / "voices"
    voices.mkdir(parents=True)
    for voice in ENGLISH_VOICES:
        (voices / f"{voice.id}.pt").write_bytes(b"")
    return tmp_path


def make_fake_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, factory: FakeFactory | None = None
) -> KokoroEngine:
    """The real Kokoro adapter on a fake pipeline (size checks of the big files skipped)."""
    isolate_environment(monkeypatch)
    monkeypatch.setattr(kokoro_module, "missing_files", lambda models_dir: [])
    return create_kokoro_engine(
        fake_models_dir(tmp_path), pipeline_factory=factory or FakeFactory()
    )
