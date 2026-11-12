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
| Same, after review round 1 of #86 (kept text checked against the document, no-break spaces, the window for the fallback cut) | 24.8 ms mean (21.9 ms median) | 2026-11-12 | as above |
| Cut 300,000 characters without a full stop (fallback cut only) | 0.08 s (before the window it was quadratic: 1.24 s for 100,000 characters in the #86 review, so about 11 s extrapolated) | 2026-11-12 | `test_a_long_text_without_a_full_stop_is_cut_in_linear_time`, same container |
