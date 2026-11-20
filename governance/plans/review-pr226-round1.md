# Review PR #226 round 1: German voice Kokoro Thorsten (#211)

Reviewed head 76fd74a (one commit on f1a334a), 14 Nov 2026 ~01:35 UTC. Plan: plans/issue211-german-voice-plan.md (D-467 to D-473). Critical (risk:high, lane:voices). Merge is ON HOLD on the coordinator's word (01:21Z) until the release/1.0 branch exists, even when green.

## Verdict

Changes requested: one real bug (F1) and two small fixes (F2, F3). Everything the coordinator listed as "points that matter" checks out.

## What I checked, and how

- **CI on 76fd74a:** every check green (tests on Linux, macOS, Windows; browser Chromium; lint and layers; licences; security; CodeQL; ZAP).
- **Locally:** ruff check, ruff format --check, lint-imports (3 contracts kept), deptry clean; fast suite **3291 passed, 1 skipped** (same count as the author).
- **Contract and core unchanged:** no diff in `voices/engine.py`, `voices/types.py`, `voices/errors.py`, `sci2audio.testing` or `sci2audio.core`. `VoiceSource` (app) gains optional fields with defaults, as the plan allows. `RemoteFile` gains `pack` with default "en".
- **English path unchanged:** `kokoro_version()` is untouched, English voices get `version_of() == version` (tested), the English pack's files and targets are identical. No golden file changes except the two CLI snapshots, and those diffs are exactly what the author says: help size 355 → 680 MB, the `--language {en,de}` option and its help, the German pack's line and "In total 682 MB" in the consent text.
- **Pinned download, checked against Hugging Face's API:** revision 734e593d… exists; `model.pth` 327,231,582 B, LFS sha256 36dde15c…59ce; `voices/thorsten.pt` 523,450 B, sha256 9d98b775…06d7; `config.json` 2,351 B, sha256 5abb01e2… (fetched and hashed; same bytes as the English config). All match the code. The download path verifies sha256 as for English (shared code).
- **Licence rows:** the model card at that revision says `license: apache-2.0`, `datasets: thorsten-voice`, and "Fine-tuned on the Thorsten-Voice dataset (CC0 / public domain)". The new THIRD_PARTY_LICENSES row and the extended espeakng-loader / phonemizer-fork rows are correct. kikiri-tts is credited on the card only for the training recipe, not data.
- **Completeness check is real (the plan-approval condition).** Mutations of `kokoro_german.py`, each run against `test_voices_german.py`:
  - `_rename` returns the name unchanged: 3 tests fail, including `test_the_german_loader_loads_every_weight`.
  - `_rename` disabled AND the missing/extra check in `convert_checkpoint` disabled: `test_the_german_loader_loads_every_weight` still fails, now through `check_loaded` ("weight predictor.F0.0.conv1.parametrizations.weight.original0 was not loaded"). So the value-by-value check catches kokoro's silent `strict=False` skip on its own.
  - `check_loaded` made a no-op: 1 test fails.
  - `_ABSENT_OK` widened to match every name: 1 test fails.
  - the `ʏ → y` mapping removed: 2 tests fail.
  The tiny-model fixture asserts the decoder really carries the new `parametrizations` names, so the test exercises the real bug.
- **Language-to-voice selection** is covered: a table of 11 cases (en, en-GB, de, de-AT, fr × no voice / English / German), a German document read by the German voice, a missing German pack stopping the job before any speech while English still works, and per-voice chunk versions.
- **espeak-ng robustness (my own probe):** 22 odd inputs through the real `EspeakG2P("de")` + `to_kokoro_phonemes` (Greek letters, Cyrillic, Chinese, emoji, ∞ ≤ →, sub/superscripts, €, %, °C, ©, URLs, Polish/Czech letters, English sentences): none raises; no unknown symbol appears.
- **Branch vs main:** behind main by PR #222 (9af111e); `git merge-tree` shows no conflicts. The review thread merges main into the branch before the merge.
- **Housekeeping done by me:** PR put into milestone v1.1 (2).

## Fix list for the author

**F1 (must fix): making a German audiobook in the web replaces the person's remembered English voice.**
`documentPage()` in `web/static/app.js` sends `voice: voice.value` in the `PUT /api/v1/settings` after Make (D-246). On a German document the page now preselects `dm_thorsten` (`_document_voice`), so after one German audiobook the saved voice is `dm_thorsten`. The next English document then gets `_document_voice("dm_thorsten", "en") == "af_heart"`, and a person who had chosen, say, `bm_george` silently loses that choice for every English book afterwards. The CLI is not affected (it saves nothing).
Wanted: a voice of another language never replaces the remembered voice. Rule: on Make, the saved voice becomes the page's voice only if the saved voice is empty or speaks the same primary language as the page's voice; otherwise the saved voice is kept (the job itself still uses the page's voice). An equivalent server-side rule is fine too. Test: a browser test (or a unit test of the rule plus a page test) where a saved `bm_george` survives an audiobook started on a German document, and a change from `bm_george` to `af_bella` on an English document is still remembered.

**F2: wrong feature ID.** `VA-08` is "Piper fallback with public-domain voices" in the KB feature list, not part of this PR. Remove it from the CHANGELOG line ("#211, VA-07, VA-08" → "#211, VA-07") and from the PR body's "Feature ID".

**F3: a German checksum case for the download.** Plan section 6 promised the fault-injection cases for both packs; only the interrupted-resume case covers the German pack. The download code is shared, so add just the case that guards the new pin: a German-pack file served with wrong bytes fails with `DownloadError` (wrong checksum) and leaves no partial file, in the `two_packs` setup.

## Accepted as is (no change asked)

- `to_kokoro_phonemes` raises on an unknown symbol instead of dropping it. Loud is right here (D-57 spirit), and the probe above found no input that triggers it.
- The job now checks the voice pack before speaking even when every chunk is cached, so a fully cached job with deleted voice files stops. The plan says so (section 4); it is clear and rare.
- A chosen German voice still reads a French document (no French default): this is the plan's "as today" rule (D-469).
- "English chunk key pinned" from plan section 6 is covered by `kokoro_version()` being untouched plus `version_of(english) == version`; no separate pin needed.
- Segments of a cut German utterance all carry the whole text as `graphemes`; nothing downstream reads segment graphemes.
