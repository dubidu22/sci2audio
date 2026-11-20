# Review PR #302, round 1 (issue #295, letter pace)

Reviewed head 8b656df (c83a7e7 plus main 34303e1 merged in). Plan: plans/issue295-letter-pace-plan.md (D-554). Fix outside the plan: strict `speed` (D-560).

## Verdict: changes requested (two test additions, no code change)

The code matches the plan Q1 to Q9. Two gaps in the tests.

## Checked and fine

- Q1/Q6 mechanism: `_english_letters_slowed` replays kokoro 0.9.4 `KPipeline.__call__` for English line by line (g2p, en_tokenize, 510-sound cut, `model(ps, pack[len-1], speed, return_output=True)`, `join_timestamps`); `KModel.forward_with_tokens` divides `duration` by `speed`, so a [1, n+2] tensor broadcasts. `per_sound` filters sounds by vocab exactly as `KModel.forward` does and pads both ends. German passes the tensor per phoneme part.
- Normal path untouched: at letter speed 1.0 the request has no `letter_speed` (`speak_to_wav`), the engine calls the pipeline as before, `chunk_key` adds `letter_speed` only off 1.0, `KEY_FORMAT` stays 1.
- Detection probed with real misaki: "NLP", "LSTM", "US", "UK", "OK", "GPUs", "CNNs" found with exact span offsets; "NASA's", "BERT's", "U.S.", "PhD", single letters, an all-capitals sentence ("IT IS A TEST OF THE SYSTEM.") left alone.
- Contract: `letter_speed` optional, documented in `voices/types.py`, `API_VERSION` "1.0", conformance suite checks 1.0 == absent, lower never shorter, bad values (0, 0.1, 1.5, -1, NaN, inf, "slow", True) refused, with three negative conformance cases. Plan deviation ("engines that declare it": no declare mechanism, every engine validates the range) is explained in the PR body and is right.
- App: `letter_pace` names in `JobSettings`, `KEPT`, settings file, report and `audio.json` settings; old file without the key reads Normal with no warning; bad value is one warning.
- CLI `--letter-pace` choices; web radio group with fieldset/legend/hint, German strings, sent with jobs, preview and remembered settings; enum in the three API models.
- D-560 strict speed: `true` and `"1.0"` are now 422, `1` and `0.8` still accepted (checked with pydantic directly). Note: strings like "1.5" were accepted before and are refused now; the page sends numbers, so nothing breaks.
- Golden diffs: exactly the three snapshot files, each line as the PR body says.

## Runs here

- ruff, format, lint-imports (3 kept), deptry: clean.
- Fast suite on c83a7e7: 4452 passed, 1 skipped.
- Real models in the container (voice files plus whisper small fetched): `-m slow` on test_voice_letter_pace.py, test_voice_kokoro.py, test_voice_kokoro_german.py: 15 passed, incl. both Whisper round trips at Normal.
- CI on 8b656df: all green (Linux, macOS, Windows, browser, ZAP, CodeQL).

## Findings

1. **Must fix: the Whisper round trip at the slower paces is missing.** Plan section 4 lists "Whisper round trip unchanged" for the slow letter-pace tests; `test_voice_letter_pace.py` has none, and the existing round trips run only at Normal. Measured here with whisper small (two runs; Kokoro audio is not bit-deterministic):
   - German "Wir nutzen NLP und ein LSTM auf der GPU.": same at 1.0, 0.7, 0.5.
   - English "We fine-tune BERT and an LSTM for NLP tasks on one GPU.": "BERT" at 1.0, "BART" at 0.7 and 0.5 (both runs); "on 1GPU" once at 0.5.
   - English "The US and the UK use CNNs and GPUs.": one run heard "U.C.N.N.s" at 0.7 and "you CNNs" at 0.5, the other run "use" at 0.7.
   So an exact-equality test would be flaky. Add a round trip that reuses `test_voice_kokoro.py`'s WER measure (words, edit_distance, same WER_LIMIT) at Slower and Slowest over a few sentences with spelled abbreviations per language, and record the WER per pace (`record_property`) so a drop shows in the nightly. Also correct the PR body line "Whisper small transcribed the prototype sentences the same at every pace": with this branch that is not true for "BERT".
2. **Should fix: D-560 strict speed is tested only on PUT /settings.** `JobSettingsIn.speed` and `PreviewIn.speed` became strict too; add `"speed": true` (422) cases for POST /jobs and POST /voices/preview.

## For Colin's listening (not a finding)

English spelled "BERT" at Slower is heard as "BART" by whisper small. Worth a listen in the v1.0.1 test with the samples in samples/abbreviation-pace/.
