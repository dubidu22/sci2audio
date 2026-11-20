# Review PR #450, round 1 (textprep batch 2 PR 6: placeholder labels on a second run, #374 #370 #362)

Head reviewed: 8df7920, with main 12fd90d merged in. Plan: plans/textprep-v12-pr6-plan.md (D-707). Critical.

**Verdict: not approvable yet. There is one blocker (B1) and two should-fix items (S1, S2). No nits.** The label reading and the oracle change do what the PR says. B1 is in the new conformance check, which two built-in steps fail.

## What I checked

- **Plan and body.**
  - The change follows D-707.
  - The body closes #374, #370 and #362.
  - The commit messages carry no closing keywords.
  - The one deviation, removing `numbers_de.label_numbers_read`, is accepted (see "Removed helper").
- **The oracle table matches the code.** In `rebuilt_from_script`, a placeholder (`block.is_placeholder`) comes back as `Block(kind, printed text, role, label)`. Its pictures' alt texts are still collected before the branch, so they are carried. Captions still map their label with `read_over`, which is the former `_mapped` moved word for word. Other blocks are unchanged.
- **Removed helper.** `label_numbers_read` has no caller left:
  - In this repo, a grep of src, tests, scripts and docs finds no match for `label_numbers_read` or `_mapped`. There is no plugins folder.
  - In the KB, a clone of sci2audio-design has no mention either.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 6620 passed, 2 skipped.
- **Corpus:** 13 documents with `run_script_job`, against main 12fd90d. Scripts, reports and work folders are byte-identical (`diff -rq` finds nothing). Timing is unchanged: nowak runs in 0.18 s against 0.17 s on main.
- **Caption fuzz, reproduced.** The author's `fuzz6.py` gives 64,512 cases on both sides: **16,080 differ on main and 0 on 8df7920.** The claim holds.
- **Probes.** I ran the whole chain twice, against main 12fd90d.
  - Linked note references glued to a label, in de and en: they now read the same on both runs. "Tab. 3x" plus a noteref reads "Tabelle 3 mal" both times; main differed.
  - Raised footnote marks after labels: these read the same as on main.
  - Bold labels followed by a number reading ("Fig. 3 × 4 grid", "Tab. 2 1990–2000", "Table 2 1/2", "Abb. 3 ½ Jahre", "Abb. 2. Verlauf"): they read the same on both runs. No step's replacement runs past a label edge.
  - Context in the small document: the only steps that read across blocks are footnotes, which need a note block, the line-end hyphen word counts, which never touch a one-line label, and citation keys. None of them changes a label reading in my probes.
  - With the notice categories switched off, the printed placeholder is read and cleaned the same on both runs.
- **#410 is fixed by this PR.** The nightly falsifying example from #436 round 3 (seed 123456: a table in REFERENCES) now reads "" on both runs. So do all 16 rows of #410's acceptance criteria: table, figure, formula and code in "References" and in "Literatur", with References on and off. On main, the 8 rows with References on all differ. See S2.

## Fix list

### Blocker

**B1. The new whole-block conformance check refuses two built-in steps.**
- **The claim.** The PR body says "All built-in steps pass". That holds only on `SAMPLE_DOCUMENTS`, which have no placeholder text for these steps to clean.
- **`unicode-clean-up`** edits inside every block kind. A formula with a soft hyphen or "ﬁ", a table with "ﬃ", or a code block with a no-break space or zero-width space each gives "an edit at … is inside a placeholder; only an edit of the whole block may change one (D-707)".
- **On the corpus:** `text_step_problems(UnicodeStep(), [nowak])` reports 26 such edits on acl2023-nowak-prefix-probabilities.
- **`line-end-hyphens`** leaves out FORMULA, TABLE and CODE but not FIGURE (`hyphens.py:111`). A figure printing "pre-\ntraining loss" fails the same way.
- **Why the edits are needed.** With Tables and figures, Formulas or Code switched off, the placeholder's printed text is read, and these edits are what clean it. Today it reads "efficiency 1 2 3", "pre-training loss" and "coefficient a = b", the same on both runs. So making the two steps skip placeholders would change what is read. That is not the fix.
- **Why it blocks.** The conformance suite is the step contract that plugins are held to, and the built-ins must pass it.

**Fix:** the check must accept the two steps and still refuse what it is there for. How is the author's choice. One way is to keep the idea of a second look at the step's own output, for placeholders only:
- an edit inside a placeholder passes if the step proposes nothing more on a copy of the document whose placeholder holds the step's own output (what the old rebuild gave);
- the whole-block rule is dropped.

`InsidePlaceholder`, which removes one more character each time, is still refused under that rule.

**Tests** (each must fail on 8df7920):
- every built-in step passes `check_text_step` on a document with a formula holding a soft hyphen and "ﬁ", a table holding "ﬃ", a code block holding a no-break space, and a figure holding "pre-\ntraining". Add it to `SAMPLE_DOCUMENTS`, or give it a test of its own that loops over `BUILT_IN_STEPS`;
- `InsidePlaceholder` is still refused, for each kind;
- update the D-707 wording in the PR body, the docstrings and the check's message to the rule you choose.

### Should-fix

**S1. Mutant 20 (the formula name read on its own instead of inside its notice) is not equivalent.**
- **Search.** I ran a counterexample search over 68 label shapes, in en and de, with the defaults and with nothing off, calling `_read_in_place` both ways. Two German labels differ:
  - `2 Mio.` reads "Formel 2 Millionen" inside the notice and "Formel 2 Millionen." on its own;
  - `3 ff.` reads "Formel 3 folgende" inside the notice and "Formel 3 folgende." on its own.
- **Why.** At the end of a text the abbreviation step keeps the stop. So the mutant gives "Formel 3 folgende. wird übersprungen."
- **Reach.** Layout's formula numbers (`maths._NUMBER`) never end like this, so files cannot reach it. A label set by a plugin or by `make_document` can.

**Fix:** a unit test on a German formula labelled `3 ff.` (or `2 Mio.`) whose notice reads "Formel 3 folgende wird übersprungen." on both runs. It must fail with mutant 20. Correct the mutation paragraph of the PR body: four survivors are equivalent (5, 8, 17, 19), and 20 is killed by the new test.

I agree that the other four survivors are equivalent:
- 5: an empty small document reads nothing.
- 8: nothing in textprep or core reads `Page.order` except its validation.
- 17 and 19: the extra readings are never looked up, and no cross-block step can reach a one-line label.

**S2. Close #410 in this PR.** The oracle change fixes it, as shown above.
- **Tests.** Add #410's acceptance tests, each failing on main 12fd90d:
  - regression cases in English and German for a table in a reference-list section, reading nothing on both runs while References is on;
  - a control with References switched off, which keeps the notice;
  - the issue's `make_document` example as a unit test.
- **PR body.** Add `Closes #410`. Say in one line why the rebuild as printed fixes it: the reference-list step removes the printed placeholder again.

## Round 2

Round 2 rechecks B1, S1 and S2. If round 2 is expected to approve, it also runs:
- the 13 corpus documents;
- the caption fuzz;
- the author's 28 mutants and the S1 mutant;
- nightly seeds 2024 and 123456 (123456 should now pass, since it was #410);
- `ci:full` on the head.
