# Light batch audit: sentence-boundary batch (D-715, plan D-719), 17 Nov 2026

Scope: the six squash commits on main from base 7cd84bd to 4bb8f81, read as one diff (48 files, +3972 −713): #467 1c45cab (PR 1, sentence sets + metric + gate), #476 2e2ae77 (PR 2, layout), #478 7d866bf (PR 3, sentence rules), #481 cfeb084 (PR 4, clause cuts + #455 citations), #486 6525212 (Windows quarantine, D-725), #484 4bb8f81 (PR 5, #463 #464). Looking only for cross-PR inconsistencies (D-718), unannounced touches to contracts, core dataclasses, goldens, regression cases or CI, and truth or known-errors entries that lock in a wrong reading. Read-only, one pass, Opus medium. I did not re-review each PR; the review reports (plans/review-pr{467,476,478,481,484,486}-round*.md) cover that.

Method:
- Read the plan (plans/sentence-boundary-plan.md) and its "earlier PRs built on a model this PR changes" lines, and the previous audit for the format.
- `git diff 7cd84bd 4bb8f81` per area: `textprep/utterances.py` (PR 3 and PR 4 both), `testing/{documents,regression,text_steps}.py` (PR 5), `tests/sentences/*`, both regression TOMLs (every removed or changed line), the three snapshot files, CI and quarantine.
- Ran on main, Python 3.13, scratch venv: `test_sentence_boundaries.py`, both regression test files and `test_textprep_conformance.py`: 954 passed.
- Probes through the whole chain (`run_steps` defaults and with categories off, then `cut_utterances`, second run via `rebuilt_from_script`), en and de, on main and on the base 7cd84bd for comparison. Scripts in this thread's scratchpad, not kept.

## Verdict

**The batch is sound. Missed findings: B 0, S 2, N 2.** No contract or core dataclass was touched. S1 is a cross-PR model split inside PR 5 (alt text now read as a paragraph, the same block's own text not). S2 is older than the batch but squarely in its area. Neither breaks the second-run guarantee.

What holds:
- **PR 3 and PR 4 on `utterances.py`:** PR 4 changed only the cut inside an over-long sentence (`_cut_point` ranking, clause openers, MIN_PIECE 40, bracket/quote depth); it does not touch `_sentences`, and PR 3 did not touch `_fitted`/`_cut_point`, as both plans said. A 420-character German sentence holding "e. V." and "Az. 13 W 17/12" is cut at a space in the second half, not inside either, and the second run gives the same utterances. #482 already covers a cut inside a multi-word reading.
- **PR 3's "removed text ended the sentence" rule against PR 4/5 removals:** probed German narrative citations ending in "f.)" / "ff.)" before a capital noun ("Wie Heydorn (1970, S. 12 ff.) Bildung versteht"), "(ebd.)", "u. a. (2019)", a link ending a sentence, hidden runs and page-break markers ending in a full stop mid-sentence before a capital ("die Seite 12. Bildung"). No wrong cut; every result is identical on the base, so the new rule fires only where a printed sentence ended.
- **PR 1's metric against PR 2's layout change:** the metric reads utterances with `continues=False` from the default job and does not call `rebuilt_from_script`, so PR 4's cuts (`continues=True`) and PR 5's harness changes do not move it. Truth files (`tests/sentences/*.txt`) were written once in PR 1 and never edited after; only `known-errors.toml` shrank (25 → 11 → 9), as a ratchet should.
- **Regression TOMLs:** every removed line in the batch is in PR 3, three rows (`citations-after-a-read-abbreviation-keep-the-sentence-end`, `links-no-two-full-stops-after-an-abbreviation`, `de-links-no-two-full-stops-after-an-abbreviation`): `expected` unchanged, `utterances` now cut after the removed citation or link, and each goal says why (D-719). PR 4 and PR 5 only add rows.
- **CI:** no workflow or `pyproject.toml` change in the batch. The only test-harness CI touch is the #486 marker: `quarantined(issue=485, platform="win32")` on one test, Linux and macOS still run it, decided as D-725 outside the plan.

## Findings

### Should fix

**S1. With its notice off, a table or figure is read raw, while its alt text is now read as a paragraph; two new rows' goals claim the paragraph model. Filed as #487 (lane:textprep, no milestone; coordinator to set).**

PR 5 (#464) read alt text through `_read_in_place` as a PARAGRAPH because raw text sounds wrong. The same PR (#463) made a notice-off placeholder's own text lose its hidden runs, but that text still gets only the D-710 clean-up, so numbers, units, abbreviations and citations reach the voice raw:

| "Tables and figures" off | table | same text as a paragraph |
|---|---|---|
| de | `Anteil 3,5 % bei 12 m² (Müller, 2019)` | `Anteil 3 Komma 5 Prozent bei 12 Quadratmeter.` |
| en | `Share 3.5 % at 12 m² e.g. p < .05 (Smith, 2019)` | `Share 3.5 % at 12 square metres for example p less than .05.` |

The rows `hidden-runs-in-a-table-read-when-its-notice-is-off` (goal "as a paragraph is") and `de-hidden-runs-in-a-table-read-when-its-notice-is-off` (goal "wie ein Absatz", expected `Gruppe Mittel 4,2`, where a paragraph reads "4 Komma 2") pin the raw reading under a goal that describes the other one. Non-default setting; behaviour older than the batch (D-710), but this batch put the two models next to each other. Fix: either read table and figure text through the inline chain when the notice is off (formulas and code stay printed), or keep it by design and reword the two goals to "read as printed, without hidden runs". Coordinator's call; the issue lists both.

**S2. German "et al." ends the sentence before a capital noun. Filed as #488 (lane:textprep, no milestone).**

"al." is in the English sentence-end abbreviations but not in `ABBREVIATIONS["de"]`. Since German nouns are capitalised, the cut misfires often: `Wie Müller et al. (2019) Bildung verstehen, ist bekannt.` reads `Wie Müller et al.` / `Bildung verstehen, ist bekannt.`; `Laut Müller et al. Kapitel 2 gilt das.` is cut the same way. Same on the base 7cd84bd, so not caused by the batch, but PR 3's German abbreviation fixes (#406) and the stress-de set both missed it. A pause and pitch drop, no text lost. Fix: add "al." for German, keep the D-719 cut after "et al. (2019). Die", and add a stress-de line.

### Nits

**N1. PR 5's plan did not announce its `sci2audio.testing` changes.** The plan said "regression rows and a SAMPLE_DOCUMENTS entry". The PR also added the `switched_off` case key and `run_case` (`testing/regression.py`), changed `read_twice` to rebuild notice-off placeholders from the script (`own_output`), made `rebuilt_from_script` keep the run tags of printed placeholders, and exported `notice_read` from `sci2audio.textprep`. All of these are conformance-suite and regression-case machinery, so critical by CLAUDE.md, and the review handled them as such (round 1 S1, round 2 S1, coordinator's ruling that the contract check keeps full strength; the conformance exclusion was dropped). So there is no gap in what got checked, only in what the plan listed. The D-718 line "Earlier PRs ... none" was right: no earlier PR of this batch uses `rebuilt_from_script` or `read_twice`. Suggestion for the plan template: a line "harness or test-format changes", next to the D-718 line.

**N2. `de-citation-with-a-capital-author-and-a-page` pins `(WBGU 2011)` read aloud without an issue.** The row's goal explains the guard (an all-capitals author needs a page or ", 2011", or "(EU 2016)" would go too), and review #481 round 1 checked it with a mutant table, so it is a known limit rather than a wrong truth. But unlike the #477 "kept on purpose" entries it names no issue, so nobody will revisit it. Suggest adding it to #477 (Later) with one line. Not filed separately.

## Contract touches (checked, none)

- **Core dataclasses (`sci2audio.core`), lint-imports layers, voice contract:** no change in the batch. `testing.documents` gained a `core.Item` import (testing sits above core). `textprep.furniture` now imports `textprep.placeholders.notice_read` at module level; `placeholders` does not import `furniture`, so no cycle.
- **Text-step interface:** unchanged; `TEXT_STEP_API` not touched, no new step, category or switch. New public name `notice_read` (PR 5), plugin interface still not public until #216 (v1.4).
- **Layer contract "utterances never cross blocks":** PR 2 joins rows into one block in layout, so the contract holds; the join is a layout decision, announced in the plan with its golden changes.
- **Goldens:** layout corpus and citations/links corpus snapshots changed by PR 2 only (announced: "layout golden files may change"); app corpus snapshot by PR 3 (Maass script/report, announced) and PR 4 (utterance counts and cut positions, follows from "regression cases" in its plan; a snapshot line in the plan would have been clearer). PR 5 changed no golden. No corpus truth file changed.
- **Regression-case format:** new optional `switched_off` key (PR 5), see N1; old cases load unchanged (`DEFAULT_SWITCHED_OFF` default), unknown names and non-lists are refused with the case id.

## Truth set and known errors (checked)

- The 9 remaining known errors are true errors with true causes: 4 `layout-join` in the plain-text samples (#466), 5 "kept on purpose" in the stress sets (#477). None marks a correct reading as an error or the reverse ("U.S. | Census" is an FP against a correct truth; "3. | Studien" is an FN against a correct truth).
- `~ ` optional starts: 41 lines in total, all of the README's kinds (run-in heads in chi 18 and maass 9, numbered examples after a colon in hardt 4, title/subtitle and list lines in the own samples). None is in a stress set, and none was added after PR 1, so none was used to absorb a rule error found later.
- Floors en P 1.000 R 0.993, de P 1.000 R 0.991 in the file; the batch ledger line reports de R 0.992 measured. That is consistent: floors are rounded down and only raised by a PR that raises them.

## Not findings (checked, fine or out of scope)

- Over-long alt text in a notice: cut by length at a space into two pieces of about 215 characters, second run identical.
- In the probes I also saw, all older than the batch and outside a light audit: "As Smith (2019, p. 5 f.) Figure 2" keeps the citation and cuts after it (en "f." locator not a citation); "LG Ulm vom 13.01.15" date not read; "matplot lib" / "passedthrough" extraction joins in the app corpus snapshot. Left for the coordinator to file if wanted.

## Workflow verdict (D-627 item 6)

| | B | S | N |
|---|---|---|---|
| Found by the batch review (#467 r1–2, #476 r1–3, #478 r1–2, #481 r1–3, #484 r1–3, #486 r1) | 0 | 11 (#467 1, #476 4, #478 1, #481 3, #484 2) | 9 (#467 2, #478 2, #481 3, #484 2) |
| Missed, found by this audit | 0 | 2 (S1 #487 non-default setting; S2 #488 older than the batch) | 2 |

Thread lifetime: one authoring thread did all five PRs with one review thread (1 compression on the reviewer). The plan's D-718 lines were right for every PR, and the review caught the one real harness risk (#484's conformance exclusion) before merge, so the template line from the last audit worked. The one cross-PR split (S1) is inside a single PR, made by an optional follow-up folded into a batch on another topic, not by context loss. Judgement: **keep lane threads at the current length** (one batch, replace at 2 compressions). One adjustment: fold unrelated follow-ups into a batch only when they share the batch's model; PR 5 (#463 #464) was placeholder work in a sentence batch, took three rounds, two of the review's should-fixes and this audit's S1.
