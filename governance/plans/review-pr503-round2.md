# Review PR #503, round 2 (#480 C2: a cut sentence is one sentence on the page and for markers), final round

Head reviewed: deb732f, the round 1 fix commit on 763595d. It changes tests only, two files with +41 lines; `git diff 763595d deb732f -- src` is empty. Round 1: plans/review-pr503-round1.md. The author's answer: plans/review-pr503-round1-fixes.md.

**Verdict: approvable, and merged.**

## The fixes
- **S1.**
  - `test_web_listen.py::test_a_mark_across_the_cut_of_a_cut_sentence_is_drawn_in_the_joined_sentence`: a citation cut lies across the join, and the joined sentence's parts are pinned exactly.
  - `test_web_player.py::test_a_word_joined_at_the_cut_of_a_cut_sentence_shows_joined`: a line-end hyphen at the cut shows as one word.
- **S2.** My probe case is added to `test_a_join_follows_only_the_chunk_the_page_draws_just_before_it`. It expects elements `s0 s0 s2` and sentences `[0, 1, 2]`.
- **Not done (optional):** overlapping spans in the property generator. Accepted. The overlap rule is now pinned by a direct case, and the generator change would change the model for every other check. No issue is filed for it.

## Final-round checks on deb732f
- **Clean run:** `tests/unit/test_web_*.py`, 710 passed, 3 skipped.
- **Mutation re-run** (same scripts, `scratchpad m503/run.sh`):

  | mutant | killed by |
  |---|---|
  | C1 | the new mark test |
  | C2 | the new hyphen test |
  | C4 | the overlap case |

  C7 and C11 still survive, as argued in round 1: both are equivalent.
- **Totals over both rounds:** 21 of my mutants (19 killed, 2 equivalent) and the author's 17 (all killed).
- **Nightly seeds** 2024 and 123456 on `test_web_player.py`, `test_web_joined.py`, `test_web_listen.py` and `test_web_markers.py`: 128 passed, 1 skipped for each seed.
- **Linux CI on deb732f:** `tests (ubuntu-latest)`, browser (Chromium), ZAP, CodeQL, licences, lint and layers, security and `CI passed` are green. The PR is non-critical, so no three-system run is needed.

## Merge
- **Main had not moved:** it was 3c7482f, which is the PR's base.
- **Squash-merged**, pinned to deb732f, with `Closes #480` in the squash message. Main is now **344db7a**, and its tree is identical to the reviewed head's.
- **#480 is closed.**
