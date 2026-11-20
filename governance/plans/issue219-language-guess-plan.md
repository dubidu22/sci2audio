# Issue #219: guess English or German when the file states no language (plan)

Thread "Guess the document language for German PDFs", 14 Nov 2026, main 3715c38. Lane: layout.
**Critical** (core dataclass change, new corpus samples with truth files, changed report goldens), so
this plan waits for the coordinator's approval before any code or test.

## 0. Today

- `build_document` (layout/build.py:73) and `build_tagged` (layout/tagged.py:117) both set
  `language = settings.language or content.metadata.language or "en"`.
- `settings.language` is the job's setting (CLI `--language`, the config file); the web has no
  language control yet (that is #212).
- `document.language` already drives everything downstream: text steps (`StepContext.language`,
  the runner skips steps that don't speak it), the voice (`voice_for`, D-469), the report, the
  web page's `lang` attributes and its default voice (`_document_voice`). So once the guess becomes
  `document.language`, the German voice and the German rules follow with no further change (D-474).

## 1. Measured

Script in the thread's scratchpad: extract each file with the app's extractors, join every line's
text, lower-case, split into words (`[^\W\d_]+`), count the words in a German and an English list of
common function words (section 2). No dependency, no model.

English corpus (10 files) and 12 German arXiv PDFs (downloaded to the scratchpad for measuring only,
never committed):

| File | Lang tag in file | Words | German common | English common | German share |
|---|---|---:|---:|---:|---:|
| 7 English corpus PDFs | none (all 7) | 1,922–11,919 | 0–12 | 279–3,517 | 0.000–0.011 |
| wells-the-time-machine.epub | en-GB | 33,417 | 3 | 10,427 | 0.000 |
| sci2audio-sample-note.md | en-GB | 223 | 0 | 57 | 0.000 |
| sci2audio-sample-plain.txt | none | 159 | 0 | 39 | 0.000 |
| 8 German PDFs | none | 2,016–57,171 | 528–18,330 | 32–650 | 0.910–0.974 |
| 1202.5919, 2301.03455, 2512.04683 | de-DE / DE-DE / de-DE | 2,511–14,885 | | | 0.929–0.985 |
| **2209.02793 (German text)** | **en** (wrong tag) | 10,801 | 2,914 | 330 | 0.898 |

- Whole documents separate cleanly: English at most 1.1 % German, German at least 89.8 %.
- The first 300 words are a bad sample: 3 German papers open with an English abstract (2503.15495
  45:54, 2512.04683 19:60, 2209.02793 10:70). So the guess counts the **whole text**.
- In 100-word windows with at least 20 common words, every window judged against its document's
  language was right except 8, and all 8 really are English passages inside German papers (abstracts,
  an ACM copyright block, English reference titles). The lists don't misfire.
- 8 of 12 German PDFs carry no tag (the issue's case). Of the 4 that do, **one is tagged "en"** though
  its text is German (a template default). See Q3.
- Cost: 1–5 ms for a paper, 30 ms for a 179-page thesis (57,000 words), 13 ms for the EPUB.

## 2. Method

New module `layout/language.py`:

```python
def guess_language(content: Content) -> LanguageGuess
def choose_language(content: Content, settings: LayoutSettings) -> tuple[str, LanguageSource, LanguageGuess | None]
```

- Words: every text line of every page (the same text layout reads; furniture adds a few words and
  doesn't matter at these margins), lower-cased, split on anything that isn't a letter.
- Two disjoint frozensets of about 60 German and 50 English **function words** (articles,
  pronouns, conjunctions, prepositions, auxiliaries: der die das und ist nicht ein eine zu von mit
  sich auf für werden wird dass … / the of and to is are that for with this be by from which …).
  Words that are common in both languages are left out of both: in, an, so, was, will, also, man,
  hat, war, um, am, as. Kept in a dict by language so a later language adds one list.
- Decision: let `g` and `e` be the German and English counts.
  - `g + e < 20` → unsure (too little text: below about 70 words of running prose).
  - `g >= 3 * e` → "de"; `e >= 3 * g` → "en"; otherwise unsure (mixed).
  - The guess is a primary tag only ("de", "en"), never a region.
- Deterministic, offline, linear in the text, no new dependency. Settings: `language_words: int = 20`
  and `language_ratio: float = 3.0` in `LayoutSettings`, with the measurements above in comments.

## 3. Who wins (order)

1. The job's setting (`--language`, config file; later the web control of #212): always wins, no
   guess is made.
2. The language the file states (PDF `/Lang`, EPUB `dc:language`, Markdown front matter `lang`):
   wins, **except** under Q3 when it names English or German and the text is clearly the other one.
3. The guess from the text, when the file states nothing.
4. English, when the text does not tell (`unsure`), with a report warning (section 5).

## 4. Core change (critical)

In `core/document.py`, exported from `sci2audio.core`:

```python
class LanguageSource(StrEnum):
    SETTING = "setting"    # the person chose it
    FILE = "file"          # the file states it
    TEXT = "text"          # guessed from the text
    FALLBACK = "fallback"  # nothing stated and the text did not tell: English

@dataclass(frozen=True)
class LanguageGuess:
    language: str  # "en", "de", or "" when the text did not tell
    words: int     # words looked at
    german: int    # German common words among them
    english: int   # English common words among them

Document.language_source: LanguageSource | None = None  # None: not recorded (built by hand, older saved jobs)
Document.language_guess: LanguageGuess | None = None    # the text's evidence, whenever the text was looked at
```

Checks in `__post_init__`: counts not negative and `german + english <= words`; `language` of the
guess is "", "en" or "de"; `TEXT` needs a guess whose language is the document's primary subtag;
`FALLBACK` needs language "en". Defaults are left out of `to_data`, so saved documents and goldens
of hand-built documents don't change, and an older saved `document.json` still loads (same pattern
as `Source.encoding_guessed`, D-346).

Why in core and not recomputed by the app: the report, the CLI, the web page and the saved job all
need to know where the language came from; recomputing it in the app from the content and the
settings would duplicate the rule in two layers and could disagree with what layout did (the
alternative D-346 also turned down).

## 5. Report, command line, web

- **Report JSON** (format stays version 1, keys added): `"language_source"` and `"language_guess"`
  (`{"language", "words", "german", "english"}` or `null`) next to `"language"`.
- **Report Markdown**, the language line:
  - setting: `Language: de, chosen in the settings.`
  - file: `Language: en-GB, as the file states.`
  - text: `Language: de, guessed from the text (1,587 German and 43 English common words in 5,053).`
  - fallback: `Language: en; the text does not show whether it is English or German, so it is read as English.`
- **Report warnings** (shown in the web under "Notes" and printed by the CLI, like the encoding
  warning of D-346): for fallback, "sci2audio could not tell from the text whether it is English or
  German, so it is read in English. If it is German, set the language to German (--language de)."
  For Q3's override: "The file says its language is en, but its text is German, so it is read in
  German. To keep English, set the language to en."
- **Command line**: these two warnings on stderr, nothing else (a clear guess is in the report;
  printing it on every untagged English paper would be noise).
- **Web document page**: one line above the voice choice, in the page's language:
  "Language of the text: German (guessed from the text)" / "(as the file states)" / "(your setting)"
  / "English (could not tell from the text)". New keys in `strings/en.toml` and `strings/de.toml`
  (`check.language_*`). The page already picks the German default voice from the report's language
  (D-469). Changing the language in the web stays in #212.

## 6. Tests

- `tests/unit/test_layout_language.py`: German and English paragraphs (own sentences); short text
  (< 20 common words) and a half-and-half text → unsure → "en" + FALLBACK; setting beats file beats
  guess; Q3 override and its limits (only en↔de, only when clear, never against the setting; the
  file's region kept when the file agrees, e.g. "de-AT"); the exact counts on a fixed text.
- **Corpus, tag removed**: every English corpus file, with `metadata.language` set to "", is guessed
  "en" (all 10); the German samples of Q4, tag removed, are guessed "de".
- A generated German PDF without `/Lang` (`tests/unit/pdf_maker.py`) runs through the script job and
  comes out with language "de", the German voice chosen (`voice_for`) and the German steps run.
- Hypothesis (`core_strategies`): `guess_language` and `build_document` never fail on any `Content`;
  the guess never depends on line or page order of the same words (counts only); core property tests
  extended to the two new fields (round trip through `to_data`/`from_data`, the `__post_init__` checks).
- Web: TestClient check of the language line for each source in English and German; the browser test
  of the document page keeps its axe check.
- CLI: stderr warning for fallback.

## 7. Goldens

- **Unchanged (byte-identical):** every English listening script, every layout golden (header still
  `language en`), every extraction golden.
- **Changed, by intent:** `test_app_corpus` report goldens of the two papers it keeps (hardt, waskom):
  JSON gains `language_source: "text"` and the guess counts; Markdown's language line becomes
  "Language: en, guessed from the text (…)." Explained in the PR.
- **New (Q4):** the German samples' truth files, extraction and tagged-layout goldens, and their
  script golden.

## 8. Size and order

About 80 lines in layout, 40 in core, 50 in app/cli/web, 2 string tables, about 300 lines of tests,
2 new samples with truth files. One PR (as asked), `layout: guess English or German when the file
states no language (#219)`, label `risk:high`. Snapshot overlap with the German numbers PR (#130):
whichever merges second regenerates the German sample goldens.

## 9. Questions for the KB log (recommendation first)

- **Q1 Where the source and the evidence live.** Recommended: two optional core fields
  (`Document.language_source`, `Document.language_guess`) plus `LanguageSource` and `LanguageGuess`
  (section 4). Not chosen: no core change, the app recomputes the guess for the report (two places
  decide the same thing, as rejected in D-346).
- **Q2 Method and thresholds.** Recommended: counts of German and English function words over the
  whole text; German or English when one outnumbers the other at least 3 to 1 and there are at least
  20 such words; otherwise English with a warning. Not chosen: a language-ID library (fastText's
  lid.176 model is CC BY-SA 3.0; lingua/langdetect add a dependency and their answers can shift
  between versions, which breaks goldens); character n-grams (more code, no gain at these margins);
  the first N words only (English abstracts mislead it, section 1).
- **Q3 A file tag that contradicts its text.** Recommended: when the file states English or German
  and the text is clearly the other (the Q2 rule), read it in the text's language, with a report
  warning saying so; the person's setting still always wins. Not chosen: the file always wins
  (the issue's wording; 1 of the 4 tagged German PDFs measured would then be read by the English
  voice with English rules, and the web can't override until #212). This changes one acceptance
  criterion of #219 and so needs the coordinator's yes.
- **Q4 German test samples.** Recommended: add two samples written for sci2audio (CC0): a German
  Markdown note and a German plain-text note, German versions of the two English samples, with
  truth files; the Markdown note states `lang: de`, the plain text states nothing. Plus a generated
  untagged German PDF in the tests. File a separate v1.1 issue (layout lane) for a real German paper
  in the corpus: arXiv 1705.08889 (PrivacyScore, CC BY 4.0, 6 pages, 367 KB, no tag), which also
  shows that the alternating running heads of the LNI template ("2 Max Maass, …", "PrivacyScore 3")
  are read as paragraphs today. Not chosen: adding that paper here (its truth file and the running-
  head bug would double this PR); test strings only (the issue asks for corpus samples).
- **Q5 What the command line prints.** Recommended: only the two warnings (fallback, Q3 override);
  a clear guess is in the report. Not chosen: a line for every guess (noise on every untagged
  English paper).
- **Q6 Web.** Recommended: show the language and where it came from on the document page; the
  control to change it stays in #212. Not chosen: pulling the web control into this PR.
- **Q7 Report format.** Recommended: add the two keys and keep version 1 (only additions; readers
  ignore unknown keys). Not chosen: version 2.
