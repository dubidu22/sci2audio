# Review PR #467, round 1 (sentence-boundary batch PR 1: sentence test set, metric, known-errors gate)

Head reviewed: 969a433, one commit on main 7cd84bd. Plan: plans/sentence-boundary-plan.md, PR 1 (D-719). Critical, and it adds tests only.

**Verdict: not approvable yet.**
- The truth, the metric and the gate hold up under every check below.
- One should-fix (S1) remains: the stated cause of the two "ff." errors is wrong. Adding "ff." to the cutter's list does not remove them.
- Two nits (N1, N2).

Since the PR is tests only, the heavy checks for this PR were done in this round:
- the gate and metric mutants;
- the full truth check (every disagreement, plus 100 starts per language);
- the fast suite.

The author's `ci:full` run on 969a433 is green on all three systems. If round 2 changes only `known-errors.toml` (and the body or the issue), it is approvable.

## What I checked

### Licence and attribution
- The three paper files quote corpus papers that `tests/corpus/LICENSES.md` lists as CC-BY-4.0: hardt (row 17), chi (row 18) and maass (row 23).
- Each file names the title, authors, source URL and licence at its top, and `tests/sentences/README.md` has the attribution table.
- The own samples are CC0, written for sci2audio (rows 25 to 28).
- The stress sets are CC0. Their names and works are stated to be made up, and the sentences read as own writing ("Der Weg entsteht im Gehen." is a proverb).
- No personal-use paper is used: there is no Kehren text, and its shapes appear only as own sentences.
- No new dependency.

### The truth was not derived from the cutter
- I compared the word forms of each paper truth with poppler's `pdftotext` output and with sci2audio's block text:

| file | word types in the truth | only in pdftotext | only in sci2audio | in neither |
|---|---|---|---|---|
| hardt | 853 | 18 | **0** | 2 |
| chi | 1119 | 17 | **0** | 4 |
| maass | 1808 | 19 | **0** | 2 |

- The truth carries pdftotext's forms where sci2audio's extraction differs (line-end splits such as "identifying" and "Seitenbetreibers"), and never a form that only sci2audio has. That fits "drafted from pdftotext, split by hand".
- The README's step 2 says a truth error is corrected with a `#` comment. No such comment exists, so no truth line was corrected after the cutter comparison. That fits too.

### Every disagreement checked against the page
The disagreements are the 25 known errors: 9 in the natural sets and 16 in the stress sets.

- **Natural sets.** All 9 are real script errors, and the truth is right in each case. I checked them against `pdftotext` and the source files:
  - chi "Zimmeck et al. (2019). | MAPS consists" (page 9);
  - maass "§§ 185 ff. StGB" (pdftotext line 495), "Abs. 1 UAbs. 1 lit. f" (line 521) and "Digitalcourage e. V. für" (line 560);
  - the plain-text title and subtitle lines and the "- " list items (sample-plain lines 1 to 2 and 21 to 22, beispiel-text lines 1 to 2 and 18 to 19);
  - "1. Introduction" (sample-plain line 8).
- **Stress sets.** All 16 truths are what a listener should hear: U.S., "A. | Then", et al. (2019), "A ⊂ B.", seaborn and iOS, "Appendix C.", "Es waren 3.", e. V., Fa., UAbs., ff., Az., "Satz 2.", and the two Lorenz rows.
- **Issues.** Every entry has one: #465 (new, v1.2, with the table), #466 (new, v1.2), and the existing #406 and #141. #468 is filed for the second German paper (D-719 Q3).
- **Whether each "why" names the real cause.** I added each word to the cutter's list:

| word added | result |
|---|---|
| "u.s." (en) | the U.S. error goes, so its why is right |
| "uabs.", "e.", "v.", "fa.", "az." | those errors go, so their whys are right |
| "ff." | the error stays (S1) |

### 100 random sentence starts per language (seed 467)
The sample was made with `/home/user/probe/s467/sample.py <lang> 467`. It draws, with `random.Random(467)`, 100 of the truth's sentence starts that follow another line in the same segment:
- en: 100 of 313 starts, from hardt, chi, sample-plain and sample-note;
- de: 100 of 243 starts, from maass, beispiel-text and beispiel-notiz.

**All 200 are correct boundaries.** They are sentence ends followed by a new sentence, or heading, caption, run-in head and list-item lines. Some I looked at more closely:
- chi "APP-350" and "PI-Extract" (bold run-in heads);
- chi "(Amos et al., 2021).4 | The Princeton-Leuven" (the footnote mark stays in place);
- hardt "(Dasigi et al., 2019)[p. 1] note that …";
- maass "lit. a–d. | Ob unter die Ausnahme";
- maass "Mozilla.6 | Darüber hinaus".

**The other direction.** I also listed every place inside a truth line where sentence punctuation is followed by a capital or digit: 149 places, which would be missed starts if the truth were wrong. All are correct non-starts:
- "et al. (2019)", "vs. Non-Ellipsis", "z. B.", "i. S. v.", "Abs. 1", "Art. 6", "e. V.";
- section numbers inside a heading line ("2.1 Datasets").

### The metric
- **Alignment.** No chance matches: no matching run shorter than 8 words lands more than 30 words away from where its neighbours put it, in any of the 7 natural files.
- **Coverage per file:** hardt 0.993, chi 0.995, maass 0.998, sample-plain 1.000, sample-note 0.950, beispiel-text 1.000, beispiel-notiz 0.944. All are above the 0.9 gate.
- **Baseline reproduced:** en P 0.9967, R 0.9900 (298 found, 1 extra, 3 missed); de P 0.9874, R 0.9916 (235, 3, 2). The floors are the baseline rounded down.

### Gate and metric mutants
I made each change on a copy of src and tests and ran `tests/unit/test_sentence_boundaries.py` (`/home/user/probe/g467/run.py`). The baseline passes.

| change | gate |
|---|---|
| a new boundary error: "vs." taken off the English list | **fails** (errors not listed; floor) |
| a listed error goes away: "u.s." added to the English list | **fails** ("listed errors that no longer happen") |
| a listed error goes away: "ff." added to the German list | passes: the error does not go away (S1) |
| optional starts counted | fails |
| FP and FN swapped | fails |
| continued pieces counted as starts | fails |
| first gap of every match skipped | fails |
| `MIN_RUN` 1 / 6 | fails / fails |
| footnote blocks kept on the script side | fails (floor) |
| line-end hyphen join off | fails |
| blocks nobody hears kept | fails |
| key keeps case | fails |
| stress paragraphs written one sentence per paragraph | fails |
| `assert not new` dropped, with "vs." taken off | still fails, through the floor (second line of defence) |

The gate fails on a new boundary error and on a listed error that goes away, as the coordinator asked.

### Fast suite and timing
- Fast suite with `HYPOTHESIS_PROFILE=ci` and `-n 4`: 6698 passed, 2 skipped.
- `test_sentence_boundaries.py` alone runs 33 tests in 5.1 s; the three papers take 0.9 to 1.8 s each.

## Fix list

### Should-fix

**S1. The two "ff." entries give a wrong cause.**
- **The entries.** `known-errors.toml` says "'ff.' is no abbreviation of the German list" for maass "S. v. 185 ff. | StGB" and stress-de "185 ff. | StGB". #465's table says the same.
- **The real cause.** The abbreviations step reads "ff" as "folgende" and keeps the full stop as printed text (the script pieces are `' §§ 185 '`, `'folgende'`, `'. StGB …'`). The cutter then sees "185 folgende." and ends the sentence there.
- **Proof.** Adding "ff." to `ABBREVIATIONS["de"]` changes nothing: the error stays, and the gate passes.
- **Why it matters.** PR 3 will fix by these whys.

**Fix:**
- correct `why` for both entries (for example: "the abbreviations step reads 'ff' as 'folgende' and keeps the full stop, which then ends the sentence");
- correct the "ff." row of #465's table the same way;
- keep the class `abbreviation`.

No test change is needed: the gate keys on `kind` and `at` only.

### Nits

**N1. The plan asked for more output than the test prints.** The plan wanted precision, recall and F1 per language **and per file**, and false positives split into **block** (layout) and **in-block** (rule). The metric computes the layout flag, but nothing reports it, and only per-language precision and recall are printed. Do one of these:
- print a per-file line (P, R, F1, layout FPs, rule FPs) in `test_natural_sets_stay_above_the_floors`;
- or say in the body that this moves to PR 3's evaluation.

The metric also sits in `tests/unit/sentence_metric.py`, not `tests/sentences/metric.py` as planned. That is fine (it must be importable), but say so in one line.

**N2. The out-of-repo evaluation script is missing.** The plan's PR 1 section names `plans/sentence-boundary-eval/eval.py` (mount, not shipped), and that folder does not exist. It is needed by PR 3, not this PR. This is a note for the coordinator; nothing in this PR needs to change.

## Round 2

Round 2 checks S1 (and N1 if done). It reruns the gate and the fast suite, and reads the three-system result on the new head. If the fix commit touches only `tests/sentences/known-errors.toml` and the test's printing, nothing else needs rerunning, and round 2 is approvable.
