"""The German voice's own parts (#211, D-467): espeak-ng phonemes onto Kokoro's vocabulary,
the 510-phoneme cuts, and the checked loading of the German weights.

The weight tests build a tiny Kokoro model (same layers, small sizes) from a config dict,
so they run in the fast suite without the 327 MB model; nothing touches the network.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.testing import no_network
from sci2audio.voices import InvalidInputError, ModelLoadError
from sci2audio.voices.kokoro_german import (
    DROPPED,
    MAX_PHONEMES,
    GermanPipeline,
    check_loaded,
    convert_checkpoint,
    load_german_model,
    split_phonemes,
    to_kokoro_phonemes,
)

# Kokoro-82M's symbol table, copied from its config.json (Apache-2.0, tests/fixtures/README.md)
VOCAB: dict[str, int] = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "kokoro-vocab.json").read_text(encoding="utf-8")
)
SHORT_UE = "ʏ"  # IPA small capital Y: espeak-ng's short ü, not in Kokoro's symbols

# German words with every umlaut, ß, the ich/ach sounds, diphthongs, affricates, nasal
# loanwords and English words in German text. Own words, no third-party text.
GERMAN_WORDS = (
    "Brücke Glück Hütte Müller Küche Mütze Füße Öl Köln Bär Mädchen Häuser Eule Feuer "
    "Bäume Quark Xylophon Yacht Psychologie Rhythmus Zwetschge Pfropfen Strumpf Herbst "
    "ich ach Nacht Licht Chemie Chaos Charakter Theorie Spektroskopie Quantenmechanik "
    "Algorithmus Wahrscheinlichkeit Restaurant Journal Chance Genie Jalousie Pizza "
    "Computer Teenager Ingenieur Orange Balkon Parfum Bonbon Champagner Croissant Saison "
    "Cousin Engagement Ensemble Garage Etage Software Feedback Machine Learning "
    "Überraschenderweise Wärmeleitfähigkeit Begutachtungsverfahren Korngrenzen. "
    "Fragen? Ja! Doppelpunkt: Semikolon; Gedanke – Strich (Klammer) „Zitat“ «Anführung» "
    "3,5 Prozent, 1998, 42."
)


# --- phonemes onto the vocabulary ----------------------------------------------------------


def test_short_ue_becomes_long_ue_and_brackets_go() -> None:
    assert to_kokoro_phonemes(f"bɾˈ{SHORT_UE}kə", VOCAB) == "bɾˈykə"
    assert to_kokoro_phonemes("a [b] {c}", VOCAB) == "a b c"
    assert DROPPED.isdisjoint(VOCAB)


def test_an_unknown_symbol_is_refused_not_dropped() -> None:
    with pytest.raises(InvalidInputError, match=r"'ʀ' \(U\+0280\)"):
        to_kokoro_phonemes("ʀoːt", VOCAB)


def test_real_espeak_german_gives_only_kokoro_symbols() -> None:
    """espeakng-loader ships espeak-ng with the package, so CI runs the real pronunciation."""
    from misaki.espeak import EspeakG2P

    with no_network():
        raw, _ = EspeakG2P(language="de")(GERMAN_WORDS)
    assert SHORT_UE in raw  # the case the mapping exists for
    phonemes = to_kokoro_phonemes(raw, VOCAB)
    assert set(phonemes) - {" "} <= set(VOCAB)
    assert "bɾˈykə" in phonemes  # Brücke


# --- cutting at 510 phonemes ---------------------------------------------------------------


def test_short_text_is_one_part() -> None:
    assert split_phonemes("  ɪç ˈlaxə.  ") == ["ɪç ˈlaxə."]
    assert split_phonemes("   ") == []


def test_cuts_prefer_sentence_ends_then_commas_then_spaces() -> None:
    sentence = "a" * 6 + "."
    assert split_phonemes(f"{sentence} bb, cc dd", 12) == [sentence, "bb, cc dd"]
    assert split_phonemes("aa, bbb cc dd", 9) == ["aa,", "bbb cc dd"]  # comma beats space
    assert split_phonemes("aaa bbb ccc", 8) == ["aaa bbb", "ccc"]
    assert split_phonemes("abcdefghij", 4) == ["abcd", "efgh", "ij"]  # one long word


def test_a_long_german_utterance_is_cut_at_its_sentences() -> None:
    sentence = "diː ʔɛɾɡˈeːpnɪsə vˈʊɐdən ˈyːbɐ dɾˈaɪ jˈaːɾə ɡəmˈɛsən. "
    parts = split_phonemes(sentence * 12)
    assert len(parts) == 2
    assert all(len(p) <= MAX_PHONEMES and p.endswith(".") for p in parts)


@given(st.text(alphabet=st.sampled_from("aɪç ˈ.,;:—–!?\n\t"), max_size=2000), st.integers(1, 600))
def test_parts_never_pass_the_limit_and_lose_no_symbol(text: str, limit: int) -> None:
    parts = split_phonemes(text, limit)
    assert all(0 < len(part) <= limit for part in parts)
    assert all(part == part.strip() for part in parts)
    assert "".join("".join(parts).split()) == "".join(text.split())


def test_the_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        split_phonemes("a", 0)


# --- the German weights: renamed on load and checked (the silent skip of 13 Nov 2026) -------

TINY_CONFIG: dict[str, Any] = {
    "istftnet": {
        "upsample_kernel_sizes": [4, 4],
        "upsample_rates": [2, 2],
        "gen_istft_hop_size": 5,
        "gen_istft_n_fft": 20,
        "resblock_dilation_sizes": [[1, 3, 5], [1, 3, 5]],
        "resblock_kernel_sizes": [3, 5],
        "upsample_initial_channel": 32,
    },
    "dim_in": 16,
    "dropout": 0.2,
    "hidden_dim": 32,
    "max_conv_dim": 32,
    "max_dur": 5,
    "multispeaker": True,
    "n_layer": 1,
    "n_mels": 16,
    "n_token": 178,
    "style_dim": 8,
    "text_encoder_kernel_size": 3,
    "plbert": {
        "hidden_size": 32,
        "num_attention_heads": 2,
        "intermediate_size": 32,
        "max_position_embeddings": 512,
        "num_hidden_layers": 1,
        "dropout": 0.1,
    },
    "vocab": VOCAB,
}
NEW = ".parametrizations.weight.original"


def tiny_model(checkpoint: Any = None) -> Any:
    """A tiny KModel; with no checkpoint it keeps its random start (nothing is loaded)."""
    import torch
    from kokoro import KModel

    if checkpoint is None:
        checkpoint = {}
    buffer = io.BytesIO()
    torch.save(checkpoint, buffer)
    buffer.seek(0)
    return KModel(repo_id="hexgrad/Kokoro-82M", config=TINY_CONFIG, model=buffer)  # type: ignore[arg-type]


def thorsten_style(model: Any) -> dict[str, dict[str, Any]]:
    """The model's weights stored as the Thorsten checkpoint stores them: "module."
    prefix, the newer weight-norm names, and no AdaIN norm scale and shift."""
    parts: dict[str, dict[str, Any]] = {}
    for part in ("bert", "bert_encoder", "predictor", "text_encoder", "decoder"):
        weights = {}
        for key, value in getattr(model, part).state_dict().items():
            if key.endswith(("norm.weight", "norm.bias")) and ".norm." in f".{key}":
                continue
            key = key.replace(".weight_g", f"{NEW}0").replace(".weight_v", f"{NEW}1")
            weights["module." + key] = value.clone()
        parts[part] = weights
    return parts


@pytest.fixture(scope="module")
def german_files(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    import torch

    source = tiny_model()
    checkpoint = thorsten_style(source)
    assert any(NEW in key for key in checkpoint["decoder"])  # the case under test
    folder = tmp_path_factory.mktemp("german")
    (folder / "config.json").write_text(json.dumps(TINY_CONFIG), encoding="utf-8")
    torch.save(checkpoint, folder / "model.pth")
    return folder, source


def same_weights(a: Any, b: Any, part: str) -> bool:
    import torch

    mine, theirs = getattr(a, part).state_dict(), getattr(b, part).state_dict()
    return all(torch.equal(mine[k], theirs[k]) for k in mine)


def test_kokoro_alone_skips_the_decoder_weights_silently(german_files: tuple[Path, Any]) -> None:
    """Characterises the bug the German loader guards against: kokoro 0.9.4 loads this
    checkpoint without an error, but its weight-normalised layers (decoder and prosody
    predictor) keep random weights (the voice speaks noise), and the completeness check
    catches it."""
    import torch

    folder, source = german_files
    checkpoint = torch.load(folder / "model.pth", weights_only=True)
    plain = tiny_model(checkpoint)
    assert same_weights(plain, source, "bert")
    assert not same_weights(plain, source, "decoder")
    assert not same_weights(plain, source, "predictor")
    with pytest.raises(ModelLoadError, match=r"weight \w+\..* was not loaded"):
        check_loaded(plain, checkpoint)
    with pytest.raises(ModelLoadError, match=r"weight decoder\..*original[01] was not loaded"):
        check_loaded(plain, {"decoder": checkpoint["decoder"]})


def test_the_german_loader_loads_every_weight(german_files: tuple[Path, Any]) -> None:
    folder, source = german_files
    with no_network():
        model = load_german_model(folder, "model.pth", "cpu", "hexgrad/Kokoro-82M")
    for part in ("bert", "bert_encoder", "predictor", "text_encoder", "decoder"):
        assert same_weights(model, source, part), part
    assert not model.training


def test_a_checkpoint_missing_weights_is_refused(german_files: tuple[Path, Any]) -> None:
    _, source = german_files
    checkpoint = thorsten_style(source)
    dropped = next(k for k in checkpoint["decoder"] if k.endswith(f"{NEW}1"))
    del checkpoint["decoder"][dropped]
    expected = {p: set(getattr(source, p).state_dict()) for p in checkpoint}
    with pytest.raises(ModelLoadError, match="fit kokoro's decoder: 1 weights missing"):
        convert_checkpoint(checkpoint, expected)


def test_a_checkpoint_with_other_parts_is_refused(german_files: tuple[Path, Any]) -> None:
    _, source = german_files
    checkpoint = thorsten_style(source)
    expected = {p: set(getattr(source, p).state_dict()) for p in checkpoint}
    del checkpoint["bert"]
    with pytest.raises(ModelLoadError, match="has the parts"):
        convert_checkpoint(checkpoint, expected)
    checkpoint = thorsten_style(source)
    checkpoint["decoder"]["module.extra.weight"] = checkpoint["bert_encoder"]["module.bias"]
    with pytest.raises(ModelLoadError, match="1 unknown"):
        convert_checkpoint(checkpoint, expected)


def test_old_names_are_kept_when_kokoro_expects_them(german_files: tuple[Path, Any]) -> None:
    _, source = german_files
    legacy = {
        part: {"module." + k: v for k, v in getattr(source, part).state_dict().items()}
        for part in ("bert", "bert_encoder", "predictor", "text_encoder", "decoder")
    }
    expected = {p: set(getattr(source, p).state_dict()) for p in legacy}
    assert convert_checkpoint(legacy, expected) == legacy


# --- the pipeline, as the Kokoro adapter calls it ------------------------------------------


class FakeModel:
    vocab = VOCAB

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, float]] = []

    def __call__(self, phonemes: str, style: Any, speed: float, return_output: bool) -> Any:
        import torch

        self.calls.append((phonemes, int(style.item()), speed))
        return type("Output", (), {"audio": torch.zeros(len(phonemes))})()


def test_the_pipeline_speaks_each_part_with_the_style_for_its_length(tmp_path: Path) -> None:
    import torch

    pack = tmp_path / "thorsten.pt"
    torch.save(torch.arange(MAX_PHONEMES, dtype=torch.float32).reshape(-1, 1, 1), pack)
    model = FakeModel()
    sentence = "ˈaːbɐ. "
    pipeline = GermanPipeline(model=model, g2p=lambda text: ((sentence * 100).strip(), None))
    with no_network():
        segments = list(pipeline("Aber.", voice=str(pack), speed=1.25, split_pattern=None))
    assert [len(p) for p, _, _ in model.calls] == [510, 188]
    assert all(style == len(p) - 1 for p, style, _ in model.calls)
    assert {speed for _, _, speed in model.calls} == {1.25}
    assert [s.graphemes for s in segments] == ["Aber.", "Aber."]
    assert all(s.tokens == () for s in segments)
    list(pipeline("Aber.", voice=str(pack), speed=1.0))
    assert list(pipeline._packs) == [str(pack)]  # the voice pack is read once
