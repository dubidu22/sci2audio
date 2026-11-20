# Review PR #450, round 2 (textprep batch 2 PR 6)

Head reviewed: a779d66. It is the fix commit 9b6cc45 plus a merge of main 1adf152, which touches CLAUDE.md only. The textprep code is unchanged since round 1 (`git diff 8df7920 a779d66 -- src/sci2audio/textprep` is empty). Rules: D-707, and D-710 as the behaviour reading confirmed by the coordinator. Critical.

**Verdict: not approvable yet, only because of two test gaps in the new own-output check (S1, S2).**
- B1, S1 and S2 of round 1 are fixed, and the code is right.
- Every heavy check of the final round passed: the corpus, mutants, nightly seeds and `ci:full`.
- What is missing: two tests, plus one sentence of the PR body. Both gaps come from mutants that survive and change whether a step passes. I found a counterexample for each.

## Round 1 items

- **B1, fixed (D-710, behaviour reading).**
  - **The change.** The whole-block rule is gone. `_inside_placeholder_problems` rebuilds each placeholder with an inner edit from the step's own output (`rebuilt_from_script(..., own_output=...)`), runs the step again, and compares. No step is exempt by id.
  - **My three checks:**
    1. **Built-ins pass.** `unicode-clean-up`, `line-end-hyphens` and every other built-in step pass `text_step_problems`:
       - on my B1 document (formula with a soft hyphen and "ﬁ", table with "ﬃ", code with a no-break space and a zero-width space, figure with "pre-\ntraining"), in en and de;
       - on `SAMPLE_DOCUMENTS`;
       - on all 13 corpus documents: no problem of any kind for any built-in step.
    2. **InsidePlaceholder** is still refused, for each kind (the suite's tests). My own `Doubler` step, which doubles an "e" inside each placeholder, is refused with 36 problems.
    3. **Plugin copies pass.** My copies of the clean-up and hyphen steps under their own ids pass, and so does a step that only spells out "ﬁ".
- **S1, fixed.** `test_a_formula_label_ending_in_an_abbreviation_is_read_inside_its_notice` ("3 ff.", "2 Mio.", both runs) kills mutant 20 (my run below).
- **S2, fixed.** The body has `Closes #410`.
  - The regression cases `reference-list-placeholders` (en) and `de-reference-list-placeholders` are in.
  - So are the 16-row test and the issue's example.
  - My #410 probe (16 rows) reads the same on both runs on this head.

## Final-round checks (all on a779d66)

- **Fast suite** (`HYPOTHESIS_PROFILE=ci`): 6650 passed, 2 skipped. The new conformance tests take 3.2 s in all.
- **Corpus:** 13 documents against main. Scripts, reports and work folders are byte-identical.
- **Caption fuzz.** It was reproduced in round 1 at 8df7920 (main 16,080 differences, PR 0). The notice code is unchanged since, so it stands.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `tests/unit/test_textprep_*.py` and `test_testing_*.py`):
  - 2024: 3744 passed.
  - 123456: 3744 passed. It failed on main because of #410, so this confirms the fix.
- **`ci:full`.** I added the label, and my run on a779d66 is green on all three systems: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, browser and `CI passed`. The author's run on the same head was green too.
- **Mutants.** I ran `mut6.py` on a clean worktree of a779d66, and the baseline passed.
  - The author's 34: 28 killed. The survivors are 5, 8, 17, 19, 26 and 28, exactly as the body says. Mutant 20 is now killed.
  - Three of my own on the new check:
    - the own copy built from the printed text: killed;
    - the third run on the original document: killed;
    - only the first placeholder compared (`for index in inside[:1]`): **survives** (S1).
- **Survivors.**
  - 5, 8, 17 and 19 are accepted as in round 1.
  - 28 is equivalent: with no placeholder edited inside, nothing is compared.
  - 26 is not (S2).

## Fix list

### Should-fix

**S1. Nothing tests that every placeholder is compared, not only the first.**
- **The mutant.** `for index in inside` changed to `for index in inside[:1]` survives every test.
- **Counterexample:** a step that spells out "ﬁ" in a formula (idempotent) and doubles the first "e" in a table (not idempotent). On the document `[FORMULA "ﬁ = x (1)" label 1, TABLE "eta 1 2"]`:
  - a779d66 refuses it ("block 1 changed again from 'eeta 1 2' to 'eeeta 1 2'");
  - the mutant lets it pass.
- **Fix:** a test with this shape, or one like it: two placeholders, only the later one not idempotent, and the step must be refused. It must fail with the mutant.

**S2. Mutant 26 (the own-output check also takes non-placeholder blocks) is not equivalent.**
- **The body's claim.** The body says it "can only repeat a problem the second-run check has already reported". That is true only for a step whose reading of a text block never depends on a placeholder's text.
- **Counterexample:** a step that cleans "dirty" to "clean" inside a figure, and in a paragraph reads "Z" as "W" always, and "X" as "Y" only while some placeholder prints "clean". On `[FIGURE "a dirty plot", PARAGRAPH "X and Z."]`:
  - a779d66 lets it pass. That is right: a real second run sees the printed figure, so the paragraph reads the same.
  - The mutant refuses it with a placeholder message about the paragraph ("block 1 changed again from 'X and W.' to 'Y and W.'").
- **Fix:**
  - a test that this kind of step keeps the contract (a paragraph's reading depends on a placeholder's printed text, and the step cleans inside that placeholder). It must fail with mutant 26;
  - in the body, mutant 26 moves to killed. The final count becomes 30 of 35 with S1's mutant added, or whatever your run gives; name the command and the baseline as before.

## Round 3

Round 3 checks only S1 and S2. It runs:
- the two tests against their mutants;
- `mut6.py` with `ONLY` set to 26 and my S1 mutant;
- the fast suite;
- `ci:full` on the new head.

If the fix commit touches nothing outside `tests/` and the PR body, the corpus, fuzz and nightly results above stand. If it is clean, round 3 is approvable.
