# Baseline measurements

Measured **before** code moves in or changes, so later improvements can be proven. Fill in once; add a dated row when something is re-measured.

## Old version (private `audiobook-generator`, frozen)

| Measure | Value | Date | How measured |
|---|---|---|---|
| Collected tests | 1,279 | 2026-11-09 | `pytest --collect-only -q` |
| Fast suite runtime | | | |
| Output of 3 corpus papers | | | saved as `docs/baseline-output/` (not committed if large) |

## Performance budget (#11, D-286)

What sci2audio should manage. `scripts/speed.py` prints each line as met, not met or not judged for the machine it runs on; only the first line is enforced in CI, because CI machines vary ("compare trends, not single runs").

| Target | Checked by | Enforced |
|---|---|---|
| A 20-page paper prepared (reading, layout, text steps, chapters, cutting) in under 30 s | `test_app_corpus.py` benchmark (fails above 30 s); the speed script reports seconds per page | yes, nightly |
| Speech faster than real time (real-time factor at least 1) on the reference machine, the MacBook Pro M4, with the device the app picks by itself | speed script on the M4 (Colin, before v1.0) | no |
| The time estimate within ±25 % of the real remaining speaking time, from the moment it is shown while a minute or more of speech is left | speed script, every machine | no |
| Encoding (MP3s, M4B, read-along) at least 50 times faster than real time | speed script; `test_output_long.py` benchmark | no |

## Speed script (#11, D-281 to D-287)

`uv run python scripts/speed.py` after `uv run sci2audio voices download`; `--quick` for the short paper, `--help` for the options. Offline (the network is blocked once the voice files are found). It measures on every device torch has on the machine (on the M4: MPS and CPU, D-282), writes every number to a JSON file (`sci2audio-speed` version 1, D-285) and prints the rows below, ready to paste. The machine is named by its model, processor, cores and memory, never by its host name. Nightly, the `benchmarks` job runs `--quick --device cpu` (D-287); its numbers are in the job's log.

**The voice alone.** Six sentences of our own (517 characters) spoken one by one, as the job does; the first sentence once more before, as warm-up, not counted. Characters per second and the real-time factor (seconds of audio per second of work); model load once per device.

| Machine | Device | Voice | Characters per second | Real-time factor | Model load | Date | Commit |
|---|---|---|---|---|---|---|---|
| macOS 26.6.2, Mac16,1, Apple M4, 10 cores, 16 GB | mps, torch 2.15.0 | af_heart | 100.8 | 6.41 | 16.62 s | 2026-11-14 | 87ba1f59d51b |
| macOS 26.6.2, Mac16,1, Apple M4, 10 cores, 16 GB | cpu, torch 2.15.0 | af_heart | 135.2 | 8.6 | 1.52 s | 2026-11-14 | 87ba1f59d51b |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | af_heart | 60.2 | 3.83 | 5.32 s | 2026-11-13 | 79db1fcb7ded |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | af_heart | 46.9 | 2.99 | 5.54 s | 2026-11-13 | 79db1fcb7ded |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | all 28 English voices (`--all-voices --skip-job`) | 44.3 (af_nicole) to 88.8 (af_jessica), median 65.7; af_heart 65.4 | 3.42 (bf_lily) to 5.17 (af_nova), median 4.44 | 4.94 s | 2026-11-13 | 79db1fcb7ded |

The three af_heart numbers on the same container (46.9, 60.2, 65.4 characters per second) show how much a shared cloud machine varies from run to run. Voices differ more in characters per second (some speak slower, so the same text takes more audio) than in real-time factor.

**The audio job.** The paper from a cold cache to its MP3s, M4B and read-along file, voice af_heart at speed 1, default chapters. Preparation = reading, layout and text steps; speaking includes the warm-up; the characters per second are the job's own measure (D-159). Since #136 the estimate fits a cost per chunk on the run (constant + characters + characters², D-380), never uses that curve beyond the longest measured chunk (D-384), leaves the first 4 voice calls out (D-381) and starts after 1,000 measured characters (D-382); the JSON file keeps the characters and seconds of every spoken chunk (`chunk_times`). Estimate: the error of the time left the job showed against the real time left, (shown − real) / real; the first estimate, the first at 25, 50 and 75 % of the characters, and the median and largest error over every estimate with 10 s or more to go (D-284).

| Machine | Device | Paper | Whole job | Preparation | Voice load | Speaking | Encoding | Audio | Real-time factor (speaking) | Estimate | Date | Commit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| macOS 26.6.2, Mac16,1, Apple M4, 10 cores, 16 GB | mps, torch 2.15.0 | acl2023-hardt-ellipsis (9 pages, 19,167 characters) | 181.28 s | 1.28 s | 2.0 s | 167.75 s (116.4 characters per second) | 10.3 s | 1550.7 s | 9.24 | first at 6% done: +24%; at 25/50/75 %: +15%/+13%/+15%; median 15%, largest 24% | 2026-11-14 | 87ba1f59d51b |
| macOS 26.6.2, Mac16,1, Apple M4, 10 cores, 16 GB | cpu, torch 2.15.0 | acl2023-hardt-ellipsis (9 pages, 19,167 characters) | 173.17 s | 0.46 s | 1.2 s | 161.3 s (119.0 characters per second) | 10.2 s | 1550.7 s | 9.61 | first at 6% done: +5%; at 25/50/75 %: +3%/-1%/-3%; median 2%, largest 8% | 2026-11-14 | 87ba1f59d51b |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | acl2023-hardt-ellipsis (9 pages, 19,167 characters) | 379.97 s | 0.69 s | 1.5 s | 352.92 s (54.3 characters per second) | 24.9 s | 1548.9 s | 4.39 | first at 4% done: -11%; at 25/50/75 %: -9%/-11%/-9%; median 9%, largest 11% | 2026-11-13 | 79db1fcb7ded |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | joss2022-biggs-pymedphys (4 pages, 5,133 characters) | 123.02 s | 0.44 s | 1.6 s | 114.26 s (45.0 characters per second) | 6.7 s | 386.75 s | 3.38 | first at 22% done: +32%; at 25/50/75 %: +28%/+7%/-3%; median 8%, largest 35% | 2026-11-13 | 79db1fcb7ded |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | acl2023-hardt-ellipsis (9 pages, 19,167 characters) | 434.74 s | 0.98 s | 1.5 s | 404.44 s (47.4 characters per second) | 27.9 s | 1548.9 s | 3.83 | first at 6% done: -20%; at 25/50/75 %: -14%/-6%/+5%; median 5%, largest 20% | 2026-11-13 | 48c5b7dd722b + #136 |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | joss2022-biggs-pymedphys (4 pages, 5,126 characters) | 140.06 s | 0.85 s | 1.7 s | 130.16 s (40.0 characters per second) | 7.3 s | 386.62 s | 2.97 | first at 26% done: +23%; at 25/50/75 %: +23%/+10%/+3%; median 10%, largest 24% | 2026-11-13 | 48c5b7dd722b + #136 |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | joss2022-biggs-pymedphys (4 pages, 5,126 characters) | 118.15 s | 0.87 s | 1.8 s | 108.84 s (47.7 characters per second) | 6.6 s | 386.62 s | 3.55 | first at 26% done: +3%; at 25/50/75 %: +3%/-4%/-9%; median 4%, largest 9% | 2026-11-13 | 48c5b7dd722b + #136 |
| Linux 6.18.44-fc-v445, Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, 15.7 GB | cpu, torch 2.15.0+cpu | joss2022-biggs-pymedphys (4 pages, 5,126 characters) | 124.94 s | 0.72 s | 1.6 s | 115.12 s (44.7 characters per second) | 7.5 s | 386.62 s | 3.36 | first at 26% done: +4%; at 25/50/75 %: +4%/-7%/-13%; median 4%, largest 13% | 2026-11-13 | 48c5b7dd722b + #136 |

Budget on this container: preparation, real time and encoding met on both papers (encoding 62 and 57 times real time). The estimate is met on hardt (largest error 11 %) but **not on the short pymedphys paper**: its first estimates say up to 35 % too long (51 % in an earlier run of the same script), and they settle only after half the paper. Followed up in Issue [#136](https://github.com/dubidu22/sci2audio/issues/136).

After #136 (the four rows marked "+ #136"): the estimate meets the budget in every run on both papers. pymedphys: largest error with a minute or more left 24 %, 3 % and 4 % in three runs, against 22 %, 23 % and 48 % in three runs of the old estimate in between on the same container. Run-to-run noise here is as large as the effect, so the change was also judged by replaying both estimates on the same recorded chunk times: pymedphys 46 → 24 %, 25 → 3 %, 26 → 4 %, 39 → 21 %, 32 → 12 %, 27 → 7 %; hardt 14 → 6 %. The cap of D-384 changes none of these numbers (the measured stretch already has long chunks); it matters when a first chapter measures only short chunks, where the curve alone could be off by up to almost twice the real time. In the hardt run above, the container slowed down during the run (57.8 characters per second in the first eighth, 43 to 47 later), which no estimate measured on the run can foresee; the old estimate replayed on the same chunk times gives the same 20 %. What is left on pymedphys is its front matter (names and affiliations speak about 30 % slower than body text of the same length); leaving the first chapter out of the measurement is Issue [#178](https://github.com/dubidu22/sci2audio/issues/178), to revisit after the M4 run.

## Voice engine (VA-02, D-48: PyTorch)

| Machine | Device | Characters per second | Install size | Notes |
|---|---|---|---|---|
| MacBook Pro M4 (Mac16,1, 10 cores, 16 GB), 2026-11-14 | Apple GPU (MPS) and CPU, torch 2.15.0 | MPS 100.8, CPU 135.2 (the voice alone); 116.4 and 119.0 in the audio job | | `PYTORCH_ENABLE_MPS_FALLBACK=1`; kokoro 0.9.4, voice `af_heart`; speed script rows above. The app picks MPS by itself; on this machine the CPU is as fast or slightly faster, and MPS has a 16.6 s model load against 1.5 s |
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

## Audio job: a paper to its audiobook with the real voice (#71)

`SCI2AUDIO_TEST_MODELS=<voice folder> uv run pytest tests/integration/test_audio_job.py -m benchmark --benchmark-only -p no:xdist`:
the 4-page pymedphys paper (default chapters: 41 utterances, 5,800 characters) from file to
4 MP3s, one M4B and the read-along file with Kokoro `af_heart` at speed 1, network blocked.
The timed rounds are reruns from the chunk cache, so they measure the job's own overhead
(reading, layout, text steps, planning, encoding); the whole first run is in the extra info.

| Machine | Whole job (first run) | Speech only | Rerun from the cache (mean of 3) | Audio | Date |
|---|---|---|---|---|---|
| Linux cloud container, 4 vCPU (Intel(R) Xeon(R) Processor @ 2.10GHz), torch 2.15.0+cpu | 134.6 s, 43.1 characters per second | 47.6 characters per second (model warm-up not counted) | 6.98 s (6.90 to 7.07 s): 6.4 s of it is ffmpeg encoding 7.5 minutes of speech twice (MP3s and M4B), 0.55 s reading and layout | 449.9 s (about 3.3 × real time) | 2026-11-13 |
