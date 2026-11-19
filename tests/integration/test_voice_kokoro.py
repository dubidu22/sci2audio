"""Kokoro English with the real model, offline (VA-01, VA-04, #9, #11). Nightly only.

Needs the models fetched by `prepare_models.py`; the nightly workflow sets
SCI2AUDIO_TEST_MODELS (voice files) and SCI2AUDIO_TEST_WHISPER (speech recognition).
Every test runs with the network blocked.
"""

from __future__ import annotations

import html.parser
import os
import re
import time
import wave
import zipfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from sci2audio.testing import check_voice_engine, no_network
from sci2audio.textprep import DEFAULT_MAX_CHARS
from sci2audio.voices import (
    PCM_FLOAT32,
    KokoroEngine,
    ParameterValues,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceSelection,
    create_kokoro_engine,
    speak_to_wav,
)

CORPUS = Path(__file__).parents[1] / "corpus"
WER_LIMIT = 0.10
PARAGRAPHS = 5


def models_dir() -> Path:
    folder = os.environ.get("SCI2AUDIO_TEST_MODELS")
    if not folder:
        pytest.skip("SCI2AUDIO_TEST_MODELS is not set (run tests/integration/prepare_models.py)")
    return Path(folder)


@pytest.fixture(scope="module")
def engine() -> Iterator[KokoroEngine]:
    with no_network():
        made = create_kokoro_engine(models_dir())
    yield made
    made.dispose()


def wav_params(path: Path) -> tuple[wave._wave_params, np.ndarray]:
    with wave.open(str(path), "rb") as stream:
        return stream.getparams(), np.frombuffer(stream.readframes(stream.getnframes()), "<i2")


@pytest.mark.slow
@pytest.mark.parametrize("voice", ["af_heart", "bm_george"])
def test_two_voices_speak_a_sentence_into_a_wav_file(
    engine: KokoroEngine, voice: str, tmp_path: Path
) -> None:
    path = tmp_path / f"{voice}.wav"
    with no_network():
        seconds = speak_to_wav(
            engine.createSession(), "The experiment was repeated three times.", voice, path
        )
    params, pcm = wav_params(path)
    assert (params.nchannels, params.sampwidth, params.framerate) == (1, 2, 24000)
    assert seconds == params.nframes / 24000
    assert 1.0 < seconds < 8.0
    assert np.abs(pcm).max() > 1000  # not silence


@pytest.mark.slow
def test_kokoro_passes_the_conformance_suite() -> None:
    check_voice_engine(lambda: create_kokoro_engine(models_dir()))


# --- speech-recognition round trip (#9) ---------------------------------------------------


class _Paragraphs(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "p":
            self.depth += 1
            self.texts.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.texts[-1] += data


def time_machine_sentences() -> list[str]:
    """Sentences of the first paragraphs of The Time Machine (public domain, plain prose)."""
    with zipfile.ZipFile(CORPUS / "epub" / "wells-the-time-machine.epub") as book:
        parser = _Paragraphs()
        parser.feed(book.read("epub/text/chapter-1.xhtml").decode("utf-8"))
    paragraphs = [" ".join(p.split()) for p in parser.texts if p.strip()][:PARAGRAPHS]
    return [s for p in paragraphs for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\u201c\u2018])", p) if s]


def at_16_khz(path: Path) -> np.ndarray:
    """The WAV as float samples at 16 kHz, the rate whisper expects (linear resampling).

    Passing samples skips faster-whisper's own decoder, which breaks with new PyAV releases.
    """
    params, pcm = wav_params(path)
    samples = pcm.astype(np.float32) / 32768.0
    duration = params.nframes / params.framerate
    target = np.arange(int(duration * 16000)) / 16000
    return np.interp(target, np.arange(params.nframes) / params.framerate, samples).astype(
        np.float32
    )


def words(text: str) -> list[str]:
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)


def edit_distance(a: list[str], b: list[str]) -> int:
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (x != y))
    return row[-1]


def test_edit_distance_counts_word_changes() -> None:
    assert edit_distance(words("the cat sat"), words("The cat sat.")) == 0
    assert edit_distance(words("the cat sat"), words("a cat sat down")) == 2
    assert words("It\u2019s \u201cfine\u201d, isn't it?") == ["it's", "fine", "isn't", "it"]


@pytest.mark.slow
def test_speech_recognition_round_trip(
    engine: KokoroEngine, tmp_path: Path, record_property: pytest.RecordProperty
) -> None:
    whisper_dir = os.environ.get("SCI2AUDIO_TEST_WHISPER")
    if not whisper_dir:
        pytest.skip("SCI2AUDIO_TEST_WHISPER is not set (run tests/integration/prepare_models.py)")
    from faster_whisper import WhisperModel

    sentences = time_machine_sentences()
    assert len(sentences) >= 15
    session = engine.createSession()
    results = []
    with no_network():
        recogniser = WhisperModel(whisper_dir, device="cpu", compute_type="int8")
        for n, sentence in enumerate(sentences):
            path = tmp_path / f"{n:03d}.wav"
            speak_to_wav(session, sentence, "af_heart", path)
            segments, _ = recogniser.transcribe(at_16_khz(path), language="en", beam_size=5)
            heard = " ".join(s.text for s in segments)
            expected = words(sentence)
            errors = edit_distance(expected, words(heard))
            results.append((errors / max(len(expected), 1), errors, len(expected), sentence, heard))

    total_errors = sum(r[1] for r in results)
    total_words = sum(r[2] for r in results)
    wer = total_errors / total_words
    worst = sorted(results, reverse=True)[:3]
    report = [f"WER {wer:.3f} over {total_words} words in {len(results)} sentences"] + [
        f"  {r[0]:.2f}  said: {r[3]!r}\n        heard: {r[4]!r}" for r in worst
    ]
    print("\n".join(report))
    record_property("wer", round(wer, 4))
    record_property("worst_sentences", [r[3] for r in worst])
    assert wer < WER_LIMIT, "\n".join(report)


# --- speed (#11, VA-02) -------------------------------------------------------------------

BENCHMARK_TEXT = (
    "I think that at that time none of us quite believed in the Time Machine. "
    "The fact is, the Time Traveller was one of those men who are too clever to be believed."
)


@pytest.mark.benchmark
def test_kokoro_speed_on_cpu(engine: KokoroEngine, tmp_path: Path, benchmark: object) -> None:
    session = engine.createSession()
    path = tmp_path / "bench.wav"

    def speak() -> float:
        with no_network():
            return speak_to_wav(session, BENCHMARK_TEXT, "af_heart", path)

    started = time.perf_counter()
    seconds = benchmark.pedantic(speak, rounds=3, warmup_rounds=1)  # type: ignore[attr-defined]
    elapsed = (time.perf_counter() - started) / 4
    benchmark.extra_info["characters_per_second"] = round(len(BENCHMARK_TEXT) / elapsed, 1)  # type: ignore[attr-defined]
    benchmark.extra_info["realtime_factor"] = round(seconds / elapsed, 2)  # type: ignore[attr-defined]
    assert seconds > 5


# --- units read as words (#68, D-243) -----------------------------------------------------

# Whisper writes some spoken units back as symbols; these turn its spelling into words
# before comparing, so the check is on what was heard, not on how whisper prints it.
HEARD_AS_SYMBOLS = {
    "mg/kg": "milligrams per kilogram",
    "°c": "degrees celsius",
    "° c": "degrees celsius",
    "mg": "milligrams",
    "kg": "kilograms",
}
UNITS_WER_LIMIT = 0.25


def heard_words(text: str) -> list[str]:
    text = text.lower()
    for symbol, spoken in HEARD_AS_SYMBOLS.items():
        text = text.replace(symbol, f" {spoken} ")
    return words(text)


@pytest.mark.slow
def test_units_are_heard_as_words(engine: KokoroEngine, tmp_path: Path) -> None:
    """The `units` regression case, as the built-in steps write it, spoken and heard back:
    "milligrams per kilogram" and "degrees Celsius" are heard (D-243)."""
    whisper_dir = os.environ.get("SCI2AUDIO_TEST_WHISPER")
    if not whisper_dir:
        pytest.skip("SCI2AUDIO_TEST_WHISPER is not set (run tests/integration/prepare_models.py)")
    from faster_whisper import WhisperModel

    from sci2audio.testing.regression import load_cases, render
    from sci2audio.textprep import StepContext, run_steps

    cases = load_cases(Path(__file__).parents[1] / "regression" / "english.toml")
    case = next(case for case in cases if case.id == "units")
    (script,) = render(run_steps(case.document, StepContext("en"), strict=True))
    assert "milligrams per kilogram" in script
    path = tmp_path / "units.wav"
    with no_network():
        speak_to_wav(engine.createSession(), script, "af_heart", path)
        recogniser = WhisperModel(whisper_dir, device="cpu", compute_type="int8")
        segments, _ = recogniser.transcribe(at_16_khz(path), language="en", beam_size=5)
    heard = " ".join(s.text for s in segments)
    got = heard_words(heard)
    joined = " ".join(got)
    assert "milligrams per kilogram" in joined, heard
    assert "degrees celsius" in joined, heard
    expected = words(script)
    wer = edit_distance(expected, got) / len(expected)
    assert wer < UNITS_WER_LIMIT, f"WER {wer:.2f}: said {script!r}, heard {heard!r}"


# --- statistics read as words (#67, D-191) ------------------------------------------------

# Whisper writes some spoken statistics back as signs or as "0.05"; these turn its spelling
# into the words and digits of the script before comparing.
HEARD_AS_STATISTICS = {
    "<": " less than ",
    ">": " greater than ",
    "=": " equals ",
}
STATISTICS_WER_LIMIT = 0.25


def heard_statistics(text: str) -> list[str]:
    text = text.lower()
    for sign, spoken in HEARD_AS_STATISTICS.items():
        text = text.replace(sign, spoken)
    return words(re.sub(r"\b0(?=\.\d)", "", text))  # "0.05" as printed: ".05"


@pytest.mark.slow
def test_statistics_are_heard_as_words(engine: KokoroEngine, tmp_path: Path) -> None:
    """The `statistics` regression case, as the built-in steps write it, spoken and heard
    back: "less than", "equals" and "confidence interval" are heard (D-191)."""
    whisper_dir = os.environ.get("SCI2AUDIO_TEST_WHISPER")
    if not whisper_dir:
        pytest.skip("SCI2AUDIO_TEST_WHISPER is not set (run tests/integration/prepare_models.py)")
    from faster_whisper import WhisperModel

    from sci2audio.testing.regression import load_cases, render
    from sci2audio.textprep import StepContext, run_steps

    cases = load_cases(Path(__file__).parents[1] / "regression" / "english.toml")
    case = next(case for case in cases if case.id == "statistics")
    (script,) = render(run_steps(case.document, StepContext("en"), strict=True))
    assert "p less than .05" in script
    path = tmp_path / "statistics.wav"
    with no_network():
        speak_to_wav(engine.createSession(), script, "af_heart", path)
        recogniser = WhisperModel(whisper_dir, device="cpu", compute_type="int8")
        segments, _ = recogniser.transcribe(at_16_khz(path), language="en", beam_size=5)
    heard = " ".join(s.text for s in segments)
    got = heard_statistics(heard)
    joined = " ".join(got)
    for spoken in ("less than", "equals", "confidence interval"):
        assert spoken in joined, heard
    expected = words(script)
    wer = edit_distance(expected, got) / len(expected)
    assert wer < STATISTICS_WER_LIMIT, f"WER {wer:.2f}: said {script!r}, heard {heard!r}"


# --- one sentence per call up to the cut limit (#494) -------------------------------------

# own sentences, in the spoken form the text steps hand over; each is one utterance
LIMIT_PROSE = (
    "The teachers who took part in the second round of the study were asked to keep a shorter "
    "diary of every lesson in which they used the new material, to note what worked well and "
    "what did not, and to send it back at the end of each month, so that the team could see "
    "how the use of the material changed over the school year and where the teachers needed "
    "more help than the written guide could give them."
)
# digits the voice reads out make it denser than prose: over its 510 tokens per call
LIMIT_NUMBERS = (
    "Between 2019 and 2023 the 14 clinics treated 1284 patients aged 18 to 65, of whom 312 "
    "took 25 milligrams and 297 took 50 milligrams twice a day for 12 weeks, while 675 took "
    "placebo; at week 24 the mean score fell by 73 points in the first group, 91 points in "
    "the second and 24 points in the third, a difference of 49 points that held in all 14 "
    "clinics and in 1187 of the 1284 patients."
)


def synthesize(engine: KokoroEngine, text: str, voice: str) -> SynthesizedAudio:
    return engine.createSession().synthesize(
        SynthesisRequest(
            text=text,
            voice=VoiceSelection(source="builtin", key=voice),
            parameters=ParameterValues({"speed": 1.0}),
            format=PCM_FLOAT32,
        )
    )


def digits_and_words(text: str, pattern: str) -> tuple[str, list[str]]:
    """Every digit in order, joined (whisper writes "1284" as "1284", "12 84" or "1.284"),
    and the words that are not numbers."""
    found = re.findall(pattern, text.lower())
    return "".join(w for w in found if w.isdigit()), [w for w in found if not w.isdigit()]


def assert_spoken_whole(text: str, got: str, pattern: str, limit: float) -> None:
    said_digits, said_words = digits_and_words(text, pattern)
    heard_digits, heard_words = digits_and_words(got, pattern)
    assert heard_digits == said_digits, f"a number was lost: heard {got!r}"
    wer = edit_distance(said_words, heard_words) / len(said_words)
    assert wer < limit, f"WER {wer:.2f} of the words: heard {got!r}"


@pytest.mark.slow
def test_a_sentence_at_the_cut_limit_is_one_model_call(engine: KokoroEngine) -> None:
    """#494: a sentence of DEFAULT_MAX_CHARS characters is spoken in one pass of the model,
    so the voice keeps its own pause and pitch at the commas."""
    assert len(LIMIT_PROSE) == DEFAULT_MAX_CHARS
    with no_network():
        result = synthesize(engine, LIMIT_PROSE, "af_heart")
    assert len(result.segments) == 1
    assert result.duration.seconds > 15


@pytest.mark.slow
def test_a_dense_sentence_over_the_model_limit_is_spoken_whole(
    engine: KokoroEngine, tmp_path: Path
) -> None:
    """#494 (D-743 A1): a sentence under the cut limit but over the model's 510 tokens is
    split by the voice itself, and every number and word is still heard."""
    whisper_dir = os.environ.get("SCI2AUDIO_TEST_WHISPER")
    if not whisper_dir:
        pytest.skip("SCI2AUDIO_TEST_WHISPER is not set (run tests/integration/prepare_models.py)")
    from faster_whisper import WhisperModel

    assert len(LIMIT_NUMBERS) <= DEFAULT_MAX_CHARS
    path = tmp_path / "dense.wav"
    with no_network():
        assert len(synthesize(engine, LIMIT_NUMBERS, "af_heart").segments) > 1
        speak_to_wav(engine.createSession(), LIMIT_NUMBERS, "af_heart", path)
        recogniser = WhisperModel(whisper_dir, device="cpu", compute_type="int8")
        segments, _ = recogniser.transcribe(at_16_khz(path), language="en", beam_size=5)
        got = " ".join(s.text for s in segments)
    assert_spoken_whole(LIMIT_NUMBERS, got, r"[a-z0-9]+", WER_LIMIT)
