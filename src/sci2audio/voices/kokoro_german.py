"""Kokoro German: the Thorsten-Voice model behind the Kokoro adapter (#211, D-467).

The German model is Kokoro-82M fine-tuned by Thorsten-Voice on the Thorsten-Voice dataset
(Apache-2.0 weights, CC0 data). kokoro 0.9.4 has no German language code, so this module
builds the German pipeline itself from three parts:

- Pronunciation: upstream misaki's `EspeakG2P(language="de")` on the espeak-ng that
  espeakng-loader ships. The text reaches it unchanged: no number, date or abbreviation
  rewriting here (D-470, D-57); the German text steps in textprep do that as marked
  edits, and espeak-ng reads any digits left.
- `to_kokoro_phonemes`: espeak-ng writes a few symbols Kokoro's 178-symbol vocabulary
  lacks, and kokoro would drop them silently. The short ü (U+028F) becomes `y` (the
  substitution the model's training data used); bracket symbols carry no sound and go.
- `split_phonemes`: kokoro only speaks 510 phonemes per call and does not split espeak
  languages itself, so longer text is cut at sentence ends, then commas, then spaces.

`load_german_model` guards against a silent failure measured on 13 Nov 2026: the
checkpoint stores its weight-normalised layers under PyTorch's newer key names
(`parametrizations.weight.original0/1`), which kokoro 0.9.4 does not expect; its loader
then falls back to `strict=False` and skips those layers of the decoder and the prosody
predictor, and the voice speaks noise. The keys are renamed in memory to whatever the
installed kokoro expects, and every weight is checked to be loaded; the file on disk stays
byte-identical to its checksum.

torch, kokoro and misaki are imported only inside the functions that need them.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sci2audio.voices.errors import InvalidInputError, ModelLoadError
from sci2audio.voices.letters import german_spans, per_sound, speed_tensor

MAX_PHONEMES = 510  # kokoro's limit per call (its context of 512 minus the two pad tokens)

# espeak-ng German symbols outside Kokoro's vocabulary: mapped (sound kept) or dropped
# (no sound). Checked against the vocabulary by the tests on a German word list.
PHONEME_MAP: Mapping[str, str] = {"\u028f": "y"}  # short ü -> long ü
DROPPED = frozenset("[]{}")

# Weights the German checkpoint does not contain: the affine scale and shift of the
# AdaIN instance norms. kokoro leaves them at 1 and 0, which is what the model was
# trained with (StyleTTS2's AdaIN norms are not affine).
_ABSENT_OK = re.compile(r"(^|\.)norm\.(weight|bias)$")
_NEW_NAMES = (".parametrizations.weight.original0", ".parametrizations.weight.original1")
_OLD_NAMES = (".weight_g", ".weight_v")
_MODULE = "module."

# Where a part may be cut, best first: after a sentence end, after other punctuation,
# at a space.
_CUTS = (
    re.compile(r"(?<=[.!?…])\s+"),
    re.compile("(?<=[,;:\u2014\u2013])\\s+"),
    re.compile(r"\s+"),
)


def to_kokoro_phonemes(phonemes: str, vocab: Mapping[str, int]) -> str:
    """Map espeak-ng's German phonemes onto Kokoro's vocabulary (see the module doc).

    Raises:
        InvalidInputError: A symbol is neither in the vocabulary nor a known mapping, so
            kokoro would drop a sound without telling anyone.
    """
    out: list[str] = []
    unknown: set[str] = set()
    for symbol in phonemes:
        symbol = PHONEME_MAP.get(symbol, symbol)
        if symbol in DROPPED:
            continue
        if symbol not in vocab and not symbol.isspace():
            unknown.add(symbol)
        out.append(symbol)
    if unknown:
        listed = ", ".join(f"{s!r} (U+{ord(s):04X})" for s in sorted(unknown))
        raise InvalidInputError(f"the German voice cannot pronounce the phonemes {listed}")
    return "".join(out)


def split_phonemes(phonemes: str, limit: int = MAX_PHONEMES) -> list[str]:
    """Cut `phonemes` into parts of at most `limit` symbols, stripped, none empty.

    Cuts at the last sentence end that fits, else the last other punctuation, else the
    last space, else hard at the limit (a single word that long). Joining the parts with
    single spaces gives the input with its whitespace runs at the cuts collapsed.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    rest = phonemes.strip()
    parts: list[str] = []
    while len(rest) > limit:
        window = rest[: limit + 1]
        cut = None
        for pattern in _CUTS:
            ends = [m for m in pattern.finditer(window) if 0 < m.start() <= limit]
            if ends:
                cut = ends[-1]
                break
        if cut is None:
            parts.append(rest[:limit])
            rest = rest[limit:].lstrip()
        else:
            parts.append(rest[: cut.start()].rstrip())
            rest = rest[cut.end() :].lstrip()  # a whitespace run may go past the window
    if rest:
        parts.append(rest)
    return [part for part in parts if part]


def convert_checkpoint(
    checkpoint: Mapping[str, Mapping[str, Any]], expected: Mapping[str, set[str]]
) -> dict[str, dict[str, Any]]:
    """Rename weight-norm keys of `checkpoint` to the names the model expects.

    `expected` maps each part (bert, decoder, ...) to the parameter names the installed
    kokoro's model has, without kokoro's "module." prefix. The renamed keys keep the
    prefix, so kokoro's loader still finds them.

    Raises:
        ModelLoadError: A part of the model is missing from the checkpoint, the checkpoint
            has a part the model lacks, or a weight the model needs is not in it.
    """
    if set(checkpoint) != set(expected):
        raise ModelLoadError(
            "the German model file does not match kokoro's model: it has the parts "
            f"{sorted(checkpoint)}, kokoro expects {sorted(expected)}"
        )
    converted: dict[str, dict[str, Any]] = {}
    for part, weights in checkpoint.items():
        wanted = expected[part]
        renamed: dict[str, Any] = {}
        for key, value in weights.items():
            bare = key.removeprefix(_MODULE)
            if bare not in wanted:
                bare = _rename(bare, wanted)
            renamed[_MODULE + bare] = value
        names = {key.removeprefix(_MODULE) for key in renamed}
        missing = sorted(n for n in wanted - names if not _ABSENT_OK.search(n))
        extra = sorted(names - wanted)
        if missing or extra:
            raise ModelLoadError(
                f"the German model file does not fit kokoro's {part}: "
                f"{len(missing)} weights missing (e.g. {missing[:3]}), "
                f"{len(extra)} unknown (e.g. {extra[:3]})"
            )
        converted[part] = renamed
    return converted


def _rename(name: str, wanted: set[str]) -> str:
    for new, old in zip(_NEW_NAMES, _OLD_NAMES, strict=True):
        for source, target in ((new, old), (old, new)):
            if name.endswith(source):
                candidate = name[: -len(source)] + target
                if candidate in wanted:
                    return candidate
    return name


def check_loaded(model: Any, checkpoint: Mapping[str, Mapping[str, Any]]) -> None:
    """Check that every weight of `checkpoint` is in `model`, value for value.

    kokoro's loader may skip weights silently (`strict=False`); this catches it.

    Raises:
        ModelLoadError: A weight did not reach the model.
    """
    import torch

    for part, weights in checkpoint.items():
        state = getattr(model, part).state_dict()
        for key, value in weights.items():
            bare = key.removeprefix(_MODULE)
            loaded = state.get(bare)
            if loaded is None or not torch.equal(loaded.detach().cpu(), value.detach().cpu()):
                raise ModelLoadError(
                    f"the German model's weight {part}.{bare} was not loaded; "
                    "the installed kokoro does not fit this model file"
                )


def _expected_names(model: Any, parts: Iterator[str]) -> dict[str, set[str]]:
    return {part: set(getattr(model, part).state_dict()) for part in parts}


def load_german_model(folder: Path, weights: str, device: str, repo_id: str) -> Any:
    """Load the German Kokoro model from local files only, checked (see the module doc).

    Raises:
        ModelLoadError: The file does not fit the installed kokoro, or a weight was
            skipped while loading.
    """
    import torch
    from kokoro import KModel

    checkpoint = torch.load(folder / weights, map_location="cpu", weights_only=True)
    # A first model, built from the config alone, tells which names kokoro expects. It is
    # given an empty checkpoint so it loads nothing and never downloads.
    empty = io.BytesIO()
    torch.save({}, empty)
    empty.seek(0)
    shape = KModel(repo_id=repo_id, config=str(folder / "config.json"), model=empty)  # type: ignore[arg-type]
    converted = convert_checkpoint(checkpoint, _expected_names(shape, iter(checkpoint)))
    del shape
    buffer = io.BytesIO()
    torch.save(converted, buffer)
    buffer.seek(0)
    model = KModel(repo_id=repo_id, config=str(folder / "config.json"), model=buffer)  # type: ignore[arg-type]
    check_loaded(model, converted)
    return model.to(device).eval()


@dataclass
class GermanSegment:
    """One spoken part, shaped like kokoro's pipeline results (no word timings)."""

    graphemes: str
    phonemes: str
    audio: Any
    tokens: tuple[()] = ()


@dataclass
class GermanPipeline:
    """German text to audio, called like kokoro's `KPipeline` by the Kokoro adapter.

    `g2p` turns text into espeak-ng phonemes (`(phonemes, _)`); `model` is a kokoro
    `KModel`. Voice packs are loaded from local files once and kept.
    """

    model: Any
    g2p: Any
    _packs: dict[str, Any] = field(default_factory=dict)

    def phonemes(self, text: str) -> list[str]:
        """The Kokoro phonemes of `text`, cut into parts kokoro can speak."""
        return split_phonemes(self.sounds(text))

    def sounds(self, text: str) -> str:
        """The Kokoro phonemes of `text`, uncut."""
        raw, _ = self.g2p(text)
        return to_kokoro_phonemes(raw or "", self.model.vocab)

    def _pack(self, voice: str) -> Any:
        if voice not in self._packs:
            import torch

            self._packs[voice] = torch.load(voice, map_location="cpu", weights_only=True)
        return self._packs[voice]

    def __call__(
        self,
        text: str,
        *,
        voice: str,
        speed: float,
        split_pattern: str | None = None,
        letter_speed: float = 1.0,
    ) -> Iterator[GermanSegment]:
        """Speak `text`; spelled letters at `speed * letter_speed` (#295)."""
        import torch

        pack = self._pack(voice)
        for part in self.phonemes(text):
            rate: Any = speed
            if letter_speed != 1.0:
                spans = german_spans(text, part, self.sounds)
                if spans:
                    values = per_sound(part, self.model.vocab, spans, speed, letter_speed)
                    rate = speed_tensor(values, self.model.device)
            with torch.no_grad():
                output = self.model(part, pack[len(part) - 1], rate, return_output=True)
            yield GermanSegment(graphemes=text, phonemes=part, audio=output.audio)


def german_pipeline(folder: Path, weights: str, device: str, repo_id: str) -> GermanPipeline:
    """The German pipeline from the files of the German voice pack in `folder`."""
    from misaki.espeak import EspeakG2P

    return GermanPipeline(
        model=load_german_model(folder, weights, device, repo_id),
        g2p=EspeakG2P(language="de"),
    )
