# Abbreviations, prosody and sync: architecture and phasing

Proposal for Colin, 14 Nov 2026; approved the same day (see below). Design only: no code, no KB entries, no issues. Written against
`main` at 1f6b4ba (after PR #300 and PR #302). Every number marked "measured" was produced in this
thread on the eight corpus papers (`tests/corpus/papers/*.pdf`) or with the voices' own
pronunciation front ends (misaki 0.9.4 for English, espeak-ng through misaki for German).

**Decided by Colin, 14 Nov 2026 16:37 UTC** ("all 6 recommendations approved"), with two
changes to the proposal below, already worked into this file:

- **The list of meanings is kept entirely by the person.** sci2audio ships no universal list,
  no field-standard list and makes no suggestions. An abbreviation the paper does not explain
  and the person's list does not hold is taken as well known in its context and read as
  printed.
- **Local LLMs (never cloud) are a future idea, maybe v2.** Nothing is designed for them now.

So the three tiers become two sources of a meaning: **the paper** (its own "Phrase (ABBR)") and
**the person's list**. Everything else is read as printed.

Contents: 1 summary · 2 where we stand · 3 where the "no restrictions" assumption holds ·
4 the one rule that shapes everything · 5 data model and sync · 6 pre-processing vs player ·
7 rules, with the German answer · 8 settings · 9 roadmap · 10 decisions for Colin ·
11 existing decisions touched.

---

## 1. Summary

- **Most of the spec fits the pipeline we already have.** A text step proposes one `replace`
  edit per abbreviation use ("MLP" → "Multi-Layer Perceptron"); the edit keeps pointing at the
  printed "MLP", so the reader and the highlight stay on the printed word while the voice says
  the phrase. This needs no change to the script, the read-along file or the chunk cache.
- **The audio is baked.** Everything the listener *hears* (expansion, n-use decay, scopes,
  bridge phrase, pauses, pronunciation) must be decided before the voice speaks, because the
  M4B and MP3s carry one rendering and play in other apps too. Only what the listener *sees*
  (glossary panel, tooltips, "show full phrase") is decided in the player. Rewind-to-expand is
  the one heard feature that can live in the player, and only with pre-rendered alternates.
- **The assumption "pre-processing can reliably detect and expand abbreviations" holds for
  abbreviations the paper defines itself, and not beyond that** without a word list or an LLM.
  Measured: in the eight corpus papers, 24% of abbreviation uses belong to terms the paper
  defines as "Full Phrase (ABBR)"; the other 76% (BERT, GPT, NLP, API, DSGVO, BGH, ...) are
  never written out in the paper.
- **Today's highlight is per sentence, not per word.** The voice's word timings exist for
  English but are thrown away; the German voice has none. Word-level read-along is its own
  feature and is not needed for the abbreviation sync to be right.
- **Phasing (approved):** feature MVP = terms the paper defines, n-use decay per chapter or
  audiobook, the author's own "(MLP)" framed with a bridge phrase, English inflection, a
  read-only glossary and tooltips, folded together with #296. Then overrides, export, the
  person's own list of meanings and the reader toggle. Word-level read-along, rewind-to-expand
  and earcons last; local LLMs a future idea for maybe v2. Slot: a themed release of its own right after v1.2, before the public
  plugin interface freezes the text-step contract (section 9).

---

## 2. Where we stand today

**What already exists**

| Piece | Where | What it does |
|---|---|---|
| `abbreviations` step | `textprep/abbreviations.py`, `data/en/abbreviations.toml` (209 lines), `data/de/abbreviations.toml` (419 lines) | Reads dotted abbreviations in full ("e.g." → "for example", "Fig. 2" → "figure 2", German "z. B." → "zum Beispiel"). Category "Abbreviations". **It does not touch acronyms** (all-caps words like MLP). |
| Letter pace | `voices/letters.py`, `JobSettings.letter_pace` (PR #302, D-554) | Slows only the sounds of letters the voice spells ("NLP"), Normal 1.0 / Slower 0.7 / Slowest 0.5. This is Colin's "abbreviation speed", already shipped. Dotted forms ("M.L.P."), mixed case and letters with digits are not slowed. |
| #296 (v1.2) | issue | "English acronyms said as words (BERT as Bert)": a list of acronyms researchers say as words. |
| Edits and script | `core/edits.py` (D-57, D-61) | Steps propose `replace`/`remove`/`pause`/`ask` edits on spans; `apply_edits` turns them into `ScriptPiece`s, each pointing at the original span it stands for. A `move` kind is being added for #213 (PR #307). |
| Utterances and chunks | `textprep/utterances.py` (D-98), `app/chunks.py` (D-155) | The script is cut into sentence-sized utterances; each becomes one audio chunk, cached under SHA-256 of text + voice + speed + engine (+ letter speed when not 1.0). The span is not in the key. |
| Read-along | `output/readalong.py` (D-102), player (D-294 to D-303) | One entry per chunk: start, end, block, start_char, end_char. The player highlights **the sentence** being read (D-300) and plays the per-chapter MP3s (D-296). |
| Word timings | `voices/kokoro_engine.py` | Kokoro's English pipeline returns per-token times (`TokenTiming`), the engine passes them on in `AudioSegment.tokens`, and **the app never reads them**. The German pipeline returns none (`kokoro_german.py`: "no word timings"). |
| Switches | `textprep/steps.py` `Category` | Twelve fixed categories, each one switch in the UI and one section in the report. |

**Measured on the corpus** (eight papers, text that is read: no reference list, no furniture;
the counter is a heuristic, so a few hits are not abbreviations, e.g. "VI", "MH17", "CC BY-NC"):

| | Value |
|---|---|
| Distinct all-caps terms / uses | 139 / 527 |
| Terms defined in the paper as "Full Phrase (ABBR)" | 18 (PLUE, NLP, NLU, MLM, NER, VPE, PCFG, CNF, TLS, HSTS, DNS, AGI, OHE, OAM, TMD, QA, DTA, ...) |
| Uses belonging to those terms | 129 (24%) |
| Terms used before their definition | 2 (PLUE in the title and abstract, MLM) |
| Plural forms ("PLMs", "PCFGs", "TMDs", "URLs") | about 39 uses (7%) |
| Hyphen compounds ("OAM-...") | 9 uses |
| Most-used terms never defined | BERT 27, PP 22, PLMs 16, CKY 8, GPT 9, API 5 (English); DSGVO 15, OLG 13, BGH 8, GG 8 (German paper) |
| Spoken utterances (default chapters) / with a later short use of a defined term | 2,232 / 162 (7.3%) |
| Edits any current step makes on a "(ABBR)" bracket | none |

**Measured voice readings** (phonemes from the voices' own front ends):

| Printed | English voice (misaki) | German voice (espeak-ng) |
|---|---|---|
| MLP | spelled "em el pee" | spelled |
| NASA | word "nasa" | word |
| WEIRD, SMART, AIM | **words** "weird", "smart", "aim" | WEIRD as a word |
| SAP | word "sap" | (not measured) |
| FICO | spelled | (not measured) |
| BERT | spelled | **word "Bert"** |
| USA, IT, DNA, PDF, CNN, ANOVA | spelled | |
| DSGVO, BGH | | spelled |
| ROIs / ROI's | spelled + "z", both the same | |
| fMRI-based | "ef em ar eye based" | fMRT-basierte: spelled + word |
| W.E.I.R.D. / S.A.P. | **spelled** | |
| Fico | word "fico" | |
| LEGAL, ONE (as in PLOS ONE) | words | |

So the voice already decides "letters or word" from its dictionary. Respelling in the text
steers it both ways (dots force letters, title case forces a word), but a dotted respelling
falls outside today's letter-pace detection.

---

## 3. Where "detect and expand without restrictions" holds

| Capability | Holds with local rules? | Why / measured |
|---|---|---|
| Find the paper's own definitions "Full Phrase (ABBR)" | **Yes** | The initial letters of the words before the bracket match the bracket. The published Schwartz–Hearst method reports 96% precision and 82% recall on a biomedical test set; to be measured on our corpus truth before the MVP is approved. Also "ABBR (Full Phrase)" and German hyphenated phrases ("Transport-Layer-Security (TLS)", seen in the corpus). |
| Expand a defined term everywhere in the paper, also before its definition | **Yes** | The step sees the whole document, so the title and abstract can use a definition from page 2. |
| Expand a term the paper never defines (76% of uses) | **Only from a list** | No rule can invent "Bidirectional Encoder Representations from Transformers". Many such terms are names nobody expands (BERT, GPT, CKY). A curated list is needed, and with it the field problem: CNN is a network in one paper and a broadcaster in another. |
| Three tiers (Universal / Field-standard / Paper-specific) | **Replaced (Colin, 14 Nov)**: meanings come only from the paper or the person's own list; anything else is taken as well known. Original finding: **partly** | Paper-specific = "defined in this paper": exact. Universal and field-standard = membership in two curated lists per language. Telling which field a paper is in is not reliable with rules; a list without fields works for most terms. |
| English plural, possessive, hyphen compound | **Yes, with a small exception list** | Plural goes on the head noun: "ROIs" → "regions of interest", "MLPs" → "multi-layer perceptrons". Possessive "MLP's" → "multi-layer perceptron's". "fMRI-based" → "functional magnetic resonance imaging based" (the voice reads it fine, measured). **Also the article**: "an MLP" must become "a multi-layer perceptron", so the edit has to cover the article before the term. |
| German inflection | **No, not in general** | Case and adjective endings change: "des BGH" → "des Bundesgerichtshof**s**", "der KI" → "der Künstlich**en** Intelligenz". Safe only where nothing changes: a long form without an adjective and not after a genitive article. Section 7 has the rule. |
| Letters or word ("read_as_word") | **Yes for the voice's own choice; a list for exceptions** | The voice already picks (table above). Phonotactic rules would disagree with it (FICO is spelled, NASA is a word). Better: keep the voice's choice and add a "said as" list (#296) plus per-term overrides. |
| Homonym guard (WEIRD, SMART, AIM) | **Only for terms with a known meaning** | The English voice says them as words today (measured). But most all-caps real words in the corpus are not acronyms: "LEGAL" in a title, "PLOS ONE", "CC BY-NC". Spelling every all-caps word would make those worse. Guard only terms the glossary knows. |
| Synthesize the extra segments | **Yes** | The voice is local; the chunk cache makes repeats free. |
| Word-level sync | **Not today** | Sentence-level highlight only. English times exist but are dropped; German would need times from Kokoro's predicted sound lengths (the same numbers #295 already scales; not measured). |
| An LLM pass | **New dependency, Colin's call** | Would help with undefined terms, field guessing and German inflection. It conflicts with D-51 (rule-based first, no AI rewriting) and, if remote, with the local-only promise; a local model is a large download, slow on a laptop (not measured) and not deterministic, so golden files cannot pin its output. Section 10, decision 3. |

---

## 4. The one rule that shapes everything: heard is baked, seen is live

The audiobook leaves sci2audio as an M4B and MP3s that play in Apple Books or any other app. One
rendering goes into those files. So:

- **Decided once, in the script job, before the voice speaks:** everything the listener hears.
- **Decided live, in the player:** everything the listener sees, plus rewind-to-expand, which
  works only in sci2audio's own player and only because both versions were spoken beforehand.

Changing a heard setting means running the script job again and speaking only the utterances
whose text changed: the chunk cache keys on text, so every other chunk is reused. Measured upper
bound: switching n-use decay on or off changes about 7% of utterances.

---

## 5. Data model and sync

### 5.1 What the layers own

| Piece | Layer | Stored in |
|---|---|---|
| Finding definitions, uses, forms; inflection; the bridge phrase | textprep (new step `acronyms`) | edits in the run, as today |
| The glossary (terms, long forms, where defined, every use) | textprep (pure function `build_glossary(document, context)`) | **new `glossary.json`** in the working folder, written by the script job |
| Which uses are said in full (n-use, scopes) | textprep function called by the app after the chapter choice (5.4) | statuses in the run → report |
| Settings | app (`JobSettings.abbreviations`), passed to steps in `StepContext` | `job.json`, `audio.json` (as all settings today) |
| Audio of each utterance | voices, app chunk cache | unchanged |
| Read-along | output | unchanged in the MVP; version 2 with word times later (5.6) |
| Glossary panel, tooltips, "show full phrase", rewind | web player | reads `glossary.json` |

The document (`document.json`) does not change: layout decides nothing about meaning (D-63).

### 5.2 The edits (no core change)

For "We train a Multi-Layer Perceptron (MLP). The MLP has ... Two MLPs ...":

| Span (printed) | Edit | Said |
|---|---|---|
| " (MLP)" (with the space before it) | replace | ", abbreviated as MLP," (bridge from settings; the voice spells MLP at the letter pace) |
| "MLP" (2nd use) | replace, or left as printed by the decay pass | "multi-layer perceptron" / "MLP" |
| "MLPs" | replace | "multi-layer perceptrons" |
| "an MLP" | replace over the article too | "a multi-layer perceptron" |

The script pieces come out as today:

```json
[
  {"text": "We train a Multi-Layer Perceptron", "span": {"block": 12, "start": 0, "end": 33}},
  {"text": ", abbreviated as MLP,", "span": {"block": 12, "start": 33, "end": 39}},
  {"text": ". The ", "span": {"block": 12, "start": 39, "end": 45}},
  {"text": "multi-layer perceptron", "span": {"block": 12, "start": 45, "end": 48}}
]
```

The last piece is the phrase; its span is the printed "MLP". This is what keeps the sync right:
whatever the voice says for a replacement, read-along points at the printed characters.

### 5.3 `glossary.json` (new, owned by the app, versioned like `audio.json`)

```json
{
  "format": "sci2audio-glossary",
  "version": 1,
  "language": "en",
  "terms": [
    {
      "short": "MLP",
      "long": "multi-layer perceptron",
      "long_as_printed": "Multi-Layer Perceptron",
      "plural": "multi-layer perceptrons",
      "source": "paper",
      "tier": "paper",
      "defined_at": {"block": 12, "start": 11, "end": 39, "page": 2, "printed_page": "2"},
      "say": "voice",
      "uses": [
        {"block": 3,  "start": 10, "end": 13, "form": "MLP",   "chapter": 0, "heard": "full"},
        {"block": 12, "start": 34, "end": 39, "form": "(MLP)", "chapter": 1, "heard": "introduced"},
        {"block": 12, "start": 45, "end": 48, "form": "MLP",   "chapter": 1, "heard": "short"},
        {"block": 20, "start": 5,  "end": 9,  "form": "MLPs",  "chapter": 2, "heard": "full"}
      ]
    }
  ]
}
```

- `source`: `paper` (defined in the text) or `user` (the person's list or an override). There
  is no built-in list and no suggestion (Colin, 14 Nov).
- `say`: `voice` (the voice decides), `letters`, `word`.
- `heard`: `full`, `short`, `introduced`, `printed` (category switched off), `not_read` (chapter
  not chosen, reference list).

The player needs no other file for the glossary panel, tooltips, export and the "show full
phrase" toggle. Per-term overrides are user data per document, `glossary-overrides.json` in the
same working folder (feature v1.1); the person's own list for all papers is a rule file in the
app's config folder, as D-57 foresees for users ("rule files, no code"). sci2audio never fills
it in.

### 5.4 Where n-use decay is decided

The step cannot count uses as heard: it does not know which blocks other steps remove (the
reference list, footnote texts), which chapters are chosen, or where a note is read after #213
moves it. So:

1. The `acronyms` step proposes a full-phrase edit for **every** use of a known term, and the
   bridge edit at each definition.
2. The runner settles overlaps as today.
3. After the chapter choice, the app calls a textprep function
   `choose_expansions(run, chapters, settings)` that walks the accepted acronym edits in the
   order they are heard (using `StepRun.read_at` from #213), counts per scope, and marks the
   uses past n as a new status `kept-short`: the script reads them as printed. A written-out
   long form in the text counts as a hearing too, so "multi-layer perceptron" followed by "MLP"
   does not expand twice.

This keeps D-61's split (steps propose, the app chooses) and needs no new core field: the pass
finds each edit's term again from its printed text through the glossary. Alternative not
chosen: an `Edit.term` field in core (critical, and only a convenience).

Scopes: `audiobook`, `chapter` (the app's chapters, the same as the M4B's), `paragraph` (a
block), `words` (re-expand once when the term was not heard in the last N spoken words). A
time-based scope ("X minutes") is shown as words with an estimate, because the minutes depend
on the audio the expansions themselves change; the job already measures characters per second
(`audio.json`), which gives the estimate.

### 5.5 Chunks and caching

No change to `chunk_key` or `KEY_FORMAT`. The text decides the key, so:

- the same settings give the same keys (a test pins this);
- turning decay up or down re-speaks only the utterances whose text changed;
- an expanded and a short version of one sentence are two cache entries and both stay usable.

### 5.6 Word-level read-along (later; not needed for the abbreviation sync)

Read-along format version 2 adds words per chunk:

```json
{"chapter": 1, "start": 41.220, "end": 44.870, "block": 12, "start_char": 39, "end_char": 120,
 "words": [[41.220, 41.400, 39, 44], [41.400, 42.610, 45, 48], [42.610, 42.900, 49, 52]]}
```

Each word is `[start, end, start_char, end_char]`. Every spoken word of a replacement maps to
the replacement's span, so "multi-layer perceptron" (41.400 to 42.610) highlights the printed
"MLP" the whole time, which is exactly Colin's rule. English times come from the voice's token
times (dropped today); German needs times from Kokoro's predicted sound lengths. Readers refuse
versions they don't know, so version 2 is a clean break (D-102).

### 5.7 Rewind-to-expand (later)

The player plays per-chapter MP3s (D-296). For every utterance that holds a short-spoken term,
the audio job speaks an alternate with the term in full, and output writes all alternates into
one extra file, `<book>.alternates.mp3`, listed in `audio.json` (bare names only, D-295), with
their times in the read-along file. When the person goes back (previous sentence, or a new
"back 15 s" button) into such an utterance, the player plays the alternate from a second audio
element, then continues the chapter MP3 at the end of that utterance. Cost: at most about 7%
more speaking time (measured share of utterances). Live synthesis from the local server on each
rewind was considered: simpler files, but a cold voice takes seconds to load and the player
would depend on the server having the voice loaded.

### 5.8 Earcon (later)

A short tone where a phrase was expanded needs the time of the expansion inside a chunk, so it
follows word times. Output would mix it into the stream; the chunk WAVs stay as they are.

---

## 6. Pre-processing vs player

| Feature | When | Where |
|---|---|---|
| Find definitions and uses, glossary | script job | textprep |
| Where a meaning comes from (paper / person's list) | script job | textprep: definitions in the text + the person's list |
| Expansion, inflection, article | script job | textprep `acronyms` step |
| n-use decay and scopes | script job, after chapter choice | textprep function, called by app |
| Bridge phrase and its trigger | script job | in the replacement text |
| Pauses around abbreviations | script job | commas in the replacement (micro-pauses); real silences only at sentence ends |
| Letters or word, homonym guard | script job | textprep respelling from the list or override |
| Letter pace | audio job | voice (`letter_speed`, done) |
| Alternates for rewind | audio job | app + output |
| Glossary panel, export MD/CSV, print to PDF | player | web, from `glossary.json` |
| Tooltip on hover or tap | player | web |
| "Reader shows full phrase" | player | web: shows the expansion in place of the printed span |
| Highlight | player | unchanged per sentence; per word after read-along version 2 |
| Rewind-to-expand | player | plays a pre-rendered alternate |

A PDF cheat sheet uses the browser's print to PDF of the glossary page, so no PDF library joins
the dependencies.

---

## 7. Rules, with the German answer

| Rule | English | German |
|---|---|---|
| Never shorten | Long forms in the text are read as printed (true by design: steps only replace the short form). | Same. |
| Author's "Phrase (ABBR)" | The phrase as printed, then the bracket replaced by ", abbreviated as MLP,". "short for" only fits the other order ("MLP, short for multi-layer perceptron"), so it is offered for "ABBR (Phrase)" and for expansions on transition. | Default ", kurz MLP,"; "abgekürzt als" is stiff when spoken. Hyphenated phrases count ("Transport-Layer-Security (TLS)"). |
| Expansion of later uses | Head-noun plural, possessive, hyphen compounds, article "a/an" re-chosen. | Only where no ending changes: the long form has no leading adjective, and the term does not follow a genitive article (des, eines) or a preposition that takes the genitive. Otherwise the short form is said and the glossary still lists it. Plurals not expanded. |
| Not explained (Colin, 14 Nov) | Neither defined in the paper nor in the person's list: taken as well known, read as printed (DNA, BERT, API). | Same (DSGVO, BGH). |
| The person's list | Kept by the person only (feature v1.1); same n-use rules as paper terms. | Same. |
| Units ("km") | Already the units step's job; not acronyms. | Same. |
| Letters or word | The voice's choice; #296 list ("BERT" as Bert); override per term; dotted respelling forces letters (measured), so letter pace must learn dotted forms. | espeak already says BERT as Bert; list for the opposite direction. |
| Homonym guard | Terms in the glossary that the voice would say as an ordinary word (WEIRD, SMART, AIM) are spelled or expanded. Unknown all-caps words are left alone (LEGAL, ONE). | Same (WEIRD is a word in German too, measured). |

---

## 8. Settings

**Smart mode** (what everyone sees, on the document page next to today's switches and the
letter pace):

- **Explain abbreviations** (on/off, default on): "The voice says the full term the first time
  in each chapter and the short form after that. The text shows what is printed."
  This is a new category switch, "Acronyms" ("Akronyme"), so it turns off on its own without
  touching "e.g." → "for example" (category "Abbreviations").
- **Pace of spelled letters** (Normal / Slower / Slowest): exists.
- A line under the switch: "14 abbreviations found · Review" → opens the glossary panel.

Smart defaults: n = 1, scope = chapter, the author's definition counts as the first full use,
bridge phrase on the definition only, commas as micro-pauses, voice decides letters or word,
anything not explained read as printed, reader shows the printed text.

**More abbreviation settings** (collapsed):

| Setting | Values | Phase |
|---|---|---|
| Say the full term | first 1 to 5 times | MVP |
| ... counted per | audiobook / chapter | MVP |
| | paragraph / every N spoken words (shown with "about X minutes") | v1.1 |
| Name the short form | at the definition / each time the full term is said / when switching to the short form / never | v1.1 (MVP: at the definition) |
| Bridge phrase | text, default "abbreviated as" / "kurz" | v1.1 |
| Pause around abbreviations | none / short | v1.1 |
| Text shows | printed text / full terms | v1.1 |
| My abbreviation list (short form, meaning, say as) | kept by the person | v1.1 |
| Going back says terms in full | on/off | v2.0 |
| Tone when a term was expanded | on/off | v2.0 |

**Per term, in the glossary panel** (v1.1): meaning (editable), say in full: default / always /
never, say as: voice / letters / word. The MVP panel is read-only.

Every label in English and German (the strings tables), and the glossary panel must work with
the keyboard and a screen reader: sentences are not tab stops (D-298), so the tooltip's content
is reachable through the panel, not only by hovering.

---

## 9. Roadmap

### Phase 0: measure (part of the MVP plan, about a day)

Definition finding on the corpus against hand-made truth; the voices' readings for the lists;
how long a comma pause is; one listening sample per bridge phrase in both languages.

### Feature MVP: "Explain the paper's own abbreviations"

- New step `acronyms` (category "Acronyms"): definitions "Phrase (ABBR)" and "ABBR (Phrase)",
  uses, English inflection and article, German safe-case rule, bridge at the definition.
- `choose_expansions` with n and scope audiobook/chapter; status `kept-short` in the run and the
  report ("said as MLP: heard in full earlier in this chapter").
- `glossary.json`; #296's "said as a word" list (a pronunciation list, not meanings) and the
  homonym guard for glossary terms; letter pace for dotted forms.
- Player: read-only glossary panel, tooltip on hover/tap.
- Settings: the switch, n, scope.
- Tests: unit tests per rule (both languages); English and German regression cases first
  (they fail on main); a new truth section `[[abbreviation]]` in the corpus TOML files (golden,
  critical) and a corpus test against it; a chunk-key test (same settings, same keys; changing
  n changes only the utterances with that term); a Hypothesis property (every printed character
  read once, spans in order) over random documents with definitions; a browser test that the
  highlight stays on the sentence with the printed "MLP" while the phrase plays.
- Golden files that change: `test_app_corpus.ambr` (chi, hardt, nowak, maass, liu, pymedphys,
  arsiwalla; seaborn has no definitions), `test_app_audio_job.ambr`, `test_cli_golden.ambr`,
  the regression TOMLs.
- Size: about four PRs (step + lists; decay + report + record; web; #296 and the guard).

### Feature v1.1: "Make it yours"

Per-term overrides and the person's own list (kept only by the person); export MD/CSV and print
to PDF; "text shows full terms"; paragraph and word-count scopes; bridge phrase text and trigger
choices; pause choice. Tests: list file round trip and refusal of broken entries, overrides
round trip, export snapshots, player toggle browser test.

### Feature v2.0: "Listen closely"

Read-along version 2 with word times (English from the voice, German from sound lengths) and a
word highlight in the player; rewind-to-expand with pre-rendered alternates; the earcon.
Future idea, maybe v2 (Colin, 14 Nov): local LLMs, never cloud; nothing designed yet, and no
suggestions to the person's list.
Word times pair naturally with read-along on page images (#155).

### Mapped onto the releases

| Option | Feature MVP | Feature v1.1 | Feature v2.0 |
|---|---|---|---|
| **A (decided)**: own release after v1.2 | v1.3 "Abbreviations" (installers and plugin interface move to v1.4) | v1.4 or v1.5 | Later, with #155 |
| B: inside v1.2 | v1.2 (with #296) | v1.3 | Later |
| C: after the plugin interface | v1.4 | v1.5 | Later |

Why A: the MVP adds a category, settings fields in `StepContext` and a status, which are part of
the text-step contract; the public plugin interface (v1.3, D-459) should freeze after them, not
before. v1.2 already holds more than 30 open issues. C works too (StepContext takes new fields with
defaults), but a new category after the freeze is a contract change for plugin authors.

---

## 10. Decisions for Colin

**All six approved as recommended by Colin on 14 Nov 2026 16:37 UTC**, with decision 3 refined:
no LLM in the MVP or v1.1, local LLMs (never cloud) kept as a future idea for maybe v2, and no
suggestions of meanings at all; the list of meanings is the person's alone.

1. **Where the feature MVP goes.** Recommend A: its own release right after v1.2, before
   installers and the plugin interface.
2. **Expansion on by default.** Until now a step edits only where the voice reads wrong (D-176,
   D-227) and the text stays as printed (D-57). Saying "multi-layer perceptron" where the paper
   prints "MLP" goes further. Recommend: on by default, for terms the paper itself defines,
   first use per chapter; off with one switch.
3. **LLM.** Recommend no LLM in the MVP or v1.1 (D-51 stands); decide at v2.0 whether an opt-in
   local "suggest meanings" pass is worth a large download. Never a cloud model.
4. **German expansions.** Recommend only where no ending changes (section 7); the alternative is
   no German expansions at all in the MVP, only the definition framing.
5. **Rewind-to-expand only in sci2audio's player.** It cannot exist in Apple Books or other
   apps. Recommend v2.0 with pre-rendered alternates; drop it if you listen mostly elsewhere.
6. **Word-level highlight.** Not needed for this feature. Recommend it as part of v2.0 with
   #155 rather than earlier.

---

## 11. Existing decisions touched

D-51 (rule-based first): kept; LLM is decision 3. D-57 (text as printed, edits): kept, the
script is still the original plus marked edits; decision 2 widens what a step may change.
D-61 (spans, app chooses edits): the decay pass is the app choosing. D-63 (layout decides
nothing about meaning): kept, `document.json` unchanged. D-98 (utterance cutter): unchanged.
D-102, D-294 to D-303 (read-along and player): unchanged in the MVP; version 2 later. D-155
(chunk key): unchanged. D-165 (records): `glossary.json` joins `audio.json` and `document.json`.
D-176, D-227 (edit only where the voice reads wrong): widened by decision 2. D-229 (word lists
as TOML): the new lists follow it. D-295, D-296 (player files, per-chapter MP3): alternates follow
them. D-299 (no "said" field in read-along): kept; the player gets the expansions from
`glossary.json`. D-459 (plugin interface v1.3): ordering argument in section 9. D-554, D-555
(letter pace, #296): reused and folded in. #213 (move edits, `StepRun.read_at`): the decay pass
counts uses in the order they are heard.
