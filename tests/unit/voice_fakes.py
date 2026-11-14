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
from sci2audio.voices.download import german_dir


@dataclass
class FakeToken:
    text: str
    whitespace: str
    start_ts: float | None
    end_ts: float | None
    phonemes: str | None = None


@dataclass
class FakeResult:
    graphemes: str
    audio: Any
    tokens: list[FakeToken] = field(default_factory=list)


SAID_AS_WORDS = {"NASA"}  # all capitals, but the fake voice says it as a word


def fake_spelling(letters: str) -> str:
    """How the fake English voice spells letters: each letter, then "i" ("NLP" "ninlipi")."""
    return "".join(letter.lower() + "i" for letter in letters)


def fake_sounds(word: str) -> str:
    """The fake English voice's sounds of a word: all capitals are spelled (a plural "s"
    adds "z"), unless said as a word; anything else is its letters in lower case."""
    stem = word[:-1] if word.endswith("s") and word[:-1].isupper() else word
    if len(stem) >= 2 and stem.isalpha() and stem.isupper() and stem not in SAID_AS_WORDS:
        return fake_spelling(stem) + ("z" if stem != word else "")
    return word.lower()


@dataclass
class FakeOutput:
    audio: Any
    pred_dur: Any


class FakePack:
    def to(self, device: str) -> FakePack:
        return self

    def __getitem__(self, index: int) -> FakePack:
        return self


@dataclass
class FakeModel:
    """Speaks 100 samples per known sound divided by that sound's speed (a number or one
    value per sound with the two padding tokens, as kokoro's `KModel` takes it)."""

    vocab: dict[str, int] = field(
        default_factory=lambda: {c: i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz .,", 1)}
    )
    device: str = "cpu"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, sounds: str, pack: Any, speed: Any, *, return_output: bool) -> FakeOutput:
        known = [s for s in sounds if self.vocab.get(s) is not None]
        rates = np.asarray(speed, dtype=float).reshape(-1)
        if rates.size == 1:
            rates = np.full(len(known) + 2, float(rates[0]))
        assert rates.size == len(known) + 2, (rates.size, len(known))
        self.calls.append({"sounds": sounds, "speed": speed, "rates": rates.tolist()})
        frames = np.maximum(np.round(4 / rates), 1).astype(int)
        n = int(frames[1:-1].sum()) * 25
        audio = 0.5 * np.sin(np.arange(n, dtype=np.float32) / 7.0)
        return FakeOutput(audio=audio, pred_dur=frames)


@dataclass
class FakeLexicon:
    def get_NNP(self, word: str) -> tuple[str | None, int | None]:
        return fake_spelling(word), 3


@dataclass
class FakeG2P:
    """misaki's English G2P on the fake voice's sounds: one token per word or full stop."""

    lexicon: FakeLexicon = field(default_factory=FakeLexicon)

    def __call__(self, text: str) -> tuple[str, list[FakeToken]]:
        tokens = []
        for word in text.split():
            stop = word.endswith(".")
            word = word.rstrip(".")
            if word:
                tokens.append(FakeToken(word, "" if stop else " ", None, None, fake_sounds(word)))
            if stop:
                tokens.append(FakeToken(".", " ", None, None, "."))
        if tokens:
            tokens[-1].whitespace = ""
        return "", tokens


@dataclass
class FakePipeline:
    """Speaks 100 samples per character at speed 1, a quiet sine, one result per line.

    For #295 it also has what the Kokoro adapter uses of an English `KPipeline` to slow
    spelled letters (`g2p`, `en_tokenize`, `model`, `load_voice`, `join_timestamps`), and
    takes `letter_speed` as the German pipeline does.
    """

    lang_code: str
    calls: list[dict[str, Any]] = field(default_factory=list)
    model: FakeModel = field(default_factory=FakeModel)
    g2p: FakeG2P = field(default_factory=FakeG2P)

    def __call__(
        self,
        text: str,
        *,
        voice: str,
        speed: float,
        split_pattern: str | None,
        **more: Any,
    ) -> Iterator[FakeResult]:
        self.calls.append(
            {"text": text, "voice": voice, "speed": speed, "split": split_pattern, **more}
        )
        for line in text.split("\n"):
            n = int(len(line) * 100 / speed)
            audio = 0.5 * np.sin(np.arange(n, dtype=np.float32) / 7.0) if n else None
            words = line.split()
            tokens = [FakeToken(w, " ", i * 0.1, i * 0.1 + 0.08) for i, w in enumerate(words)]
            yield FakeResult(graphemes=line, audio=audio, tokens=tokens)

    def load_voice(self, voice: str) -> FakePack:
        self.calls.append({"load_voice": voice})
        return FakePack()

    def en_tokenize(self, tokens: list[FakeToken]) -> Iterator[tuple[str, str, list[FakeToken]]]:
        text = "".join(t.text + t.whitespace for t in tokens).strip()
        sounds = "".join((t.phonemes or "") + (" " if t.whitespace else "") for t in tokens)
        yield text, sounds.strip(), tokens

    @staticmethod
    def join_timestamps(tokens: list[FakeToken], pred_dur: Any) -> None:
        for index, token in enumerate(tokens):
            token.start_ts, token.end_ts = index * 0.1, index * 0.1 + 0.08


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
    """A models folder with an (empty) voice pack for every English voice and the German
    voice Thorsten."""
    voices = kokoro_module.kokoro_dir(tmp_path) / "voices"
    voices.mkdir(parents=True)
    for voice in ENGLISH_VOICES:
        (voices / f"{voice.id}.pt").write_bytes(b"")
    german = german_dir(tmp_path) / "voices"
    german.mkdir(parents=True)
    (german / "thorsten.pt").write_bytes(b"")
    return tmp_path


def make_fake_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, factory: FakeFactory | None = None
) -> KokoroEngine:
    """The real Kokoro adapter on a fake pipeline (size checks of the big files skipped)."""
    isolate_environment(monkeypatch)
    monkeypatch.setattr(kokoro_module, "missing_files", lambda models_dir, languages=None: [])
    return create_kokoro_engine(
        fake_models_dir(tmp_path), pipeline_factory=factory or FakeFactory()
    )
