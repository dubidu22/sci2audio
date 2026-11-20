# Plan: issue #295, let listeners set how fast spelled abbreviations are spoken

Thread "Let listeners set abbreviation speed", 14 Nov 2026. From Colin's v1.0.0 listening test
("abbreviations like BERT are spoken too fast; let the user decide"). Milestone v1.0.1. Lane
voices, with the setting plumbed through app, web and cli. Main at 1d4fb56.

**Critical: yes.** It adds an optional parameter to the voice plugin contract and changes three
golden files (section 5). No change to core dataclasses, the layer contract, the text-step
interface or any textprep rule; the script text stays as it is. Label `risk:high`. No new
dependency. **The plan waits for the coordinator's approval; no code or tests before that.**

## 1. Measured (details and tables in #295)

- Textprep leaves "BERT", "NLP", "LSTM", "FKZ" as printed; the voice spells them. misaki
  (English) and espeak-ng (German) say an unknown all-capitals word as one word, letters run
  together with only secondary stresses. German says "BERT" as the word "Bert".
- Default voices at speed 1.0: English spells **5.8 to 7.0 letters/s**, while the same voice
  says ordinary syllables at 4.9/s, so letters come 20 to 40 % faster than normal speech.
  German spells 4.3 to 5.1 letters/s against 4.8 syllables/s.
- Rewriting the text ("B E R T", "B. E. R. T.", "B, E, R, T", semicolons, dashes, ellipses)
  is no usable control: in English spaces and dots are hardly slower (LSTM 6.8, NLP 7.1),
  commas give 4.0 to 5.0 depending on the word, with list intonation; a lone "A" becomes the
  article; dots would end sentences for the cutter; and the script would no longer show the
  text as printed.
- Slowing only the spelled letters' sounds works evenly (prototype in the cloud container):
  Kokoro predicts a duration for every sound and divides it by the speed; passing a factor
  per sound slows the letters and leaves the rest of the sentence as it was.

| Factor | English letters/s (BERT, LSTM, NLP, FKZ) | German letters/s (NLP, LSTM, FKZ, GPU) |
|---|---|---|
| 1.0 (today) | 6.9, 6.8, 6.8, 5.8 | 4.4, 5.1, 4.3, 5.0 |
| 0.7 | 4.7, 4.7, 4.8, 4.2 | 3.3, 3.7, 3.1, 3.7 |
| 0.5 | 3.5, 3.5, 3.3, 2.9 | 2.4, 2.7, 2.3, 2.7 |

Whole sentence "We fine-tune BERT and an LSTM for NLP tasks on one GPU.": 4.9 s today,
6.1 s at 0.7, 7.6 s at 0.5. Whisper small transcribes every factor the same as today.
Samples to listen to: `/mnt/project-files/samples/abbreviation-pace/` (en and de at 1.0, 0.7
and 0.5).

## 2. Decisions to approve

**Q1. Mechanism: the voice slows only the sounds of spelled letters.** Not a textprep rewrite
(section 1). The voice already knows which words it spells, the script stays as printed
(D-57), and the rate is even across words. Rejected: comma or dot forms in textprep (uneven,
changes script and cutter), splitting the utterance and speaking the abbreviation alone at a
lower speed (breaks the sentence's melody, extra chunks).

**Q2. Three paces, named for the listener:** Normal = factor 1.0 (today), Slower = 0.7,
Slowest = 0.5. Slower brings English letters to about the voice's ordinary syllable rate
(4.2 to 4.8/s); Slowest is clearly deliberate (2.9 to 3.5/s). The factor multiplies with the
voice speed (a book at speed 0.8 and Slower speaks letters at 0.8 × 0.7).

**Q3. Default stays Normal.** At Normal the audio is byte-identical to today and every cached
chunk stays valid. Alternative: make Slower the default, since English letters are measurably
fast; I recommend Normal because Colin asked for a choice, not a new default, and Normal keeps
every v1.0 book unchanged. The default can move later with one line.

**Q4. What counts as a spelled abbreviation (per voice language):**
- English: a misaki token of two or more capital letters, maybe with a plural "s" ("GPUs"),
  whose phonemes are misaki's own letter spelling of it (`lexicon.get_NNP`). Words misaki says
  as words are left alone.
- German: a word of two or more capital letters (any upper-case letter, so "ÖPNV" counts)
  whose espeak-ng phonemes equal those of its letters said one by one. "BERT" ("Bert") is left
  alone. Its phonemes are found in the sentence's phonemes in order; if they are not found
  (espeak joined it with a neighbour), that word keeps today's pace. Detection never fails a
  chunk.
- Mixed case ("RoBERTa", "CoNLL"), single letters and dotted forms ("i.i.d.") are not slowed
  in this issue.

**Q5. Voice contract: one optional synthesis parameter `letter_speed`** (number, 0.25 to 1.0,
default 1.0): "the speed factor of letters the voice spells out; an engine that cannot do this
ignores it". Documented in `voices/types.py` and `engine.py`; `API_VERSION` stays "1.0"
(additive, optional). Kokoro rejects values outside the range with `InvalidInputError`, like
`speed`. The conformance suite checks that 1.0 gives the same audio as no parameter and that
bad values are rejected for engines that declare it.

**Q6. Kokoro implementation.** At 1.0, or when an utterance has no spelled word, the code path
is today's, untouched. Otherwise:
- English: the session runs kokoro's own steps itself (`g2p`, `en_tokenize`, `infer`,
  `join_timestamps`, about 20 lines), passing a per-sound speed tensor in place of the number,
  so token timings for the read-along stay right.
- German: `GermanPipeline` passes the same tensor per phoneme part.
- This relies on `KModel.forward_with_tokens` dividing the predicted durations by `speed`
  (kokoro 0.9.4, pinned below 0.10). A fast test with a stand-in model checks the tensor's
  shape and values; the slow nightly test checks real letters really slow down, so a kokoro
  update that breaks it shows up the same night.

**Q7. App setting `letter_pace`** in `JobSettings`: "normal", "slower" or "slowest" (names,
not numbers; the app maps them to 1.0, 0.7, 0.5). Saved in the settings file (`KEPT`); an old
file without it reads Normal, an unknown value gives a warning like other bad values. Recorded
in the report's and the job record's settings. The chunk key gets `letter_speed` only when it
is not 1.0, so Normal keys stay identical and `KEY_FORMAT` is not bumped. Changing the pace
speaks the book again (the app cannot know which utterances the voice spells in).

**Q8. CLI:** `--letter-pace {normal,slower,slowest}` beside `--speed`, for one run, on top of
the saved settings like `--speed`.

**Q9. Web:** under the speed slider, a radio group "Spelled-out abbreviations" (Normal,
Slower, Slowest) with the hint "For abbreviations the voice reads letter by letter, such as
NLP." (German: "Buchstabierte Abkürzungen": Normal, Langsamer, Am langsamsten). Saved with the
settings, sent with each job, and used by the voice preview, so typing "BERT" into the preview
sentence lets the listener hear the pace. API: `letter_pace` in `SettingsModel`,
`JobSettingsIn` and `PreviewIn` (an enum in the OpenAPI schema).

## 3. Script and report

The script does not change (no text step changes). The report and `audio.json` list
`letter_pace` in the settings, so a listener can see which pace a book was made with.

## 4. Tests (written first)

- Voices, fast: detection per language on fake G2P output (spelled, said as a word, plural,
  mixed case, not found in the sentence); speed tensor built right; 1.0 takes today's path
  (stand-in pipeline records the call); bad `letter_speed` values rejected; conformance suite
  run against Kokoro with a stand-in model.
- Voices, slow (nightly, real models): English and German sentences at each pace; spelled
  letters slow by the measured amounts (within a tolerance), the sentence without
  abbreviations is byte-identical at every pace, Whisper round trip unchanged.
- App: settings round trip and old file without the key; chunk key unchanged at Normal and
  different at Slower; record and report settings; audio job passes the factor to the voice.
- CLI: flag parsed, bad value a usage error, help text.
- Web: TestClient for settings, job and preview with the new field; Schemathesis picks it up
  from the schema; browser test: keyboard and axe-core on the radio group, the choice saved and
  sent with the preview.
- Regression case in `english.toml`: none needed (script unchanged); one added case would only
  pin "BERT" as printed, which line 711 already does.

## 5. Golden files that change (snapshot diffs explained in the PR)

- `tests/unit/__snapshots__/test_app_corpus.ambr`: the settings block gains
  `'letter_pace': 'normal'` (three places).
- `tests/unit/__snapshots__/test_app_audio_job.ambr`: the same in the audio record's settings.
- `tests/unit/__snapshots__/test_cli_golden.ambr`: the help text gains `--letter-pace`.

No script, layout, extraction or textprep golden file changes.

## 6. Shape and size

One PR, `voices: let listeners slow spelled abbreviations (#295)`, branch
`voices/issue295-letter-pace`: voices (engine, German pipeline, contract docs), testing
(conformance), app (settings, config, chunks, audio, job), cli, web (models, api, pages,
template, app.js, strings). About 400 lines of code and 500 of tests. It does not split well:
the parameter alone is unused and the setting alone does nothing. App and web are
single-threaded lanes: the code-blocks thread's #286 (web view) and the release-day PR touch
nearby files, so I merge main in as they land.

## 7. Out of scope (separate issues if wanted)

- English "BERT" said as the word "Bert", as researchers say it (a list of acronyms said as
  words). I can file it for v1.2.
- Pauses around abbreviations; slowing numbers, symbols or mixed-case names.
