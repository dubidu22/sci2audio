# Review PR #690, round 2 (batch B-P2, #684)

Thread: review-plugins-b-p2 (Opus 5.5). Head reviewed: 0c78cc1 (one fix commit on f7d8898). Date: 2026-11-20.
**Critical: yes** (CRIT-01, a safety mechanism of the text-step plugin interface). Answer read: `plans/answer-pr690-round1.md` (5eaf784).

**Verdict: approved** (0 must-fix, 0 should-fix, 1 note). Before merge: the author merges main in, and a green three-system `ci:full` run on that head (CRIT-02, D-580). This round ran on Linux only.

## Round 1 findings

- **M1 fixed.** In `textprep/plugins.py`, `step_problems`, the entry-point-name check and the built-in-id check now run inside `_made`, in the loading worker and inside its `try`. `_step` is now only the worker call with its time limit. `taken` is only read in the worker; `_load` never changes it.
  - Once `step_problems` passes, `_GuardedStep.keep_plain_copies` stores plain copies: `str.__str__` returns an exact `str` without calling a subclass's override, `languages` becomes a tuple of exact `str`, and `api_version` becomes `TEXT_STEP_API`. So `found.setdefault`, `sorted(found)`, `PluginInfo` and `handles` in the caller and the runner touch only built-in values.
  - This is the root fix for the kind (unguarded-plugin-code) and its check. T8 is `test_a_broken_plugin_is_a_problem_and_the_others_still_load[entry13-RuntimeError: no repr]`. T9 is `test_a_plugin_whose_version_check_hangs_is_left_out`. T10 is `test_a_plugin_s_id_and_languages_are_kept_as_plain_copies`, with a str subclass whose `__hash__` and `__lt__` raise. All three are present under the node IDs in the PR body.
  - My round-1 probes, rerun at 0c78cc1:
    - the raising `__repr__` id is now `PluginProblem("failed while its attributes were read: RuntimeError: …")` at 0.00 s;
    - the blocking `__ne__` on `api_version` is now "took longer than 0.2 s to load; left out" at 0.20 s.
  - The move departs from the plan text and stays within D-845; the answer says so.
- N1 is Issue #693 (v1.4, lane:textprep, risk:high) and N2 is #694 (v1.4, lane:textprep, risk:low); both are open. N3 and N4 are unchanged, with reasons I accept.

## Verified

- Diff f7d8898..0c78cc1 touches only `src/sci2audio/textprep/plugins.py`, `tests/unit/broken_text_plugins.py` and `tests/unit/test_textprep_plugins.py`. No test line is removed or changed (additions only). `_GuardedStep.find` is not touched in this round, so the `find` outcomes and the #676 tests are as in round 1.
- Comments: the new ones give the reason. The rejection parameter comment and the `keep_plain_copies` and `_made` docstrings narrate nothing and carry no review tag.
- Local run (macOS M4, fresh worktree at 0c78cc1): ruff check clean, ruff format --check clean (385 files), lint-imports 3 kept, deptry clean. Fast suite `-k "not espeak"`: 8595 passed, 6 skipped, 6 xfailed. The two Hypothesis core tests that failed for the author on `too_slow` passed here (no load); I saw no failure.
- CI on 0c78cc1 (Linux): `CI passed`, `tests (ubuntu-latest)`, `lint and layers` and `governance pr checks` pass.

## Findings

### N1 (note): a language that is not a str is now rejected with a technical message
`plugins.py`, `keep_plain_copies`, `str.__str__(language)`. `step_problems` accepts any element for which `str(lang)` matches a primary tag, for example an object whose `__str__` returns `"en"`. Such a plugin loaded at f7d8898. It is now rejected with "failed while its attributes were read: TypeError: descriptor '__str__' requires a 'str' object but received a 'Obj'" (my probe). Rejecting it is right, since the contract says languages are tags. The message would be clearer if `step_problems` required `isinstance(lang, str)` and said "languages must be … tags". That changes the text-step interface's checks, so it belongs with #693 or a later PR. No change asked.

Handoff (THR-07): goal: PR #690 to merge. Done: round 2 approved. Next: the author merges main in (c4c2de8) and runs `ci:full`; the review thread checks the merge diff and the three systems on that head, then merges on the coordinator's go.
