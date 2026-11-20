# Review PR #489, round 2 (web lane v1.3 PR A: #461, #462, #471, #472)

Head reviewed: b847ce8, the round 1 fix commit on 39e11d3. Round 1: plans/review-pr489-round1.md; the author's answer: plans/review-pr489-round1-fixes.md. Linux CI is green on b847ce8 (`CI passed`, `tests (ubuntu-latest)`, `browser (Linux, Chromium)`, lint and layers, licences, security, CodeQL, ZAP).

**Verdict: approvable, and merged.**

## The fixes
- **S1, fixed.** `_shown` now has its own furniture rule: a REMOVE in a furniture block counts, and any other edit there does not. The rule is named in the `_changes` and `_shown` docstrings and in the PR body, and it has unit tests. Furniture mutants: F1 (the rule returns False), F2 (it returns True) and F3 (the rule removed) are all killed.
- **S2, fixed.** `set()` remembers the element that was focused when P opened the panel. When P closes the panel with the focus inside it, the focus goes back to that element, or the page is blurred if it was the body. My probe at 1024 × 768 (nobody focused, P, P, Space) now gives `aria-expanded` false and the audio playing; on 39e11d3 it gave true and paused. The two new browser tests are `..._gives_the_focus_back_where_it_was` and `..._gives_the_focus_back_to_the_control_it_left`.
- **S3, fixed.** There is now a notice test and a test of a heard versus an unheard footnote move. On b847ce8, M1, M2, M3 and M4 are each killed by the unit tests (`test_web_listen.py`, `test_web_player.py`, `test_web_pages.py`; 92 pass unmutated).
- **N1, done.** The PR body now explains why the corpus check is left out: the hand-made cases cover every branch of `_shown` and kill every mutant.

## Not a finding (no action)
- My round 1 fix list said a close by the toggle, the close button or Esc would keep today's `toggle.focus()`. The new `set()` returns early when the focus is not inside the panel, so a toggle press made without the focus (as in Safari, where a click does not focus a button, #447) leaves the focus where it was. Before this change it moved the focus to the toggle.
  - D1's purpose (#444) is to keep focus that would otherwise be lost. Focus that is outside the panel is not lost, so the change does not hurt.
  - The close button and Esc both act from inside the panel, so they still focus the toggle.
  - A keyboard press on the toggle leaves the focus on the toggle.

## Tests run here
- Browser tests (`test_focus.py`, `test_listen.py`, `test_player.py`, `test_library.py`, Chromium): 60 passed.
- Unit tests: 92 passed, plus the mutant runs above.

## Merge
- **Main has not moved** since 4bb8f81, the base of the branch, so no merge of main was needed.
- **Squash-merged**, pinned to b847ce8: main is now **9377cd8**, and its tree is identical to the reviewed head's. Closed: #461, #462, #471 and #472.
