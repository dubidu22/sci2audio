# Review PR #484, round 1 (sentence-boundary batch PR 5: hidden runs in placeholders #463, figure alt text read #464)

Head reviewed: 8db9cc2. It is two commits on main cfeb084:
- f27efd1, the harness switch and regression cases that hold today's output;
- 8db9cc2, the rules.

It is critical. Plan: plans/sentence-boundary-plan.md, PR 5 (D-719 Q5). The probes and the fix I tried are in `plans/review-pr484-round1-probes/` (`fix484-r1.diff`).

**Verdict: not approvable yet.** There is one should-fix in the test harness, and one nit.
- **S1.** The conformance change opens a hole, so a bad step that main catches now passes.
- **N1.** The alt text's "reads as nothing" check needs a pinning test.

The rules themselves are right.

## What I checked

### Tests first
- f27efd1 changes no textprep source: only `testing/regression.py`, the cases and their tests. Its own tree passes 919 tests (`test_textprep_regression*.py` and `test_textprep_conformance.py`), so its cases hold main's output.
- 8db9cc2 then changes only the six new cases' `expected`:
  - the table and code rows lose "13", "SECRET", "7" and "hidden";
  - the alt rows read "3.5 % at 12 square metres, for example p less than .05" and "3 Komma 5 Prozent bei 12 Quadratmeter", without the link or the citation.

### (1) `notice_read` gates `HiddenRunStep` (#463)
- **Probes** (`hid.py`): a table, formula, code block and figure, each holding a page-break run "13" and a hidden run "SECRET", in en, de and fr, with the category on and off.
  - A notice is read when the category is on, in en and de.
  - Otherwise the printed text is read without "13" and "SECRET". That covers the category off in any language, and French whatever the switch, because no notice step handles French.
  - This matches the notice steps exactly. `_NoticeStep.find` replaces every block of its kinds and has no other condition, and the runner puts the job's `switched_off` into the context (`runner.py`, `replace(context, switched_off=…)`).
- The French table losing its hidden runs is right: its printed text is what is read.

### (2) Alt text read as a paragraph (#464)
- **Probes** (`alt.py`): 13 alt texts in en and de, run once and then a second time over the script.
  - Links, citations ("(Smith, 2019)", "(Müller 2019, S. 4)", "Heydorn (1974/2004)") and "vgl."/"see" before a link are left out.
  - Abbreviations, units and symbols are read: "for example", "zum Beispiel", "square metres", "3 Komma 5 Prozent", "plus or minus", "less than", "Figure 3", "Abbildung 2 aus Quelle 4".
  - The second run's notice is identical in every case.
- **The departure from #464** is right. Its fallback ("the folded alt text if the reading is empty") would read a link-only alt's URL aloud, which is the very bug. An alt that reads as nothing now adds nothing, and the edit's reason says why.
- **Corpus.** The corpus figures with alt text ("A bar chart of minutes per group", "Ein Balkendiagramm der Minuten pro Gruppe", the Standard Ebooks logo) read as before.

### (3) The harness change: does the exclusion open a hole? Yes (S1)
- **The change.** `_run_problems` now leaves out of the main idempotence check every placeholder that a step edits inside. It relies on `_inside_placeholder_problems` (D-710) for those blocks.
- **Why that is not enough.** The D-710 check rebuilds the placeholder from the step's own output. So it sees a step re-reading its own edit, but not a step whose edit inside a placeholder depends on another block it also changed. Only the main check sees that, because it rebuilds the placeholder as printed and the neighbours from the script, which is the D-577 second run.
- **Probe** (`hole.py`, step `Neighbour`).
  - The step removes "loss" from paragraphs and the first character of every placeholder while some paragraph says "loss". So its second run changes the placeholders back.
  - `text_step_problems(Neighbour())` gives 8 problems on main cfeb084 ("not idempotent: run on its own output, block 0 changed again …") and **0 on 8db9cc2**.
- **The cause of the exclusion.** `rebuilt_from_script` brings a placeholder back as printed, but without its run tags. `hidden-runs` then sees no hidden run on the second run.
- The better fix keeps those tags. The printed text is unchanged, so they still fit.

### (5) Corpus, gate, known errors
- **Corpus utterances** (`/home/user/probe/p478/utt.py`, all 13 files): byte-identical to main cfeb084. No corpus placeholder holds a hidden or page-break run.
- **Goldens:** no snapshot or existing regression row changes.
- **Sentence gate:** 33 passed. The floors are unchanged: en P 1.0000 R 0.9934, de P 1.0000 R 0.9916. The known errors are unchanged at 9.
- **100 random boundaries per language** (`/home/user/probe/s478/sample.py <lang> 484`):
  - en: 58 hits, 2 optional and 40 not compared;
  - de: 95 hits, 1 optional and 4 not compared.

  I read every not-compared start: they are checklist items, table rows, captions and front matter, all real starts. No start is wrong.

### (4) The replaced test
`test_the_alt_text_is_part_of_the_notice_so_later_steps_leave_it` pinned the model that #464 changes, which was alt text read raw. Its replacement pins the new model in en and de, and the body says why. This is right.

### Mutants
`/home/user/probe/m484/run.py` on a copy of 8db9cc2. These test files ran with `-n 4 -m "not slow and not benchmark and not browser"` and `HYPOTHESIS_PROFILE=ci`:
- `test_textprep_hidden_runs.py`;
- `test_textprep_placeholders.py`;
- `test_textprep_conformance.py`;
- `test_textprep_regression*.py`;
- `test_app_corpus.py`;
- `test_testing_rebuilt_from_script.py`;
- `test_sentence_boundaries.py`.

The baseline passes: 1309 passed. Of 12 mutants, 9 are killed and 3 survive.

| # | mutant | verdict |
|---|---|---|
| 1 to 4 | hidden runs skip every placeholder (main); `notice_read` without the category, the language or the kind | killed |
| 5 | alt also for a captioned figure | **equivalent**: the notice uses `shows` only `if not names`, and a captioned figure always has names |
| 6 | alt without `index not in named` | **equivalent**: `named` holds formula indices only |
| 7 | `printed_if_left_out` dropped | killed |
| 8 | "reads as nothing" = blank instead of "no letter or digit" | **survives (N1)**: "[3], [4]" gives "It shows: ." and "https://x.org – (WBGU 2011, S. 1)" gives "Sie zeigt: –" |
| 9 | `read_twice` rebuilds placeholders as printed | killed |
| 10, 11 | the case switches ignored (run_case / load) | killed |
| 12 | the conformance exclusion removed | killed (built-in `hidden-runs` then fails), which is why S1 replaces the exclusion rather than just removing it |

## Fix list

### Should-fix

**S1. Keep a printed placeholder's run tags in `rebuilt_from_script`, and drop the exclusion in `_run_problems`.**
- **The fix.** When a placeholder comes back as printed, pass its runs' tags to `make_document`: (start, end, tags) per run in the block's text, from its `TextLine` parts. The text is unchanged, so the tags still fit. Then the main idempotence check needs no exclusion, and `hidden-runs` removes the same runs on the second run.
- **Tried** (`fix484-r1.diff`):
  - `hole.py` gives its 8 problems again;
  - all textprep tests, `test_testing_rebuilt_from_script.py` and the corpus goldens pass (3914 passed, 35 snapshots);
  - built-in `hidden-runs` keeps the contract.
- **Tests:**
  - a conformance test with the `Neighbour` step of `hole.py` ("an edit inside a placeholder that depends on another block must read the same on a second run"). It fails on 8db9cc2;
  - a `rebuilt_from_script` test: a placeholder rebuilt as printed keeps its hidden and page-break runs, and one in `own_output` does not.
- **Also:** update the docstrings of `_run_problems` and `rebuilt_from_script`, and the body's point 3.

### Nit

**N1. Pin "reads as nothing" as "no letter or digit".** Add these to `test_an_alt_text_read_as_nothing_adds_nothing_to_the_notice`:
- en "[3], [4]";
- de "https://x.org – (WBGU 2011, S. 1)".

Both give the bare notice on 8db9cc2, and mutant 8 adds "It shows: ." or "Sie zeigt: –".

## Round 2
- **The fix commit:** one fix commit with S1 and N1.
- **My checks:**
  - `hole.py` and the mutants again;
  - the corpus utterances, where I expect no change against 8db9cc2.
- **If clean, the final-round checks:**
  - nightly seeds (2024, 123456) on the textprep property tests and the conformance suite;
  - the fast suite;
  - a three-system green run on the exact head.
- **Then the merge**, on the coordinator's standing go.

## Addendum: the coordinator's rulings (01:57Z)
1. **S1 stands.** The second-run check keeps its full strength, with no exclusions.
2. **The departure from #464 is approved.** An alt text that is only a URL or only a citation adds nothing to the notice; the raw URL is not read. This needs a test for each case in each notice language, which adds to N1:
   - en: a bare "https://x.org" (today's case "See https://x.org" has a word before the link);
   - de: a citation alone, "(Müller 2019, S. 4)";
   - en "(Smith, 2019)" and de "vgl. https://x.org" are already there.
3. **D-718.** This PR revisits what #450 (PR 6, D-707/D-710) built on the old notice model, where a placeholder always goes whole and its alt text is part of the notice.
   - **Status today.** The en and de tests cover all four kinds with the notice off, and with the notice on (other categories off). French covers only the table.
   - **N2.** Parametrize `test_a_placeholder_in_a_language_without_notices_loses_its_hidden_runs` over all four kinds (table, formula, figure, code), with the category on and off. My probe `hid.py` shows all 8 French cases read "a b c".
   - The report's final round states the coverage as a table.
