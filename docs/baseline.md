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
