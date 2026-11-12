"""Kokoro adapter on a fake pipeline: contract, voices, local files only (VA-01, VA-04)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from voice_fakes import FakeFactory, FakeResult, isolate_environment, make_fake_engine

from sci2audio.testing import check_voice_engine, no_network
from sci2audio.voices import (
    DEFAULT_VOICE,
    ENGLISH_VOICES,
    PCM_FLOAT32,
    SAMPLE_RATE,
    AudioFormat,
    EngineError,
    InvalidInputError,
    ModelNotFoundError,
    ParameterValues,
    SynthesisRequest,
    VoiceSelection,
    create_kokoro_engine,
    download_plan,
)
from sci2audio.voices import kokoro_engine as kokoro_module


def request(text: str, voice: str = DEFAULT_VOICE, **parameters: object) -> SynthesisRequest:
    return SynthesisRequest(
        text=text,
        voice=VoiceSelection("builtin", voice),
        parameters=ParameterValues(parameters),
        format=PCM_FLOAT32,
    )


def test_fake_kokoro_passes_the_conformance_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    check_voice_engine(lambda: make_fake_engine(tmp_path, monkeypatch))


def test_english_voices_are_28_and_all_downloaded() -> None:
    assert len(ENGLISH_VOICES) == 28
    assert {v.id[:2] for v in ENGLISH_VOICES} == {"af", "am", "bf", "bm"}
    assert DEFAULT_VOICE in {v.id for v in ENGLISH_VOICES}
    downloaded = {Path(f.target).stem for f in download_plan().files if "/voices/" in f.target}
    assert downloaded == {v.id for v in ENGLISH_VOICES}
    gb = {v.id for v in ENGLISH_VOICES if v.language == "en-GB"}
    assert gb == {v.id for v in ENGLISH_VOICES if v.id.startswith("b")}


def test_voice_is_passed_as_a_local_file_never_a_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = FakeFactory()
    session = make_fake_engine(tmp_path, monkeypatch, factory).createSession()
    session.synthesize(request("Hello there.", "bm_george", speed=1.25))
    call = factory.pipelines["b"].calls[-1]
    assert Path(call["voice"]) == kokoro_module.kokoro_dir(tmp_path) / "voices" / "bm_george.pt"
    assert call["speed"] == 1.25
    assert call["split"] is None


def test_one_pipeline_per_accent_made_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    factory = FakeFactory()
    made: list[str] = []

    def counting(lang_code: str) -> object:
        made.append(lang_code)
        return factory(lang_code)

    session = make_fake_engine(tmp_path, monkeypatch, counting).createSession()  # type: ignore[arg-type]
    for voice in ("af_heart", "am_michael", "bf_emma", "bm_lewis", "af_sky"):
        session.synthesize(request("Hi.", voice))
    assert made == ["a", "b"]


def test_audio_segments_and_token_timings_are_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = make_fake_engine(tmp_path, monkeypatch).createSession()
    result = session.synthesize(request("one two\n\nthree"))
    samples = np.frombuffer(result.data, dtype="<f4")
    assert result.sample_rate == SAMPLE_RATE
    assert result.duration.seconds == pytest.approx(len(samples) / SAMPLE_RATE)
    # the empty middle line has no audio and is skipped
    assert [s.graphemes for s in result.segments] == ["one two", "three"]
    assert [t.text for t in result.segments[0].tokens] == ["one", "two"]
    assert sum(len(s.audio) for s in result.segments) == len(result.data)


def test_text_without_sound_gives_empty_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def silent(lang_code: str) -> object:
        return lambda text, **kwargs: iter([FakeResult(graphemes=text, audio=None)])

    session = make_fake_engine(tmp_path, monkeypatch, silent).createSession()  # type: ignore[arg-type]
    result = session.synthesize(request("..."))
    assert result.data == b""
    assert result.duration.seconds == 0
    assert result.segments == ()


@pytest.mark.parametrize(
    ("req", "what"),
    [
        (request(""), "empty"),
        (request("Hi.", "zf_xiaoxiao"), "a Chinese voice is not offered (D-50)"),
        (request("Hi.", speed=0.49), "too slow"),
        (request("Hi.", speed=2.01), "too fast"),
        (request("Hi.", speed=None), "not a number"),
        (
            SynthesisRequest(
                "Hi.",
                VoiceSelection("builtin", DEFAULT_VOICE),
                ParameterValues(),
                AudioFormat("audio/mpeg", "mp3"),
            ),
            "another format",
        ),
    ],
)
def test_invalid_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, req: SynthesisRequest, what: str
) -> None:
    session = make_fake_engine(tmp_path, monkeypatch).createSession()
    with pytest.raises(InvalidInputError):
        session.synthesize(req)


def test_engine_failure_is_an_engine_error_and_the_session_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = FakeFactory()
    session = make_fake_engine(tmp_path, monkeypatch, factory).createSession()
    pipeline = factory.pipelines["a"]

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("kernel exploded")

    monkeypatch.setattr(type(pipeline), "__call__", broken)
    with pytest.raises(EngineError, match="kernel exploded"):
        session.synthesize(request("Hi."))
    monkeypatch.undo()
    isolate_environment(monkeypatch)
    assert session.synthesize(request("Hi.")).data


def test_missing_voice_file_is_reported_not_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = make_fake_engine(tmp_path, monkeypatch).createSession()
    (kokoro_module.kokoro_dir(tmp_path) / "voices" / "af_bella.pt").unlink()
    with pytest.raises(ModelNotFoundError, match="af_bella"):
        session.synthesize(request("Hi.", "af_bella"))


def test_missing_files_stop_before_anything_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_environment(monkeypatch)

    def never(lang_code: str) -> None:
        raise AssertionError("no pipeline may be built without the files")

    with no_network(), pytest.raises(ModelNotFoundError, match="run the voice download"):
        create_kokoro_engine(tmp_path, pipeline_factory=never)


def test_missing_spacy_model_never_triggers_its_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spacy
    import spacy.cli

    def no_download(*args: object, **kwargs: object) -> None:
        raise AssertionError("spacy.cli.download was called")

    monkeypatch.setattr(spacy.util, "is_package", lambda name: False)
    monkeypatch.setattr(spacy.cli, "download", no_download)
    with no_network(), pytest.raises(ModelNotFoundError, match="en_core_web_sm"):
        kokoro_module._kokoro_pipeline_factory(tmp_path, "cpu")


def test_creating_the_engine_runs_the_start_up_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_fake_engine(tmp_path, monkeypatch)
    assert os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] == "1"
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert sys.path[-1] == str(tmp_path / "spacy" / "en_core_web_sm-3.8.0")


def test_factory_error_becomes_engine_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(lang_code: str) -> None:
        raise OSError("weights unreadable")

    with pytest.raises(EngineError, match="Failed to create Kokoro engine: weights unreadable"):
        make_fake_engine(tmp_path, monkeypatch, broken)  # type: ignore[arg-type]


def test_importing_voices_does_not_import_torch_or_kokoro() -> None:
    code = (
        "import sys, sci2audio.voices, sci2audio.testing.voices; "
        "print(sorted(m for m in ('torch', 'kokoro', 'misaki', 'spacy') if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == "[]"
