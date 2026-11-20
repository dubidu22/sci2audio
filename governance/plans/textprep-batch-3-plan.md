# Textprep batch 3: #494, #488, #477, #487

Status: **APPROVED as D-743 (18 Nov 13:24Z) with additions A1 to A4 (§6); #477 ruling D-744.**
Author: textprep lane thread "Build the v1.2 textprep fixes", 18 Nov 2026. Base: main 96de4a3.
Read first: CLAUDE.md, rules 1.4.4 + state, KB main 2d21ce0, decisions D-712..D-741,
`480-joined-sentence-plan.md` (part B), `sentence-boundary-plan.md`,
`audit-sentence-boundary-batch-2026-11-17.md` (S1, S2, N2), the four issues and their comments.
Measured on a scratch worktree (no branch, nothing pushed): the full fast suite with
`DEFAULT_MAX_CHARS = 400` (19 failures, listed in §1).

## 0. Criticality and PR split

Every part touches regression cases, so the whole batch is critical (CRIT-01; the
sentence-boundary batch set the same precedent: "regression cases" made all its PRs critical):

| PR | issues | why critical | touches |
|---|---|---|---|
| **PR 1** | #494 | changes `utterances` of 5 existing regression rows, 2 corpus snapshots (`test_app_corpus.ambr`); risk:high | `textprep/utterances.py` (one constant + docstring) |
| **PR 2** | #488, #477 | adds regression rows, edits `tests/sentences/known-errors.toml` and adds one line to the truth file `tests/sentences/stress-de.txt` | `textprep/utterances.py` (sentence ends), maybe `data/en/sentence_openers.toml` (new) |
| **PR 3** | #487 | changes `expected` of 2 existing regression rows (D-726 ruling: they pin the wrong reading) | `textprep/placeholders.py`, the skip checks of 7 inline steps |

I recommend **three PRs, not two**: #487 is placeholder reading, #488/#477 are sentence ends. The
last audit's lesson was to fold follow-ups together only when they share a model (PR 5 of the
sentence batch mixed placeholder work into sentence work and took three rounds). PR 2 and PR 1
both edit `utterances.py` but in different functions (`_sentences` vs the limit), so they do not
conflict beyond the TOML files.

Order: PR 1 first (as asked). PR 3 is written while PR 1 is in review (different files); PR 2
after PR 1 merges, from the new main. One PR in review at a time, one review thread for the batch
(Opus high, since all are critical). Each: Linux CI green, then my own `ci:full` green, label
removed, then review. Merge main into the branch, never rebase.

## 1. PR 1, #494: cut sentences only past 400 characters

Acceptance (from the issue): 300 to 400 characters is one utterance, longer still cut by the
#481 rules; slow real-voice test that a 400-character English and German sentence is one
segment; cut-rule regression rows updated with before/after diff; second-run idempotency holds;
PR says cached chunks of 300 to 400 characters are spoken again once.

**P1.1** `DEFAULT_MAX_CHARS = 400` in `textprep/utterances.py`; the comment names #494 and the
measured margin (German worst 1.16 phoneme tokens per character, 464 of 510). Module docstring
unchanged otherwise (it names no number).

**P1.2** Regression rows (tests first: rows changed before the constant). The 5 rows that
fail at 400 today, measured:
- `long-sentence-colon-beyond-the-limit` and `de-long-sentence-colon-beyond-the-limit` (about
  455 characters): still cut at the colon, now 2 pieces instead of 3 (the ", which" / ", dass" cut
  is no longer needed). `utterances` updated; goal reworded from "beyond the first 300
  characters" to "beyond the limit". The colon rule stays covered.
- `long-sentence-comma-before-a-conjunction`, `de-long-sentence-comma-before-a-conjunction`,
  `long-sentence-without-a-clause-mark` (310 to 360 characters): become one utterance. They
  are kept and their goals now say what they prove: a sentence of 300 to 400 characters is one
  utterance (#494, acceptance 1).
- **P1.3** New twin rows over 400 characters so the cut rules keep their coverage at the new
  limit: `long-sentence-comma-before-a-conjunction-over-the-limit` (en, de) and
  `long-sentence-without-a-clause-mark-over-the-limit` (en). Own wording, no third-party text.
  The goal of each states the rule, not the limit's value.
  No regression-format change (I considered a per-row `max_chars` key and rejected it: rows
  would then pin a reading no user hears).

**P1.4** Unit tests in `test_textprep_utterances.py` that size their sentences for 300 and so
fail at 400 (8: `test_parts_keep_about_the_same_length`,
`test_a_semicolon_that_leaves_a_clipped_last_part_is_not_taken`,
`test_three_parts_share_the_whole_sentence_evenly`, 5 cases of
`test_a_long_sentence_is_cut_outside_brackets_and_quotes`): they test the cut ranking, not the
default, so they pass `max_chars=300` through the existing `cut()` helper. Test-harness change:
none (the helper already takes it). New unit tests: a 399/400/401-character sentence at the
default (one, one, two utterances), and `continues` on the second piece of the 401 one.

**P1.5** Two app tests (`test_app_audio_job.py`) fail at 400:
`test_progress_goes_through_the_phases_and_estimates_after_the_first_chapter` (20.15 vs 20)
and `test_the_estimate_fits_a_cost_per_call_per_character_and_per_square`. Cause checked in
`app/estimate.py`: the estimate never extends the fitted curve beyond the longest chunk measured
so far (D-384), and with 400 a chunk longer than any measured one is still to come in the
PyMedPhys fixture. That is the designed behaviour, not a bug. Both tests are about the cost
model, so they pass `max_chars=300` to `run_audio_job` (already a parameter). The one-line
docstring of `app/estimate.py` ("300 characters by default") becomes "`DEFAULT_MAX_CHARS`
characters": an app-lane file, comment only; I name it in the PR. If the coordinator prefers
zero app-file edits, I leave the docstring and file a one-line issue.

**P1.6** Corpus snapshots: `test_app_corpus.ambr` changes for 2 of its papers:
arxiv2017-maass-privacyscore (German) 9 fewer utterances (sections "1 Einleitung" 21 → 20,
"6 Rechtliche Fragestellungen" 141 → 133), joss2021-waskom-seaborn 3 fewer ("Statement of
need" 12 → 11, "Overview" 44 → 42).
Accepted with `--snapshot-update`; the PR lists every joined pair (12). No other snapshot moves.

**P1.7** Slow tests with the real voices (`tests/integration/test_voice_kokoro.py`,
`test_voice_kokoro_german.py`): a 400-character English and German sentence (own wording,
ordinary prose) is synthesized and comes back as exactly one segment. Plus a measurement, run
once by me with the real g2p and written into the PR (not a test): phoneme tokens of every
300 to 400-character utterance of the corpus scripts, and how many would pass 510. Known limit
to state: digits are expanded by the voice ("2019" is about 20 phonemes), so a number-dense
400-character sentence can still pass 510; then Kokoro splits it itself at punctuation, as it
does today for any over-long text. No text is lost. If the measurement finds such utterances in
the corpus, I report the count and propose (not implement) a follow-up issue.

**P1.8** Second run: regression `read_twice`, the property tests and the corpus second-run check
run unchanged. Grace periods and toggles (lesson from #480 C2): I re-read, without changing,
the player's sentence-step and Focus code for anything sized by utterance length (a back-step
grace window, the reading mark across a `continues` cut). Any finding goes to the web lane as
an issue; PR 1 does not touch `web/`.

**P1.9** PR body: cached chunks of sentences between 300 and 400 characters (and of the pieces
of longer sentences whose cut moves) are spoken again once on the next build; nothing else in
the cache changes.

Size: about 40 lines of code and tests, plus the TOML and snapshot diffs.

## 2. PR 2, #488 + #477: sentence ends

### #488: German "et al."
**P2.1** Tests first: German regression rows for the three shapes of the issue
(`Wie Müller et al. (2019) Bildung verstehen, ist bekannt.` one utterance;
`Laut Müller et al. Kapitel 2 gilt das.` one; `Müller et al. (2019) zeigen das.` one) and for
`… et al. (2019). Die Studie …` (cut stays: the D-719 removed-text rule). A line in
`tests/sentences/stress-de.txt` with its truth (truth file: critical, named in the PR).
**P2.2** Add `"al."` to the German extras in `_german_abbreviations()` (beside `"e."`, `"az."`),
with a comment. Same reading as English: "et al." ends no sentence unless the removed citation
after it ended one. I considered "ends before a sentence opener" ("et al. Die Studie") and
rejected it: English does not do it, and "Die" after "et al." is as often a title word.

### #477: limits kept on purpose
Acceptance: each row either fixed by a rule that keeps every regression case and the sentence
gate green, or closed as a deliberate limit with its known-errors entry pointing at the
decision; no word list that only matches the test sentence.

**P2.3** Rows 1 and 2 ("the U.S. | Census Bureau" FP, "called A. | Then" FN): one general rule,
the English twin of the German ordinal rule (#227, D-530). An English sentence-opener list
(`data/en/sentence_openers.toml`: articles, pronouns, sentence adverbs and conjunctions only,
never a noun, same format and check as the German one) and:
- a single capital initial ("A.") ends the sentence before a word of that list;
- a dotted capital abbreviation of two or more letters (pattern `(?:[A-Z]\.){2,}`: "U.S.",
  "U.K.", "J.R.R.") ends it only before a word of that list ("in the U.S. The data" cut,
  "U.S. Census" not, "J.R.R. Tolkien" not). Today it always ends there.
Trade-off named: "in the U.S. Researchers found" loses its cut (FN) where today it is right.
**Gate:** adopted only if the sentence sets show no new error and the natural-set floors hold,
every regression row stays, and the corpus snapshots do not move (or every move is a fix I
list). Otherwise I drop the part that fails, and that row is closed as a limit (P2.5).
**P2.4** Row 3 (lower-case starts "seaborn.", "iOS"): closed as a deliberate limit. Allowing a
lower-case start cuts after every abbreviation the lists lack ("approx. five"); an
inner-capital rule ("iOS", "mRNA") would only move the problem.
**P2.5** Row 4 (German "Es waren 3. | Studien"): closed as a deliberate limit (D-530 documents
it; a noun list is ruled out there).
**P2.6** known-errors.toml: entries fixed by P2.3 are removed (the ratchet requires it); the
kept ones' `why` points at the decision number the coordinator gives (one D-number for the
#477 ruling). Issue #477's N2 comment (WBGU) stays as a recorded limit with the same pointer.
Regression rows for P2.3 (en): "set A. Then", "the U.S. The data", "the U.S. Census Bureau",
"J. Smith", "J.R.R. Tolkien", "Vitamin A. The" (cut), each with `utterances`.

Size: about 60 lines of code, a new 40-word list, rows.

## 3. PR 3, #487: a table or figure with its notice off is read as a paragraph is

Ruling D-726 (option 1): read the printed text of a notice-off table or figure through the same
textprep path as a paragraph; formulas and code stay as printed; correct the two rows.

**P3.1** Tests first: rows `hidden-runs-in-a-table-read-when-its-notice-is-off` (en: `expected`
unchanged, "Group Mean 4.2" reads the same) and `de-hidden-runs-in-a-table-read-when-its-
notice-is-off` (`Gruppe Mittel 4,2` → `Gruppe Mittel 4 Komma 2`); goals reworded to what they
pin. New rows, en and de, the probe of the issue: a table and a figure with "Tables and figures"
off read like the same text as a paragraph (`Anteil 3 Komma 5 Prozent bei 12 Quadratmeter.`,
citations removed, "e.g." spelled out); the same blocks with the notice on are unchanged
(notice only); a formula and a code block with their notices off stay as printed.
**P3.2** One predicate in `textprep/placeholders.py`, next to `notice_read`:
`read_as_prose(block, context)`: True for any block that is not furniture and not a
placeholder, and for a TABLE or FIGURE whose notice is not read. Formula and code: False.
**P3.3** The inline steps use it instead of their own kind checks: links (`links.SKIPPED_KINDS`),
citations, numbers, statistics (`notation.SKIPPED_KINDS`), units and abbreviations (`_skipped`).
Unchanged on purpose: line-end hyphens keep skipping tables (a "-" at a line end in a table is
often an empty cell, D-545 note in `hyphens.py`); footnote marks stay paragraph/heading/caption/
list only (a mark in a table points at the table's own notes inside the same block, not at a
FOOTNOTE block); characters and hidden runs already read placeholders (D-710, #463).
Not used: `_read_in_place` (the issue mentions it). It reads a name inside a notice; here there
is no notice, the block's own script pieces are read in place, so spans map character by
character like a paragraph's.
**P3.4** Second run: `rebuilt_from_script(own_output=…)` already returns a notice-off
placeholder as read (#463), and the conformance check `_inside_placeholder_problems` (D-710)
already judges edits inside one on their own output; both now cover these steps. I run the
conformance suite on the corpus with "tables-and-figures" off (all 13 documents) and list any
step that changes its own output again. Test-harness change: the corpus conformance test gains
that switched-off run as a parameter (listed in the PR).
**P3.5** Corpus check: count of table and figure blocks in the 13 documents and a before/after of
their reading with the notice off, in the PR. Default setting (notice on) is unchanged, so no
corpus snapshot should move; if one does, I stop and report.

Size: about 50 lines of code, rows, one conformance parameter.

## 4. Lessons applied
Regression rows do not lock in wrong readings (P1.2 goals rewritten, P3.1 rows corrected); a cut
ranks bracket/quote positions last (unchanged, P1.4 keeps its tests at 300); anything drawn
across a cut gets its own test (P1.4 `continues`); a re-cutting PR re-checks grace periods and
toggles (P1.8); known-errors entries name the true cause (P2.6); second-run idempotency (P1.8,
P3.4); notice-off placeholder text takes the paragraph path (P3).

## 5. Ledger
One line per PR event in `ledger/implementation.md`.

## 6. Additions of D-743 (pinned)

**A1 (gate for PR 1, before P1.1).** P1.7's phoneme measurement runs before the constant changes.
Stop and report to the coordinator if any 300 to 400-character corpus utterance passes the
voice's token limit (510), or if a number-dense 400-character sentence loses audio in either
voice. A slow test with such a sentence in English and in German proves the full text is spoken
(nothing truncated); "the voice splits it itself" is not asserted unproven.
**A2 (P1.8).** Saved user data: a marker in markers.json and a saved position in position.json
inside a sentence whose cut moves or disappears still land on that sentence after a rebuild;
shown by a test, or by naming the existing re-anchoring test that covers it.
**A3 (P1.5).** The two estimator tests may pin max_chars=300, but one estimator test stays on
the default limit. The docstring edit in app/estimate.py is allowed in PR 1, named in the body.
**A4 (PR 2).** data/en/sentence_openers.toml is covered by the packaged-data check (the wheel
contains it). The "in the U.S. Researchers found" loss is recorded with its true cause as a
regression row or a known-errors entry, as the gate result calls for.
**D-744.** #477 rows 1 and 2: English sentence-opener rule only under the P2.3 gate; a part that
fails is dropped and its row closes as a limit. Rows 3, 4 and the WBGU note (N2) close as
deliberate limits; their known-errors entries point at D-744.

## 7. Hand-off (18 Nov 19:12Z): batch done

All three PRs are merged:
- **PR 1, #524** (#494), merged as 712ec4c. The cut limit is 400 characters.
- **PR 3, #528** (#487). A table or figure whose notice is off is read as a paragraph.
- **PR 2, #547** (#488 and #477), merged as f126875. German "et al." is fixed. English initials and dotted capitals end a sentence only before a word of the opener list.

Open follow-ups, all filed:
- **#527** (textprep): "←−" is read as "minus", and "(I − P)−1" as "minus 1", in the Nowak algorithm figures. Older than #528.
- **#533** (textprep, filed by the reviewer): mutants of the cut logic that also survive on main.
- **#534** (web): the comment on `PREVIEW_LIMIT = 300` in `web/models.py` still names the cutter's old limit.
- **#536** (textprep): "im Jahr 1998. Jahr" reads differently on a second run (year output, then ordinal). Older than #524.
- **#540** (textprep, filed by the reviewer): more second-run shapes that are older than this batch.

Deferred or kept on purpose (D-744, recorded in `tests/sentences/known-errors.toml`):
- "in the U.S. Researchers found" is not cut, because the English opener list holds no nouns.
- Lower-case sentence starts ("seaborn.", "iOS") are not recognised.
- German "Es waren 3. | Studien" is not cut.
- "(WBGU 2011)" is read aloud (the row's goal says so).

Notes for later:
- The English list `data/en/sentence_openers.toml` keeps out nouns, one-letter words and the 9 function words that are also surnames ("He", "An", "So", …, #547 B1). Any word added later must pass the same check.
- `opens_sentence` now reads an English list. The units step calls it too, but no English unit is printed with a full stop, so its readings did not change.
- From a second run on, German "et al. (2019). Die" is no longer cut after "et al." (the citation is gone). The words are the same (D-577), in the same class as #482.

