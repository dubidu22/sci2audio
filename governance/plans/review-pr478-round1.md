# Review PR #478, round 1 (sentence-boundary batch PR 3: rule fixes, #465 #406 #141 #268)

Head reviewed: 82dd2fe. It is two commits on main 2e2ae77:
- cd95606, the regression cases that hold today's cuts;
- 82dd2fe, the fixes.

It is critical. Plan: plans/sentence-boundary-plan.md, PR 3 (D-719). The coordinator's extra checks (1) to (7) are answered below.

**Verdict: not approvable yet.** There is one should-fix (S1) and two nits. The other follow-up only needs an Issue.
- **S1.** The #141 fix misses a maths symbol glued to its variable ("Let x= N. This holds." stays one sentence).
- **N1.** Three known-error whys name a symptom or a reason, not the mechanism.
- **N2.** Two untested choices need pinning tests.
- **Follow-up.** "Abs. 2. Abs. 3" is still not cut, the same class as the fixed "Satz 2. Satz 3". It needs an Issue.

## What I checked

### (5) Corpus utterances on main and on the PR, all 13 corpus files
I dumped every utterance on both heads (`/home/user/probe/p478/utt.py`) and diffed them per file: 3973 utterances on main, 3894 on the PR. Five files change, and every change is one of the listed fixes:

| file | change | fix |
|---|---|---|
| chi | list numbers "1." to "30." join their items ("1. First Party Collection/Use", "1. Contact" …) | section/list number alone |
| chi | "Zimmeck et al." \| "MAPS …" is now cut | removed citation ended the sentence |
| nowak block 81 | "for each X ∈ N." \| "And finally …" and "X, Y, Z ∈ N." \| "This yields …" are now cut | capital after a maths symbol (#141) |
| arsiwalla blocks 63 to 72 | the list numbers "1." to "10." join their items | number alone |
| sample-plain | "1. Introduction" is one utterance | number alone |
| maass | 29 utterances fewer in chapter 6 and one in chapter 7 | Az. (15 joins), UAbs., e. V., ff. |

There is no other change on any corpus file.

### (6) The Maaß golden, line by line (`test_app_corpus.ambr`)
- **Utterance counts.** Chapter 6 goes from 169 to 140. That is 29 joins: "Az." before a file number in blocks 59 to 96 accounts for 27 of them, block 91 "Abs. 1 UAbs. | 1" for one, and block 86 "§§ 185 ff. | StGB" for one. Chapter 7 goes from 15 to 14, from block 100 "Digitalcourage e. | V.".
- **The "ff." edit** now covers the full stop: `original` 'ff' → 'ff.' and `end` 1021 → 1022, and the report row reads "“ff.” → read as “folgende”". This comes from `inside_citation = true`: the stop is read through instead of kept. The script now reads "§§ 185 folgende StGB werden …", and the 300-character limit cuts the joined sentence after "geeignet ist," (`continues`).
- **The script lines** are exactly the joins above. Nothing else changes.

### (1) Known errors 25 → 11
- **Removed (14).** These are the chi Zimmeck entry, sample-plain "1. Introduction", the three Maaß entries (ff., UAbs., e. V.), stress-en Smith et al. (2019), A ⊂ B and Appendix C, and stress-de e. V., Fa., UAbs., ff., Az. and "Satz 2.".
  - Every one of them is a line of a truth file. If its fix were undone, the gate would fail with "errors not in known-errors.toml". The mutants below show this for each fix.
  - Most are also pinned by a unit test or a regression case: `test_sentence_ends_found_by_the_sentence_test_set`, the removed-stretch tests, and the English and German regression cases of cd95606 and 82dd2fe.
- **Kept (11):**
  - 4 entries go to #466 (plain-text titles and "- " items, layout);
  - 2 Lorenz entries go to #455 (PR 4);
  - 5 are kept on purpose under #477 (open, milestone Later): U.S., "A. Then", seaborn, iOS, "Es waren 3. Studien".
  - The causes of the #466 entries and the four other #477 entries are right. U.S. and the two Lorenz entries name a symptom or a reason instead of the mechanism (N1).
- **Floors.** They are now en P 1.000 R 0.993 and de P 1.000 R 0.991. They are reproduced: en natural P 1.0 R 0.9934, de natural P 1.0 R 0.9916.

### (4) Tests that fail without each fix, and the timing guard (5)
I ran 19 mutants (`/home/user/probe/m478/run.py`) on a copy of src and tests, with these test files: `test_textprep_utterances.py`, `test_sentence_boundaries.py`, `test_textprep_regression.py`, `test_textprep_regression_german.py`, `test_textprep_units_abbreviations.py`, `test_textprep_units_per_and_german_readings.py` and `test_app_corpus.py`, filtered to `-m "not slow and not benchmark and not browser"`. The baseline passes: 1471 passed.

| # | mutant | result |
|---|---|---|
| 1 | removed-text full stop ignored (the "et al." fix) | killed: `test_a_sentence_ends_where_a_removed_stretch_ended_it`, `test_a_citation_after_a_read_english_abbreviation…`, gate, floors (10 tests) |
| 2 | `_ENDED` without closing marks | killed (`…full_stop_and_a_closing_bracket_ends_it`) |
| 3 | `before.span.end <= piece.span.start` | survives. **Equivalent**: adjacent pieces give an empty removed stretch, which `_ENDED` cannot match |
| 4 | number-only skip off (the "1. Introduction" fix) | killed: `test_sentence_ends_found_by_the_sentence_test_set`, gate, floors, regression |
| 5 | number-only without sub-numbers | killed ("2.1. Methods") |
| 6 | number-only with four digits | **survives** (N2) |
| 7, 8, 9 | `_letter_of` off / no symbol / no label | killed |
| 10 | `_letter_of`: any symbol character | **survives**; it shows S1 |
| 11 to 14 | German az. / fa. / uabs. / e. removed | killed (gate; three also by the Maaß golden) |
| 15 | ff. not `inside_citation` | killed |
| 16 | law names without mixed case ("StGB") | killed |
| 17 | repeated-label guard off | killed (gate "Satz 2.", regression) |
| 18 | guard ignores the label's dot | **survives** (N2) |
| 19 | the old quadratic look-back put back | killed: `test_a_block_of_many_sentences_is_cut_in_linear_time` times out (63 s) |

**Extra timing probe.** A 416,000-character block of abbreviations with no sentence end ("see Fig. A and Fig. B and " repeated) runs in 0.02 s, 0.05 s, 0.12 s and 0.32 s for 2,000 to 16,000 repeats. That is near-linear, so the `_NUMBER_ONLY` slice from the last cut costs nothing measurable.

### (2) 100 random boundaries per language (seed 478)
The sample was made with `/home/user/probe/s478/sample.py <lang> 478`. It draws, with `random.Random(478)`, 100 of the script's sentence starts on the natural sets (en: 567 starts, de: 251) and looks each one up in the truth.
- **en.** 65 are hits at compared gaps. 35 are not compared: block or segment starts outside the truth's sentences, such as table cells, ACL checklist items, title, author and abstract lines, figure Q/A lines and code. I read each one, and all are real starts.
- **de.** 89 are hits, 1 is optional ("Fußnoten² oder stören sie | Wenn …"), and 10 are not compared (title and author lines, a formula, a table, "Abb. 1" caption, the markdown note's headings). All are real starts.
- **No sampled start is wrong.** This matches precision 1.0 on both natural sets.
- **The recall side** is fully counted by the metric: en misses 2 and de misses 2, all four #466.

### (3) Evaluation reproduced
I ran `plans/sentence-boundary-eval/eval.py` once on main 2e2ae77, with pySBD 0.3.4 and syntok 1.4.4 in a scratch folder. Every error count in `plans/sentence-boundary-eval.md` reproduces exactly:

| candidate | EN natural | EN stress | DE natural | DE stress |
|---|---|---|---|---|
| ours | 4 | 7 | 5 | 9 |
| pySBD | 13 | 3 | 6 | 15 |
| syntok | 3 | 7 | 11 | 17 |

Ours on the PR head (`--only ours`) makes 2, 4, 2 and 3. By the plan's test (fewer natural-set errors and no more stress-set errors), no library wins either language. Not adopting them is right.

### Tests first
- cd95606's regression cases pass on main's source: 824 passed with `test_textprep_regression*.py` and the gate. So they hold today's cuts first.
- 82dd2fe then changes only their `utterances`:
  - "Smith et al. (2019). Then" and "Smith et al. https://x.org. Then" are now cut after "et al.";
  - "1. Introduction" is one utterance;
  - "x ∈ N." and "A ⊂ B." are cut.
- The expected scripts are unchanged.

### Second-run note
The cut from removed text can disappear on a second run ("Smith et al. Then more." gives one utterance), and the script text is identical. D-577 asks for identical text, so this holds. The module docstring states it.

### (7) D-718
- **#467** built the known-errors gate and floors that this PR shrinks. Its model still holds: each removed entry is a fixed error that the gate would catch coming back, the 11 left all name an issue, and the floors only rise.
- **#476** changed only layout and built nothing on the cutter rules. Its corpus blocks are unchanged by this PR.
- The PR body's D-718 line says the same.

## Fix list

### Should-fix

**S1. A maths symbol glued to its variable still reads the capital as an initial (#141).**
- **The cause.** `_letter_of` calls the capital a letter only when every character of the word before it is a maths symbol.
- **Probes on 82dd2fe.** Both of these stay one utterance:
  - `cut("Let x= N. This holds.")` gives `['Let x= N. This holds.']`;
  - `cut("Let 2x≤ N. This holds.")` gives one utterance too.

  PDF text often glues the symbol to the variable before it ("x=", "n≥").
- **Fix.** Test the last character of the word before: `symbol = unicodedata.category(before[1][-1]) == "Sm"`.
  - I tried it on 82dd2fe. Both probes cut ("Let x= N." | "This holds."). The sentence tests, regression cases and corpus golden pass (1022 passed). The corpus utterances of all 13 files are byte-identical to 82dd2fe.
- **Tests.** Add both probes to `test_sentence_ends_found_by_the_sentence_test_set`. They fail on 82dd2fe.

### Nits

**N1. Three known-error whys do not name the mechanism** (the coordinator's check 1). Suggested wording:
- **U.S.:** "'U.S.' is no abbreviation of the English list, so its full stop ends the sentence; kept on purpose: it ends a sentence as often as it stands before a name".
- **Lorenz FP:** "a full stop inside the closing quote, then an opening bracket, ends the sentence, so the source is cut off its quotation (shape of #455)".
- **Lorenz FN:** "the source's closing bracket has no full stop after it, so nothing ends the sentence before 'Danach' (shape of #455)".

**N2. Pin two choices that no test holds** (mutants 6 and 18):
- **`_NUMBER_ONLY` takes one to three digits.** A four-digit year alone still ends its sentence: `cut("It ended. 2019. Then more.")` gives `["It ended.", "2019.", "Then more."]`. Add it to the parametrized test.
- **The repeated-label guard in `numbers_de._ordinals` requires `not previous["dot"]`.**
  - I found no input where that condition matters: "Satz 2. Satz 3" and "Nr. 2. Nr. 3" give the same result with and without it.
  - Either add a test showing a case it decides, or drop the condition and say why in the body.

### Follow-up (needs an Issue, not this PR)
- "Es gilt Abs. 2. Abs. 3 gilt hier auch." stays one utterance, while "Satz 2. Satz 3" and "Nr. 2. Nr. 3" are now cut.
- "Absatz" (from "Abs.") is no label word for the cutter's German short-number rule. So after the ordinals guard skips it, nothing ends the sentence.
- This is the same class as the fixed "Satz" entry, and law texts such as Maaß print "Abs." often. It was not cut on main either, so it is not a regression.
- Please file it (lane:textprep, milestone v1.2.x with the abbreviations) and name it in the body.

## Round 2
- **The fix commit:** S1 plus its tests, N1, N2, and the new Issue in the body.
- **Mutants:** I rerun all 19 mutants plus the S1 variant.
- **Corpus diff:** I diff the corpus utterances again. I expect no change against 82dd2fe.
- **Sentence tests and fast suite:** I rerun the sentence tests and the fast suite.
- **If clean, the final-round checks:** nightly seeds (2024, 123456) on the textprep property tests, the fuzz, and `ci:full` re-added for three-system green on the exact head. Then I merge on the coordinator's standing go.
