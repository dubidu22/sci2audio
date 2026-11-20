# PR #353, answer to review round 1

New head: da3ac78 (on e0a2bce, main 79d0cdb merged in earlier). Every item of `review-pr353-round1.md` is fixed; nothing is deferred.

- **B1, fixed:** `_rebuilt_label` maps a label through the script only for `BlockKind.CAPTION`. Every other kind (footnote mark, formula number, heading number, list marker, placeholders) keeps the old rule: the label stays if the new text prints it, and otherwise it goes. The docstrings of `rebuilt_from_script` and `_rebuilt_label` now say captions, and so does the PR body. Tests:
  - (a) `test_a_footnote_mark_is_not_mapped_into_its_introduction`, parametrised over English "† Note." and "* Note." and German "∗ Hinweis.": the rebuilt note has label "". All three fail on f5b2a37 and pass on da3ac78.
  - (b) `test_every_corpus_document_reads_the_same_on_a_second_run` asserts that every label the rebuild changed belongs to a caption. It fails on f5b2a37 at maass and passes on da3ac78.
- **N1, fixed:** the `piece.pause` skip is removed, because a pause has an empty span and no text, so it reads as kept and adds "". The `_mapped` docstring says so. The test is renamed `test_a_label_covered_only_by_a_pause_goes`. The final strip/one-line/in-text checks stay, with a comment marking them as defensive (`Block` raises on such a label; a mapped one is dropped instead).
- **N2, done:** the corpus second-run test is parametrised over all 13 corpus documents (8 papers, the EPUB, 2 Markdown, 2 text). All pass.

Checks on da3ac78:
- Fast suite (`HYPOTHESIS_PROFILE=ci`, -n 8): 5204 passed, 1 skipped, 2 xfailed (#320, #321).
- ruff, ruff format, lint-imports and deptry are clean.
- Nightly seeds 555 and 8080 on runner, conformance and the new unit file are clean.
