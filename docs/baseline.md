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
| MacBook Pro M4 | Apple GPU (MPS) | | | `PYTORCH_ENABLE_MPS_FALLBACK=1` |
| Windows laptop | CPU | | | |
| Linux | CPU | | | |

## Output: writing the audiobook (#69)

`uv run pytest tests/unit/test_output_long.py -m benchmark --benchmark-only`: 10 minutes of
24 kHz mono audio (60 chunks, 3 chapters) to 3 MP3s, one M4B and the read-along file.

| Machine | Mean time | Date | Notes |
|---|---|---|---|
| Linux container, x86_64 (cloud session) | 1.77 s (3 rounds, 1.68 to 1.87 s) | 2026-11-12 | bundled ffmpeg 9.0.2 from imageio-ffmpeg 0.8.1; about 340 times faster than real time |
