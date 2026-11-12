# Baseline measurements

Measured **before** code moves in or changes, so later improvements can be proven. Fill in once; add a dated row when something is re-measured.

## Old version (private `audiobook-generator`, frozen)

| Measure | Value | Date | How measured |
|---|---|---|---|
| Collected tests | 1,279 | 2026-11-09 | `pytest --collect-only -q` |
| Fast suite runtime | | | |
| Output of 3 corpus papers | | | saved as `docs/baseline-output/` (not committed if large) |

## Voice engine (VA-02, D-48: PyTorch)

| Machine | Device | Characters per second | Install size | Notes |
|---|---|---|---|---|
| MacBook Pro M4 | Apple GPU (MPS) | | | `PYTORCH_ENABLE_MPS_FALLBACK=1`; Colin measures (VA-02) |
| Windows laptop | CPU | | | |
| Linux | CPU | | | |
| Linux cloud container, 4 vCPU (Intel(R) Xeon(R) Processor @ 2.10GHz), 2026-11-12 | CPU, torch 2.15.0+cpu | 66 to 74 (warm; `test_kokoro_speed_on_cpu`: 160 characters, 9.7 s of audio in 2.2 to 2.4 s, about 4 × real time); model load 6 to 13 s | 1.3 GB environment with the CPU torch index (`--torch-backend cpu`); 5.6 GB with the default PyPI torch, which pulls the CUDA libraries (3.0 GB nvidia, 1.0 GB triton) | Kokoro-82M, voice `af_heart`, kokoro 0.9.4; measured in #18. Plus 355 MB of voice files in the model folder |

Speech-recognition round trip (#9), same machine and date: word error rate **0.012** over 249 words (16 sentences of *The Time Machine*, chapter I), whisper `small` int8; the errors are spellings ("traveler", "gray") and one rare word.

## Output: writing the audiobook (#69)

`uv run pytest tests/unit/test_output_long.py -m benchmark --benchmark-only`: 10 minutes of
24 kHz mono audio (60 chunks, 3 chapters) to 3 MP3s, one M4B and the read-along file.

| Machine | Mean time | Date | Notes |
|---|---|---|---|
| Linux container, x86_64 (cloud session) | 1.77 s (3 rounds, 1.68 to 1.87 s) | 2026-11-12 | bundled ffmpeg 9.0.2 from imageio-ffmpeg 0.8.1; about 340 times faster than real time |

## Text preparation

| Measure | Value | Date | How measured |
|---|---|---|---|
| Cut the largest corpus paper into utterances (`cut_utterances`, `arxiv2024-arsiwalla-qualia-meaning`: 82,692 script characters, 797 utterances) | 15.9 ms mean (13.8 ms median) | 2026-11-12 | `uv run pytest -m benchmark --benchmark-only -k cutting` in a Linux cloud container (x86_64, 4 cores, not a CI runner); Issue #63 |
| Same, after review round 1 of #86 (kept text checked against the document, no-break spaces, the window for the fallback cut) | 24.8 ms mean (21.9 ms median) | 2026-11-12 | as above |
| Cut 300,000 characters without a full stop (fallback cut only) | 0.08 s (before the window it was quadratic: 1.24 s for 100,000 characters in the #86 review, so about 11 s extrapolated) | 2026-11-12 | `test_a_long_text_without_a_full_stop_is_cut_in_linear_time`, same container |

## Script job: a paper to its listening script and report (#70)

`uv run pytest tests/unit/test_app_corpus.py -m benchmark --benchmark-only`: the 28-page
arsiwalla paper from file to script, report and job record (extraction, layout, text steps,
chapters, cutting, writing). Budget: under 30 s for a 20-page paper (#11); the test fails
above 30 s.

| Machine | Mean time | Date | Notes |
|---|---|---|---|
| Linux container, x86_64 (cloud session) | 1.02 s (3 rounds, 1.01 to 1.03 s) | 2026-11-12 | built-in text steps of #63 (page furniture only); each text step that lands adds to it |
