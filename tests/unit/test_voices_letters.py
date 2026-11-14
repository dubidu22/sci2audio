"""Spelled abbreviations at the listener's pace (#295, D-554): which sounds a voice slows,
and that the Kokoro adapter and kokoro's own model slow only those.

Phoneme strings are the real ones misaki and espeak-ng gave on 14 Nov 2026 (issue #295).
"""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from voice_fakes import FakeFactory, fake_spelling, make_fake_engine

from sci2audio.testing import no_network
from sci2audio.voices import (
    DEFAULT_VOICE,
    GERMAN_DEFAULT_VOICE,
    LETTER_SPEED_MAX,
    LETTER_SPEED_MIN,
    PCM_FLOAT32,
    InvalidInputError,
    ParameterValues,
    SynthesisRequest,
    VoiceSelection,
)
from sci2audio.voices.kokoro_german import GermanPipeline, to_kokoro_phonemes
from sci2audio.voices.letters import (
    capitals,
    english_spans,
    german_spans,
    is_spelled,
    letter_speed,
    per_sound,
    speed_tensor,
)


def request(text: str, voice: str = DEFAULT_VOICE, **parameters: object) -> SynthesisRequest:
    return SynthesisRequest(
        text=text,
        voice=VoiceSelection("builtin", voice),
        parameters=ParameterValues(parameters),
        format=PCM_FLOAT32,
    )


# --- the parameter --------------------------------------------------------------------------


@pytest.mark.parametrize("value", [LETTER_SPEED_MIN, 0.5, 0.7, LETTER_SPEED_MAX, 1, "0.7"])
def test_letter_speed_takes_numbers_from_a_quarter_to_one(value: object) -> None:
    assert letter_speed(value) == float(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value", [0.0, 0.2, 1.01, 2.0, -1.0, math.nan, math.inf, "slow", None, True]
)
def test_letter_speed_refuses_anything_else(value: object) -> None:
    with pytest.raises(InvalidInputError, match="letter_speed"):
        letter_speed(value)


# --- what counts as spelled -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "letters"),
    [
        ("NLP", "NLP"),
        ("GPUs", "GPU"),
        ("BERT's", "BERT"),
        ("BERT’s", "BERT"),
        ("ÖPNV", "ÖPNV"),
        ("AI", "AI"),
        ("RoBERTa", None),
        ("Nlp", None),
        ("A", None),
        ("As", None),
        ("GPT-4", None),
        ("A100", None),
        ("i.i.d.", None),
        ("", None),
    ],
)
def test_capitals_are_two_or_more_capital_letters(word: str, letters: str | None) -> None:
    assert capitals(word) == letters


@pytest.mark.parametrize(
    ("said", "letters", "spelled"),
    [
        ("bˌiˌiˌɑɹtˈi", "bˌiˌiˌɑɹtˈi", True),  # BERT: misaki spells it
        ("ʤˌipˌijˈuz", "ʤˌipˌijˈu", True),  # GPUs: the plural adds a sound
        ("ˈAˌI", "ˌAˈI", True),  # AI: from misaki's word list, stressed otherwise
        ("nˈæsə", "ˌɛnˌAˌɛsˈA", False),  # NASA: said as a word
        ("lˈæsO", "ˌɛlˌAˌɛsˌɛsˈO", False),  # LASSO
        ("bˈɛɾt", "bˈeː ˈeː ˈɛɾ tˈeː", False),  # German BERT: "Bert"
        ("ˌɛfkˌɑːʦˈɛt", "ˈɛf kˈɑː ʦˈɛt", True),  # German FKZ
        ("ˌɛnˌɛlpˈiɪzə", "ˌɛnˌɛlpˈi", False),  # more than a plural ending
        ("ˌɛnˌɛlpˈi", None, False),
        ("ˌɛnˌɛlpˈi", "", False),
    ],
)
def test_spelled_means_the_letters_said_one_by_one(
    said: str, letters: str | None, spelled: bool
) -> None:
    assert is_spelled(said, letters) is spelled


def tokens_to_ps(tokens: list[Any]) -> str:
    """kokoro's `KPipeline.tokens_to_ps`."""
    return "".join((t.phonemes or "") + (" " if t.whitespace else "") for t in tokens).strip()


def token(text: str, phonemes: str | None, whitespace: str = " ") -> SimpleNamespace:
    return SimpleNamespace(text=text, phonemes=phonemes, whitespace=whitespace)


SPELLINGS = {
    "GPU": "ʤˌipˌijˈu",
    "NASA": "ˌɛnˌAˌɛsˈA",
    "LSTM": "ˌɛlˌɛstˌiˈɛm",
    "AI": "ˌAˈI",
}


def test_english_spans_are_the_sounds_of_spelled_tokens() -> None:
    tokens = [
        token("“", "", " "),  # no sounds, but a space that tokens_to_ps strips
        token("We", "wˌi"),
        token("use", "jˈuz"),
        token("GPUs", "ʤˌipˌijˈuz", ""),
        token(",", ","),
        token("NASA", "nˈæsə"),
        token("data", "dˈATə"),
        token("and", "ænd"),
        token("RoBERTa", "ɹˈO bˈɜɹTə"),
        token("or", "ɔɹ"),
        token("LSTM", "ˌɛlˌɛstˌiˈɛm", ""),
        token(".", ".", ""),
    ]
    sounds = tokens_to_ps(tokens)
    spans = english_spans(tokens, SPELLINGS.get)
    assert [sounds[a:b] for a, b in spans] == ["ʤˌipˌijˈuz", "ˌɛlˌɛstˌiˈɛm"]


def test_english_without_capitals_has_no_spans() -> None:
    tokens = [token("We", "wˌi"), token("read", "ɹˈid", "")]
    assert english_spans(tokens, SPELLINGS.get) == []


def espeak_german() -> Any:
    from misaki.espeak import EspeakG2P

    return EspeakG2P(language="de")


def german_sounds(g2p: Any, vocab: dict[str, int]) -> Any:
    def sounds(text: str) -> str:
        return to_kokoro_phonemes(g2p(text)[0] or "", vocab)

    return sounds


def test_german_spans_are_spelled_words_found_in_the_sentence() -> None:
    """With the real espeak-ng: NLP and FKZ are spelled, BERT is the word "Bert"."""
    from test_voices_german import VOCAB

    sounds = german_sounds(espeak_german(), VOCAB)
    text = "Für NLP nutzen wir BERT; das FKZ steht neben NLP."
    sentence = sounds(text)
    spans = german_spans(text, sentence, sounds)
    found = [sentence[a:b] for a, b in spans]
    assert found == [sounds("NLP").strip(), sounds("FKZ").strip(), sounds("NLP").strip()]
    assert all(sounds("BERT").strip() not in part for part in found)


def test_german_spans_need_word_boundaries_and_skip_what_is_not_found() -> None:
    def sounds(text: str) -> str:
        return {"NLP": "ˌɛnˌɛlpˈeː", "N L P": "ˈɛn ˈɛl pˈeː"}.get(text, "x")

    inside = "ʔaˌɛnˌɛlpˈeːb ˌɛnˌɛlpˈeː, ˌɛnˌɛlpˈeː."
    assert german_spans("NLP", inside, sounds) == [(14, 24), (26, 36)]
    assert german_spans("NLP", "ganz anders", sounds) == []
    assert german_spans("Kein Kürzel", "kaɪn kˈʏɾʦl", sounds) == []


def test_per_sound_follows_kokoros_filtered_sounds_and_padding() -> None:
    vocab = {"a": 1, "b": 2, " ": 3}  # "c" is not a kokoro sound: KModel drops it
    assert per_sound("ab c b", vocab, [(1, 2), (5, 6)], 1.2, 0.5) == [
        1.2,
        1.2,
        0.6,
        1.2,
        1.2,
        0.6,
        1.2,
    ]
    assert per_sound("ab", vocab, [], 1.0, 0.5) == [1.0, 1.0, 1.0, 1.0]
    assert per_sound("ab", vocab, [(-3, 99)], 1.0, 0.5) == [1.0, 0.5, 0.5, 1.0]


# --- kokoro's model takes one speed per sound -------------------------------------------------


def silent_decoder() -> Any:
    """Stands in for the tiny model's decoder, whose layer sizes are fixed for the real
    model; the sound itself is not under test, only the sound lengths."""
    import torch

    class Decoder(torch.nn.Module):
        def forward(self, *parts: Any) -> Any:
            return torch.zeros(1, 1)

    return Decoder()


def test_kokoros_model_slows_only_the_sounds_given_a_lower_speed() -> None:
    """The adapter relies on `KModel.forward_with_tokens` dividing each sound's predicted
    length by `speed` (kokoro 0.9.4): a speed per sound must slow just those sounds. A
    kokoro release that changes this fails here, in every PR. The model is tiny and
    untrained; kokoro slices its style vector at 128, so the style is 128 wide."""
    import io

    import torch
    from kokoro import KModel
    from test_voices_german import TINY_CONFIG

    torch.manual_seed(295)
    buffer = io.BytesIO()
    torch.save({}, buffer)
    buffer.seek(0)
    config = {**TINY_CONFIG, "style_dim": 128}
    model = KModel(repo_id="hexgrad/Kokoro-82M", config=config, model=buffer).eval()  # type: ignore[arg-type]
    model.decoder = silent_decoder()
    ids = torch.LongTensor([[0, *range(43, 63), 0]])
    style = torch.randn(1, 256)
    rates = [1.0] * 22
    for index in range(5, 10):
        rates[index] = 0.5
    _, normal = model.forward_with_tokens(ids, style, 1)
    _, slowed = model.forward_with_tokens(ids, style, speed_tensor(rates, model.device))
    for index, (before, after) in enumerate(zip(normal.tolist(), slowed.tolist(), strict=True)):
        if 5 <= index < 10:
            assert abs(after - 2 * before) <= 1, (index, before, after)  # rounding
        else:
            assert after == before, index
    assert sum(slowed.tolist()[5:10]) > sum(normal.tolist()[5:10])


# --- the Kokoro adapter -------------------------------------------------------------------


def test_at_letter_speed_one_the_pipeline_speaks_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = FakeFactory()
    session = make_fake_engine(tmp_path, monkeypatch, factory).createSession()
    session.synthesize(request("We use NLP.", letter_speed=1.0))
    pipeline = factory.pipelines["a"]
    assert pipeline.calls == [
        {"text": "We use NLP.", "voice": pipeline.calls[0]["voice"], "speed": 1.0, "split": None}
    ]
    assert pipeline.model.calls == []


def test_english_slows_the_spelled_sounds_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = FakeFactory()
    session = make_fake_engine(tmp_path, monkeypatch, factory).createSession()
    with no_network():
        result = session.synthesize(request("We use NLP and NASA.", speed=1.25, letter_speed=0.5))
    pipeline = factory.pipelines["a"]
    assert not any("text" in call for call in pipeline.calls)  # kokoro's own loop not used
    call = pipeline.model.calls[-1]
    sounds = call["sounds"]
    assert sounds == f"we use {fake_spelling('NLP')} and nasa."
    slow = [rate for rate in call["rates"] if rate != 1.25]
    assert slow == [0.625] * len(fake_spelling("NLP"))
    start = 1 + sounds.index(fake_spelling("NLP"))  # after the padding token
    assert call["rates"][start : start + len(slow)] == slow
    assert [t.text for t in result.segments[0].tokens] == ["We", "use", "NLP", "and", "NASA", "."]
    assert all(t.end > t.start for t in result.segments[0].tokens)


def test_english_without_spelled_letters_gets_the_plain_speed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = FakeFactory()
    session = make_fake_engine(tmp_path, monkeypatch, factory).createSession()
    session.synthesize(request("We read NASA data.", "bm_george", speed=0.9, letter_speed=0.5))
    assert factory.pipelines["b"].model.calls[-1]["speed"] == 0.9  # a number, not per sound


def test_slower_letters_make_longer_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = make_fake_engine(tmp_path, monkeypatch).createSession()
    lengths = [
        len(session.synthesize(request("We use LSTM.", letter_speed=value)).data)
        for value in (0.99, 0.7, 0.5)
    ]
    assert lengths == sorted(lengths)
    assert len(set(lengths)) == 3


def test_german_passes_the_letter_speed_to_its_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = FakeFactory()
    session = make_fake_engine(tmp_path, monkeypatch, factory).createSession()
    session.synthesize(request("Wir nutzen NLP.", GERMAN_DEFAULT_VOICE, letter_speed=0.7))
    session.synthesize(request("Wir nutzen NLP.", GERMAN_DEFAULT_VOICE))
    calls = factory.pipelines["d"].calls
    assert calls[0]["letter_speed"] == 0.7
    assert "letter_speed" not in calls[1]


@pytest.mark.parametrize("value", [0.0, 1.5, "slow", math.nan])
def test_the_adapter_refuses_a_bad_letter_speed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    session = make_fake_engine(tmp_path, monkeypatch).createSession()
    with pytest.raises(InvalidInputError, match="letter_speed"):
        session.synthesize(request("We use NLP.", letter_speed=value))


class RecordingModel:
    """Stands in for kokoro's KModel in the German pipeline: records the speed."""

    def __init__(self, vocab: dict[str, int]) -> None:
        self.vocab = vocab
        self.device = "cpu"
        self.speeds: list[Any] = []

    def __call__(self, sounds: str, style: Any, speed: Any, *, return_output: bool) -> Any:
        import torch

        self.speeds.append(speed)
        return SimpleNamespace(audio=torch.zeros(len(sounds)))


def test_the_german_pipeline_slows_spelled_letters(tmp_path: Path) -> None:
    import torch
    from test_voices_german import VOCAB

    pack = tmp_path / "thorsten.pt"
    torch.save(torch.zeros(510, 1, 1), pack)
    model = RecordingModel(VOCAB)
    g2p = espeak_german()
    pipeline = GermanPipeline(model=model, g2p=g2p)
    text = "Für NLP nutzen wir BERT."
    with no_network():
        list(pipeline(text, voice=str(pack), speed=1.0, letter_speed=0.5))
        list(pipeline(text, voice=str(pack), speed=1.0))
        list(pipeline("Wir nutzen BERT.", voice=str(pack), speed=1.0, letter_speed=0.5))
    per_sound_speed, plain, word_only = model.speeds
    sounds = german_sounds(g2p, VOCAB)
    nlp = len(sounds("NLP").strip())
    assert np.count_nonzero(per_sound_speed.numpy() == 0.5) == nlp
    assert plain == 1.0
    assert word_only == 1.0  # "BERT" is said as a word: nothing to slow
