# Answer to review of PR #583, round 1

Pushed: the merge of main **a19662f**, then one fix commit **bd2043a** (head). ci:full was added again for the three-system run.

- **R1 done.** I merged main at 0a72357 with a merge commit, never a rebase. CHANGELOG.md conflicted only in `### Fixed`: both lines are kept, #493 first and then #445/#449, with no other change.
- **R2 fixed.** The new test `tests/unit/test_web_documents.py::test_another_error_while_placing_a_newer_name_is_tried_once`: `os.replace` raises ENOSPC for `"<U+1FAE8> My Paper.pdf"`. It is asked exactly once (`[stored_name(sent)]`), the answer is 507 `disk-full`, no `.part` is left, and no `source/` file is left. Mutant q17 (`if error.errno != errno.EILSEQ:` → `if False:`) now fails it. Without the mutant it passes.
- **R3 done.** The PR body's "Out of scope" now links #584.

Checks: ruff and format are clean. web documents, output retried names, app audio faults and app job pass locally (92).
