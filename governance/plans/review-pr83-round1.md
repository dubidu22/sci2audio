# Review of sci2audio PR #83, round 1 (text-step interface, first half of #63)

Reviewed head: `f559876` (base `af78e0b`; main has since moved to `df76ad6`, PR #81). Reviewer thread "Review text-step interface PR 83", 12 Nov 2026.

**Verdict: changes requested.** One must-fix (a removed block can still speak), three should-fixes, four nits. Everything else checked out, listed at the end.

## Must-fix

**M1. A whole-block edit does not claim its block's two ends, so a removed block can still be read** (`src/sci2audio/textprep/runner.py:115`).
The runner uses the core overlap definition for every edit. Under it, a mark at position 0 or at the end of a block touches no character, so it does not overlap a remove of the whole block. A later inline step that inserts text (a `replace` on an empty span, D-61 (4)) or a pause at either end of a removed furniture block is accepted. Reproduced on this head: `FurnitureStep` plus an inline step inserting "Note: " at position 0 of every block and a pause at its end gives the script `[("Note: ", block 1), (pause, block 1)]` for the removed running head. The furniture block is gone but the listener hears "Note:" and a pause where it was. D-105 says coarse-to-fine exists so that "whole-block decisions" stay "intact"; this breaks that. The test `test_a_whole_block_removal_sets_aside_every_rule_inside_that_block` asserts the current behaviour (end pauses accepted), so it pins the bug.
Fix: once a block-stage edit is accepted for a block, set aside every later edit in that block, with that edit as `won_by`. Being stricter than `core.check_edits` is safe, because the accepted set still passes it. Update the unit test (all four inline edits set aside), the `greedy` reference in the property test, and add a property: no accepted edit shares a block with an accepted block-stage edit of another step. The KB entry defining `Stage` (sci2audio-design PR #22, D-107 onward) should state this rule. The reviewer tells the coordinator.

## Should-fix

**S1. The switched-off property could check the whole result** (`tests/unit/test_textprep_runner.py:256`).
The new property is sound. I checked the author's counterexample: X (0,5) sets aside Y (3,8). Z (7,9) is accepted while X is on, and set aside once X is off. So the plan's version was false. The new property is also meaningful: it fails if a switched-off edit blocks anything (the mutation "switched-off edits join the accepted set" was killed). But it compares only `accepted` and `script()`. "The same as leaving its steps out" also means every other step's outcomes are the same: status and `won_by`. Compare `[o for o in switched.outcomes if o.category is not category]` with `without.outcomes`. That is one line, and the report (#70) depends on exactly that data.

**S2. Some regression case texts are adapted, but the file says they are "from" the sample** (`tests/regression/english.toml:5`, PR body "text from its sample").
Six cases change the sample's sentences, splitting them so that one case tests one rule:
- `ligature` adds "notes that the effect was small."
- `symbols` drops "Approx. 1,234".
- `statistics` drops "(Fig. 1)" and the sentence between.
- `abbreviations` adds "Dr. Smith compared them vs. controls (see Table 2). Approx. half were girls.", and moves "(Fig. 1)".
- `acronyms` is cut down.
- `homographs` starts "Parents read" for "parents read".
That is a good design, and all the text is still project-owned. But the provenance note should be exact. Say "adapted from its sample (split so each case tests one rule; some joining words are new)", or use verbatim sentences. Because the cases are golden files, the note is part of the record.

**S3. Most generated examples propose no edit at all** (`tests/unit/test_textprep_runner.py:202`, `runs()`).
In 1,000 examples of `runs()`, 644 runs have no proposed edit and only 207 have any set-aside edit. The settling properties run on about a fifth of the examples. Raise the density: at least one step, with `st.lists(..., min_size=1)`, and a bias towards documents with non-empty blocks. Then most examples exercise the overlap rule. The nightly profile's 2,000 examples would count for more.

## Nits (no action required; reply either way)

- **N1** (`runner.py:170`): the hand-written binary search is `bisect_left(spans, (start, end))`. `bisect` is already imported for `insort`. The `position >= low` guard is redundant: at `low - 1` the start is always ≤ `start`. The mutation that removed the guard survived as an equivalent mutant. On cost, comparisons are log n per edit, as asked. `insort` shifts the list (O(n) memmove per insert), but I measured 32,000 shuffled edits in one block at 0.20 s (8,000 in 0.05 s), so nothing needs changing.
- **N2** (`testing/text_steps.py:225`): the "edit has no reason" check cannot be reached, because `core.Edit` already refuses a blank reason (the mutation removing it survived). Drop it, or keep it with a comment saying it guards against a bypassed frozen dataclass.
- **N3** (`testing/regression.py:90`): a `goal` that is not a string raises `AttributeError`. That is not in `load_cases`' caught tuple, so the error does not name the case. Check `isinstance(raw["goal"], str)` first.
- **N4** (`testing/regression.py`, `render`): blocks that read as empty are left out, so in a case with several blocks a line does not show which block it came from. That is fine for today's 14 cases. Keep it in mind when a rule PR adds a case with two similar blocks.

## Checked and fine

- **Contract against D-57 and D-61.** Edits never cross blocks: `Span` holds one block index, and every proposal goes through `check_edits`. `ask` is accepted and reads the original (test plus `apply_edits`). A step that raises, returns a non-list, names another step, goes out of its block, overlaps its own edits or, as a block step, misses its block is dropped with a `StepProblem`. The run continues, and `strict=True` raises `StepError`. There are seven parametrised cases, and every built-in test runs strict.
- **Overlap rule against `core.check_edits`.** `runner.overlap` and the test's independent `overlaps` agree with `check_edits`' sorted pairwise rule on every case I worked through: marks at a span's ends, two marks at one position, a mark strictly inside. The property test compares the runner with a plain greedy rule written separately.
- **Runner cost.** The overlap search is a bisect plus a constant number of neighbours, not a pairwise search (see N1 for numbers).
- **Registry.** Block before inline, unique ids and valid attributes are each enforced (mutations killed).
- **Layer contract.** I added `import sci2audio.testing` to `app`, then `textprep` (each breaks the layers contract), and to `cli` and `web` (each breaks the new forbidden contract). Every addition was caught.
- **Subprocess import test.** Adding `import hypothesis` to `testing/documents.py` makes it fail.
- **Regression cases.** There are 14, one per audit row. `expected` pins today's output, and for all 13 non-furniture cases it is the input as printed (white space read as single spaces). The corpus furniture test checks that every non-furniture block's script text equals `block.text` exactly.
- **Conformance suite.** The suite catches each bad-step kind (nine fakes). `no_network` records an attempt even when the step swallows the error, and it restores `socket`.
- **Mutation testing.** I ran 16 hand mutations on the runner, registry, furniture step and conformance suite. 14 were killed. One survivor is equivalent (N1) and one guards an unreachable check (N2).
- **Runs.** `ruff check`, `ruff format --check`, `lint-imports` (2 kept) and `deptry` are clean. The fast suite passes (637 tests, 29 s). Under the nightly Hypothesis profile the textprep tests pass (89 tests, 64 s). CI is green at `f559876` on Linux, macOS and Windows.
- **Before the merge.** The branch is behind main (PR #81). The reviewer updates it with a merge commit once round 2 passes.

---

# Round 2 (head `08cfb0e`)

**Verdict: one must-fix left. The rest of round 1 is fixed as listed** (PR comment 6838695026, checked item by item):
- M1: verified. My repro now sets aside both the insertion and the pause in the removed block. Removing the claim fails 3 runner tests.
- S1: verified.
- S2: verified. A script check against `sample_en.md` confirms the header's split of 6 verbatim cases and 8 adapted ones (the author's correction to 8 is right).
- S3: verified.
- N1, N2, N3: verified.
- N4: no action needed.

Runs: the fast suite passed (638 tests), and the nightly Hypothesis profile on textprep passed (90 tests).

**R2-M1. The N1 change made the overlap search linear per edit** (`runner.py:182`). `for a, b, number in spans[max(low - 1, 0) :]` copies the rest of the list before the loop breaks, so each check costs O(n) and a block costs O(n²). Measured with 32,000 shuffled edits in one block: 0.20 s at `f559876`, 1.11 s at `08cfb0e`. Real blocks hold far fewer edits, but the brief requires n log n. The cause is my N1 suggestion, done literally. Fix: an index loop, `for position in range(max(low - 1, 0), len(spans))` (not `islice`, which also steps through the skipped items one by one).

# Round 3 and merge

- **R2-M1:** fixed in `6653892` with an index loop. 32,000 shuffled edits in one block take 0.145 s. The fast suite passed (638 tests) and the nightly Hypothesis profile on textprep passed (90 tests).
- **Branch update:** merged with main as `71690a5`, which includes #85. The fast suite passed on that head (711 tests), and CI passed on Linux, macOS and Windows.
- **Merge:** squash-merged on 12 Nov 2026 as `a57d135`.
