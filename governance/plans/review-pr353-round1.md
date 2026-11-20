# Review PR #353, round 1 (textprep follow-ups PR 1, #324)

Head reviewed: f5b2a37 (base main 99b8166). Plan: plans/textprep-v12-followups-plan.md PR 1 (D-605). Critical.

**Verdict: not approvable yet. One blocker (B1), no should-fix, two nits.**

## What I checked

- Change against the plan: matches PR 1 (label mapped through the script, corpus second-run test over every paper, the four #324 cases out of `SECOND_RUN_EXCEPTIONS`, no regression case text changed). One gap against the plan's guard, see B1.
- Fast suite on the branch (`HYPOTHESIS_PROFILE=ci`, -n 4): 5196 passed, 1 skipped, 2 xfailed (#320, #321), as the author reports.
- Regression cases English and German, run twice: 565 passed, 2 xfailed both times.
- Corpus second-run test: 8 of 8 papers pass. ruff check, ruff format, lint-imports (3 kept), deptry: clean.
- Sample documents: the only `src` change is `sci2audio/testing/documents.py`, which no app, web or stage module imports, so no corpus script can change. Probed anyway: the five non-PDF corpus documents (EPUB, two Markdown, two text) read the same on a second run on both main and the branch.
- Nightly seeds (`HYPOTHESIS_PROFILE=nightly`, runner + conformance + new unit file): 1, 2024, 99999, 7, 123456 all clean.
- Timing: no step changes. The corpus test now runs 8 papers instead of 1 (8.4 s locally, each paper well under the 120 s module timeout).
- Commit messages: no "fixes/closes/resolves #N" in either branch commit. `Closes #324` is only in the PR body.
- Mutation-style breaks of `_rebuilt_label` / `_mapped` (each run against the new unit file, both regression files, runner, corpus and the three other users of `rebuilt_from_script`):
  - killed: placeholder guard removed; crossing replacement no longer gives None; inside-check loosened; kept piece appended whole; short-circuit "label in text" removed; strip check removed (killed only by the English regression case `footnote-with-symbol-mark`, see B1).
  - survived: final `label in text` check removed; `splitlines` check removed; pause skip removed. All three are unreachable or redundant (N1), not missing tests.

## Fix list

### Blockers

**B1. A footnote mark is mapped into its introduction: a made-up label.** The PR says (and the plan's guard requires) that no label is made up for a block whose label really went. That holds for placeholders only because of the explicit `is_placeholder` exception. A footnote's mark is replaced by the footnotes step's introduction in the same way, and the mapping turns the introduction into the label:

- Corpus, maass block 10: label `∗`, text `∗ Dieser Artikel …`; the script replaces `∗` (span 0–1) with `Fußnote.`, so the rebuilt label is `Fußnote.` (main: `""`).
- Made-up documents: English `Block(FOOTNOTE, "† Note.", label="†")` and `"* Note."` rebuild with label `Footnote.`; German `"∗ Hinweis."` with `Fußnote.` (main: `""` for all).
- English escapes this only when the note text is glued to the mark (`"∗Work done…"` → introduction `"Footnote. "` with a trailing space, which fails the strip check). Removing the strip check makes `footnote-with-symbol-mark` fail, so today the guard is an accident of whitespace.

The second run happens to read the same (the step sees the text as already introduced), so no test fails, but `rebuilt_from_script` is the plugin authors' second-run helper (#203): a plugin step that matches marks by label would now look for a mark "Fußnote." in the running text.

Fix: map the label through the script only for captions (`block.kind is BlockKind.CAPTION`), the only kind #324 needs; every other kind (footnote mark, formula number, heading number, list marker) keeps the old rule (stays if the new text prints it, else goes). The `is_placeholder` check is then covered by the same rule; keep or fold it as you prefer. Tests: (a) unit tests that an English `"† Note."` and a German `"∗ Hinweis."` footnote rebuild with label `""` (fail on the current head); (b) in `test_every_paper_reads_the_same_on_a_second_run`, assert that every label the rebuild changed belongs to a caption, so a corpus paper pins it too (fails on the current head at maass block 10). Update the docstrings and the PR body ("in a block that is read") to say captions.

### Should-fix

None.

### Nits

**N1. Unreachable checks and a test that does not test its name.** A pause has an empty span and no text (core `ScriptPiece`), so without the `piece.pause` skip it lands in the kept branch and adds nothing: `test_a_label_next_to_a_pause_only_goes` passes for the reason "no piece covers the label", not because of the skip. The final `label in text` and `splitlines` checks cannot fail either: the mapped pieces are consecutive in script order, so their text is a substring of the rebuilt text, and `Block` checks both again. Either drop the pause skip and rename the test (for example "a label covered only by a pause goes"), or leave the code and say in a comment that the checks are defensive. No new tests wanted for these.

**N2. Non-PDF corpus documents.** The corpus second-run test covers the 8 papers only. The EPUB, two Markdown and two text corpus documents also read the same on a second run (probed on the branch and on main), and the Markdown notes carry labels. Optional: parametrise the test over them too, or say why not.

### Deferred

None.

## Next

Round 2 on the new head: B1 tests must fail on f5b2a37 and pass on the fix; re-run the mutation set, fast suite, regression cases twice, two nightly seeds; check `tests (macos-latest)` and `tests (windows-latest)` on the new head (ci:full is on the PR).
