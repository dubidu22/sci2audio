# #211 German voice: research, choice and plan

Thread "Add a German reading voice", 13 Nov 2026. Lane: voices (extraction slot). Critical (new download, licences, voice routing in the app; risk:high), so this plan waits for the coordinator's approval. Colin (D-455): "search for the best german option and just pick it then".

## 1. Choice

**Pick: Kokoro-82M German fine-tune by Thorsten-Voice** (`Thorsten-Voice/Kokoro`, default checkpoint = epoch 5, pinned revision `734e593d320a3d876bede7020f773dfd481a0cc7`), one male voice, id `dm_thorsten`.

**Runner-up: Piper `de_DE-thorsten-high`** (same speaker's data, older VITS model).

Why:
- Best clean result in the measured comparison below: the fewest recognition errors of the licence-clean candidates (WER 1.8 % with Whisper large-v3-turbo, 1.2 % with Whisper small), against 3.0 % / 7.3 % for Piper thorsten-high.
- Licence chain fully clear: weights Apache-2.0 (published by Thorsten Müller, the speaker, on his own Thorsten-Voice account), training data the Thorsten-Voice dataset (CC0), base model Kokoro-82M (Apache-2.0, already accepted in #18).
- Same stack as the English voice: kokoro 0.9.4 + misaki 0.9.4 + espeak-ng (espeakng-loader, already shipped and recorded for Q12). **No new Python dependency**, same 24 kHz output, same speed control.
- Fast enough: 86 characters per second on 4 cloud vCPUs (about 4.5x faster than real time), model loads in under 1 s after the first load.
- Size: 328 MB download (one weights file + one 0.5 MB voice pack + the 2 KB config).

## 2. Measured comparison (13 Nov 2026, cloud container, 4 vCPU, CPU torch, 12 German sentences I wrote, 1,321 characters, already in spoken form)

| Candidate | Model licence | Training data | WER (turbo / small) | chars/s | Real-time factor | Download | Verdict |
|---|---|---|---|---|---|---|---|
| **Kokoro Thorsten (ep5)** | Apache-2.0 | Thorsten-Voice, CC0 | **1.8 % / 1.2 %** | 86 | 0.22 | 328 MB | **pick** |
| Piper de_DE-thorsten-high | MIT (voices repo); engine piper-tts GPL-3.0 | Thorsten-Voice, CC0 | 3.0 % / 7.3 % | 131 | 0.15 | 114 MB | runner-up |
| Piper de_DE-kerstin-medium | as above | Kerstin, CC0 | 3.0 % / – | 616 | 0.03 | 63 MB | lower quality |
| Pocket TTS German (Kyutai), voice "juergen" | weights CC-BY-4.0, code MIT | **not documented** for German; "juergen" voice source not documented | 0.6 % / – | 45 | 0.44 | 219 MB | refused: licence gate |
| Pocket TTS German 24-layer | as above | as above | 0.6 % / – | 14 | **1.52** (slower than real time) | 672 MB | refused |
| kikiri German Martin / Victoria (Kokoro) | Apache-2.0 | speaker marked "synthetic", base trained on "51speakers-synthetic" data whose generator is not stated | not run | – | – | – | refused: unclear rights |

Not run, refused on licence or fit: XTTS-v2 (Coqui Public Model Licence, non-commercial), F5-TTS German and Meta MMS (CC-BY-NC weights), Piper pavoque (CC BY-NC-SA), Orpheus German (Llama licence, 3B, GPU), Chatterbox Multilingual (MIT, but 0.5B parameters, slow on CPU, built-in watermark).

Errors heard by Whisper (turbo) for the two Thorsten voices: Kokoro "Phonomen an Kongrenzen" (Korngrenzen), "weikom" (Vakuum); Piper "der Schichten" (dünner), "Kongrenzen", "eröffentlicht", "Schichtdieke", "Bruggenstruktur". Pocket's lowest WER is real, but it is a generative (autoregressive) model that can skip or repeat words, and its German data and voice have no stated source, so it fails `.claude/rules/licences.md` ("voices trained on data with unclear rights"). Worth re-checking if Kyutai documents them.

Listening samples (same 12 sentences): `/mnt/project-files/samples/german-voice/` (kokoro_thorsten.mp3, piper_de_DE-thorsten-high.mp3, piper_de_DE-kerstin-medium.mp3, pocket_german_juergen.mp3). Bake-off scripts: `/mnt/project-files/plans/issue211-bakeoff/`. A neural MOS predictor (UTMOS) could not be run here (its code loads from GitHub via torch.hub, blocked), so naturalness rests on the model class (StyleTTS2 vs VITS), the error types above and Colin's listening test.

## 3. Pitfalls found while measuring (the PR handles each)

1. **Silent weight drop.** The Thorsten weights use PyTorch's new weight-norm key names (`parametrizations.weight.original0/1`); kokoro 0.9.4 expects `weight_g/weight_v`, fails the strict load and falls back to `strict=False`, which silently skips the decoder's weights. Result: noise (Whisper heard nothing; first measurement). Fix: rename the keys in memory at load, then verify that every weight of the model was loaded except the AdaIN `norm.weight/bias` pairs, which this checkpoint does not contain (kokoro's fallback leaves them at 1 and 0, as the German kokoro fork does). Anything else missing raises `ModelLoadError`. The downloaded file stays byte-identical (checksum).
2. **Out-of-vocabulary phoneme.** espeak-ng German writes `ʏ` (short ü, "Brücke"), which is not in Kokoro's 178 symbols; kokoro drops unknown symbols silently. Map `ʏ → y` (the substitution the model's training data used). Brackets `[ ] { }` are the only other unknown symbols I found and carry no sound; they are dropped. A test asserts that no German letter sequence produces an unknown symbol.
3. **No chunking for espeak languages.** kokoro's pipeline does not split espeak-language text and asserts at 510 phonemes. German text gives about 1.05 phonemes per character, so a 300-character utterance (textprep's limit) fits, but the voice still splits longer input itself: at sentence punctuation, then at commas, then at spaces, each part at most 510 phonemes.
4. **No misaki or kokoro fork.** The Thorsten model card asks for git forks of misaki and kokoro. They are not needed: the fork only adds a language code and a `DEG2P` that calls the same `EspeakG2P(language="de")` that upstream misaki 0.9.4 already has. Forks from git cannot ship on PyPI.
5. **No hidden text rewriting.** The fork's `DEG2P` also rewrites numbers, dates, currencies and abbreviations before phonemizing. That would change the text silently (D-57); those rules belong to textprep as marked edits (#130, #113). Until they land, espeak-ng reads digits in German by itself ("3,5" → "drei Komma fünf").

## 4. How it plugs in

No change to the voice contract (`Engine`, `EngineSession`, value objects) or to `sci2audio.core`.

**voices/download.py: voice packs.** Every `RemoteFile` gets a `pack` ("en" or "de"). `download_plan(languages=None)`, `missing_files(models_dir, languages=None)` and `download_voice_files(models_dir, languages=None, ...)` take the packs to cover (None = all). The German pack: `kokoro-82m-de-thorsten/<revision>/config.json`, `model.pth` (327,231,582 bytes, sha256 36dde15c…59ce), `voices/thorsten.pt` (523,450 bytes, sha256 9d98b775…06d7), from `huggingface.co/Thorsten-Voice/Kokoro/resolve/<revision>/`, licence text shown on the consent screen. The English pack is unchanged (same targets, so existing installs stay valid).

**voices/kokoro_german.py (new).** `GermanPipeline`: same call shape as kokoro's `KPipeline` (`pipeline(text, voice=..., speed=..., split_pattern=None)` yielding segments with `.audio`, `.graphemes`, empty tokens), built from its own `KModel` (weights loaded and verified as in 3.1) and `EspeakG2P("de")`; pure helpers `to_kokoro_phonemes()` (3.2) and `split_phonemes()` (3.3).

**voices/kokoro_engine.py.** `GERMAN_VOICES = (VoiceInfo("dm_thorsten", "Thorsten", "de-DE", "male"),)`, `VOICES = ENGLISH_VOICES + GERMAN_VOICES`. `KokoroEngine` lists both and routes a voice to its language's pipeline (`"d"` → German pipeline, made on first use, with its own model). `create_kokoro_engine` needs at least one installed pack; a voice whose pack is missing raises `ModelNotFoundError` naming the download for that language. English code paths stay as they are.

**app/voice.py and app/audio.py: the job's voice follows the job's language.** `VoiceSource` gains the language of each voice, a default voice per language (`en` → `af_heart`, `de` → `dm_thorsten`) and a version per voice. After the document is read: the chosen voice is used if it speaks the job's language (primary subtag); otherwise the job's language's default voice; for a language without a voice (e.g. French) everything stays as today. The audio record and report name the voice used. Before any speech the job checks that the voice's pack is installed and stops with "the German voice is not installed; download it first" otherwise. **English versions and chunk keys stay byte-identical**, so English caches and goldens do not change; German chunks carry `kokoro-de-thorsten@734e593d320a;kokoro 0.9.4;misaki 0.9.4;espeakng-loader 0.2.4`.

**CLI.** `voices` lists the German voice; `voices download [--language en|de]` (default: every missing pack), the consent text grouped by pack. `--language de` on a job already exists and now picks the German voice.

**Web.** `/api/voices` lists the German voice and adds `installed_languages`; the plan covers every missing pack (existing consent screen and digest; `installed` stays "all packs"). The voice page shows the German voice (strings in en.toml and de.toml); the German preview sentence is German. The job-language override in the web is #212's.

## 5. Text normalisation needed from textprep (not in this PR)

The voice reads what it gets; espeak-ng covers plain German words and digits. Textprep's German rules decide the rest as marked edits: #130 numbers, dates and statistics (ordinals "3." → "dritte", decimal comma, years), #113 abbreviations, symbols and units ("z. B.", "%", "°C", Greek letters, which espeak-de otherwise spells or drops), #101 links and citations, #96 line-end hyphens, #212 notices. Known weak spot to feed those rules: English technical terms inside German text get German pronunciation; a pronunciation-override list (the Apache-2.0 `de_overrides.json` of semidark/misaki) is a follow-up after Colin's listening test.

## 6. Tests

Fast suite (every PR, three systems):
- Download packs: plan contents, sizes, licences and targets per pack; filter by language; German-only download with a fake fetch; existing fault-injection cases (no network, disk full, folder removed, wrong checksum, interrupted resume) parametrised over both packs.
- Weight loading: key renaming and the completeness check on small fake checkpoints; a checkpoint missing decoder weights raises `ModelLoadError` (the bug in 3.1).
- Phonemes: `to_kokoro_phonemes` maps `ʏ` and drops only the listed symbols; real espeak-ng (espeakng-loader is installed in CI) on a German word list with all umlauts, ß and loanwords yields only vocabulary symbols; Hypothesis: `split_phonemes` never makes a part over 510 and loses no symbol, on any text.
- Engine with fake pipelines: voice list, routing en/de, missing German pack → `ModelNotFoundError`, and `check_voice_engine` (conformance) passes with the German voice included.
- App: voice-resolution table (en doc / de doc / fr doc × no voice / English voice / German voice), German pack missing → clear `JobError` before speech, English chunk key unchanged (pinned value).
- CLI and API: voices list, `voices download --language de`, `/api/voices` (Schemathesis picks up the schema).
- Browser: the voice page lists Thorsten, axe-core passes.

Nightly (`slow`, real model, network blocked): German sentence → WAV (24 kHz mono, not silence), conformance suite, speech-recognition round trip on my own German sentences with the nightly's Whisper small (measured 1.2 %, limit 10 % as for English). `benchmark`: German characters per second, row in `docs/baseline.md`. `prepare_models.py` also fetches the German pack.

Golden files: none change (English output and chunk keys stay identical). Licence rows in `THIRD_PARTY_LICENSES.md`: Thorsten-Voice/Kokoro weights (Apache-2.0) and their training data (Thorsten-Voice dataset, CC0).

Rough size: about 500 lines of code and 700 of tests, one PR.

## 7. Decisions for the coordinator (recommendation first)

- **Q1 Voice:** Kokoro Thorsten (epoch 5) as the German voice; Piper thorsten-high as the named runner-up; Pocket TTS refused until Kyutai documents its German data and voice.
- **Q2 Download:** per-language packs; the default download covers every missing pack; English installs stay valid; jobs need only their own pack.
- **Q3 Voice by language:** the chosen voice if it speaks the job's language, else that language's default; languages without a voice behave as today.
- **Q4 No text rewriting in the voice:** no `DEG2P` normalisation; numbers etc. come from textprep (#130, #113); until then espeak-ng reads digits.
- **Q5 Cache versions per voice:** English version strings unchanged; German has its own.
- **Q6 Follow-up issue:** "guess English or German when the file states no language" (layout lane). Many LaTeX PDFs carry no language tag, so today a German paper without one is read as English unless the user sets the language. Recommend v1.1, since it decides whether Colin's German PDFs get the German voice without a manual step.
- **Q7 Follow-up issue:** German pronunciation overrides for English technical terms (after Colin's listening test, v1.1 or v1.2).
