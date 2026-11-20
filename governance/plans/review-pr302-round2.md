# Review PR #302, round 2 (issue #295, letter pace)

Reviewed head 55b0462 (b0e668c + 55b0462 on top of round 1's 8b656df). Fix list: https://github.com/dubidu22/sci2audio/pull/302#issuecomment-6879554003

## Verdict: approved, merge by squash when CI is green on 55b0462

## Round 1 findings

1. Whisper round trip at each pace: FIXED. `test_speech_recognition_round_trip_at_each_pace` (slow), five abbreviation-dense sentences per language at Normal / Slower / Slowest, reuses `at_16_khz` and `edit_distance` from test_voice_kokoro.py, WER per pace recorded with `record_property`, limit 0.20 on the worst pace. The higher limit than the prose round trip's 0.10 is justified in the comment by measurements (whisper slips on names: LSDM, RMSC, BART). `heard_words` joins dotted/dashed letters on both sides; a fast test pins it. PR body Whisper line corrected.
2. Strict speed on jobs and preview: FIXED. `"speed": true` and `"speed": "0.8"` are 422 cases in test_web_jobs.py and test_web_preview_files.py.

## Runs here (real models, whisper small)

- Changed fast tests: 56 passed.
- `-m slow tests/integration/test_voice_letter_pace.py`: 7 passed. WER English normal 0.019, slower 0.096, slowest 0.135; German 0.000, 0.021, 0.021. Limit 0.20 leaves about three words of margin for English at Slowest; it is nightly-only and records each pace, so a drift shows before it fails.

## For Colin's listening (not a finding)

At Slower, whisper heard "use CNNs" as "U-C-N-Ns" (the word "use" sounds like the letter U next to slow letters) and "BERT" as "BART". Worth a listen in the v1.0.1 test.
