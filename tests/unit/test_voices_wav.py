"""Voice audio as 16-bit mono WAV files for the output stage (#69 contract, VA-05)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays
from voice_fakes import make_fake_engine

from sci2audio.voices import (
    PREVIEW_TEXT,
    SAMPLE_RATE,
    InvalidInputError,
    preview,
    speak_to_wav,
    write_wav,
)
from sci2audio.voices import wav as wav_module


def read(path: Path) -> tuple[wave._wave_params, np.ndarray]:
    with wave.open(str(path), "rb") as stream:
        return stream.getparams(), np.frombuffer(stream.readframes(stream.getnframes()), "<i2")


@given(arrays(np.float32, st.integers(0, 300), elements=st.floats(width=32)))
def test_pcm16_never_fails_and_stays_in_range(samples: np.ndarray) -> None:
    pcm = np.frombuffer(wav_module.to_pcm16(samples), "<i2")
    assert len(pcm) == len(samples)
    finite = np.isfinite(samples)
    expected = np.round(np.clip(samples[finite].astype(np.float64), -1, 1) * 32767)
    assert np.array_equal(pcm[finite], expected.astype("<i2"))
    assert np.all(pcm[np.isnan(samples)] == 0)
    assert np.all(pcm[samples == np.inf] == 32767)
    assert np.all(pcm[samples == -np.inf] == -32767)


def test_write_wav_is_mono_16_bit_and_times_from_frames(tmp_path: Path) -> None:
    path = tmp_path / "chunk.wav"
    seconds = write_wav(path, np.array([0.0, 0.5, -0.5, 2.0], dtype=np.float32), 24000)
    params, pcm = read(path)
    assert (params.nchannels, params.sampwidth, params.framerate, params.nframes) == (
        1,
        2,
        24000,
        4,
    )
    assert pcm.tolist() == [0, 16384, -16384, 32767]
    assert seconds == 4 / 24000
    assert not list(tmp_path.glob("*.part"))


def test_empty_audio_is_a_valid_zero_frame_wav(tmp_path: Path) -> None:
    path = tmp_path / "chunk.wav"
    assert write_wav(path, np.zeros(0, dtype=np.float32), 24000) == 0
    assert read(path)[0].nframes == 0


def test_bad_sample_rate_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError):
        write_wav(tmp_path / "x.wav", np.zeros(3), 0)


def test_failed_write_leaves_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "chunk.wav"

    def full(self: object, data: bytes) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(wave.Wave_write, "writeframes", full)
    with pytest.raises(OSError, match="No space"):
        write_wav(path, np.ones(10, dtype=np.float32), 24000)
    assert list(tmp_path.iterdir()) == []


def test_speak_to_wav_and_preview_through_the_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = make_fake_engine(tmp_path / "models", monkeypatch).createSession()
    normal = speak_to_wav(session, "Hello there.", "af_heart", tmp_path / "a.wav")
    fast = speak_to_wav(session, "Hello there.", "af_heart", tmp_path / "b.wav", speed=2.0)
    params, _ = read(tmp_path / "a.wav")
    assert params.framerate == SAMPLE_RATE
    assert normal == params.nframes / SAMPLE_RATE
    assert fast < normal

    seconds = preview(session, "bf_emma", tmp_path / "p.wav", speed=1.5)
    assert seconds == pytest.approx(int(len(PREVIEW_TEXT) * 100 / 1.5) / SAMPLE_RATE)
