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

## Text preparation

| Measure | Value | Date | How measured |
|---|---|---|---|
| Cut the largest corpus paper into utterances (`cut_utterances`, `arxiv2024-arsiwalla-qualia-meaning`: 82,692 script characters, 797 utterances) | 15.9 ms mean (13.8 ms median) | 2026-11-12 | `uv run pytest -m benchmark --benchmark-only -k cutting` in a Linux cloud container (x86_64, 4 cores, not a CI runner); Issue #63 |
