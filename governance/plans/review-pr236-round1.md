# Review of PR #236, round 1 (#219 language guessing)

Head 32e720b on main 3715c38 (up to date). Critical (core Document fields, report goldens, new corpus samples).
Plan: plans/issue219-language-guess-plan.md, decisions D-494 to D-500 (KB pending batch lines 120-128).

**Verdict: changes requested (small).** The design matches the plan; six fixes before merge, one item deferred (#237).

## Checked and fine

- **Core (D-494)**: `LanguageSource` (StrEnum) and `LanguageGuess` (frozen) in core, exported; `Document.language_source` / `language_guess` default `None`, so every existing constructor call is valid and `to_data` leaves them out (export golden unchanged; test asserts it). `from_data` of an older `document.json` loads. `__post_init__`: TEXT needs a guess equal to the primary subtag, FALLBACK needs "en", guess counts non-negative and german+english <= words, guess language in ("", "en", "de"). Core strategies draw all valid combinations, so the existing round-trip property covers the new fields.
- **Layer contract**: lint-imports passes; `layout/language.py` imports only core and layout. No other contract change.
- **Whole text (D-495)**: `guess_language` loops over every line of every page; no first-N cut.
- **Thresholds (D-495)**: `language_words = 20`, `language_ratio = 3.0`. Probed: 15 German + 5 English (20 words, exactly 3:1) → "de"; 14+5 (19) → ""; 15+6 → "". Matches D-495. Lists disjoint, words common to both left out (test). Upper case ("ÜBER", "FÜR") counted.
- **Precedence (D-496)**: setting wins and the text is not looked at (guess None); file wins unless it names en/de and the text clearly is the other; region kept when the text agrees ("de-AT"); "fr" never overruled; unsure text never overrules. Override tested both ways (de over "en-US", en over "de-DE").
- **Samples (D-497)**: both German samples read as own text, German versions of the CC0 English samples, no third-party text; LICENSES.md rows CC0-1.0, #219. Truth files, extraction and tagged-layout goldens added only (no line removed from existing snapshots).
- **CLI (D-498)**: only `language_warning` (fallback, override) on stderr, for `script` and `audio`.
- **Web (D-499)**: note in English and German string tables, in a `<p class="hint" id="text-language">` that is part of the voice select's `aria-describedby`, so a screen reader announces it with the voice choice; no note for reports made before v1.1. Browser suite incl. axe: 50 passed locally.
- **Report (D-500)**: two keys after `language`, version stays 1.
- **Byte identity**: `sci2audio script` on all 10 English corpus files, main 3715c38 vs PR: every listening script identical; reports differ only in the language line and the two new keys (7 PDFs + plain text "guessed from the text", EPUB and Markdown "en-GB, as the file states"). Report goldens (hardt, waskom) change only by those keys and the line.
- **Speed**: 1.4 million words in 0.62 s.
- **Local runs**: ruff, format, lint-imports, deptry, fast suite 3,646 passed 1 skipped; browser 50 passed. CI on 32e720b green (CI passed still running at review time).

## Fix list (round 1)

1. **Pin the D-495 boundaries in tests.** Hand mutants `>= language_words` → `>` and `german >= ratio * english` → `>` both survive `test_layout_language.py` + `test_core_objects.py`. Add exact cases with the default settings: 15 German + 5 English common words → "de"; 14 + 5 (19 words) → ""; 15 + 6 → ""; and the English mirror (5 + 15 → "en", 6 + 15 → "").
2. **Order-independence property (plan section 6).** Add the Hypothesis property that the guess does not depend on the order of lines and pages (e.g. the same `Content` with its pages reversed, or its lines shuffled, gives an equal `LanguageGuess`).
3. **CLI tests for D-498.** No test asserts that the language warnings reach stderr (the edited assertion in `test_cli_script.py` now checks only "UTF-8"). Add: a short untagged text prints the fallback warning once; a Markdown file with `lang: en` and German prose prints the override warning; a clearly English untagged text prints no language warning.
4. **Stale user-facing text.** `cli.py` `--language` help says "(default: the file's own)"; make it say the file's own, else guessed from the text (en or de). `app/settings.py:26` comment says `"" = the file's own, else "en"`; update it the same way. Update the CLI help golden.
5. **Override warning hint.** The fallback warning names the command-line option, the override warning does not. Make it end like the fallback: "To read it as en, set the language to en (on the command line: --language en)." Update its test.
6. **PR body**: it says the web line sits "above the voice choice"; it sits below the select with the other hints (fine, and it is in `aria-describedby`). Correct the sentence.

## Deferred

- #237 (v1.1): stated tags are passed through as written, so `en_US` escapes the D-496 override (primary split on "-" gives `en_us`) and `und`/`zxx`/`mul` block the guess. Same on main; belongs in extraction.
