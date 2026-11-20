# Review of PR #137, round 1 (closes #129)

Reviewed head: fdade80 (tests only: tests/browser/conftest.py, tests/browser/test_axe.py, tests/unit/test_web_security.py). Base 1064e18.

## Verdict

Clean. No blocking findings. Merge after the branch is brought up to date with main (update-branch merge commit) and CI is green on the new head.

## What I ran (Linux container, Chromium 1243 via SCI2AUDIO_CHROMIUM)

- ruff check, ruff format --check, lint-imports (3 contracts kept), deptry src: all clean.
- `pytest -m browser`: 18 passed.
- Fast suite as in CI (`not slow and not benchmark and not browser`): 2095 passed. The three SIGINT timing tests named in the PR body passed; no flake in this run.
- Browser and fast tests together in one session (`not slow and not benchmark`): 2113 passed. This is the mix that broke `test_a_header_sent_twice_is_refused` before.
- Nightly Hypothesis profile: not run; the PR changes no code and no property test.

## Mutation checks

1. Removed the three new lines in `axe_problems` (wait, style check, assert): the new test fails with exactly main's finding, `target-size (serious) [['.skip'], ['.home']]`.
2. Removed only `wait_for_load_state("load")`: the new test fails with "the page's stylesheet is not applied", so the style assertion is a real guard and its message is the clear one.
3. Put main's `test_web_security.py` back and ran `test_axe.py::test_the_check_finds_a_real_problem` followed by `test_web_security.py`: RuntimeError from asyncio.run, 1 failed. With the PR: 47 passed.

## Points checked

- Playwright's click still waits for an initiated navigation to commit (no_wait_after default), so `wait_for_load_state("load")` waits on the new document, not the old one. Mutation 1 confirms it in practice.
- The delayed stylesheet in the new test reaches the server again after the click (the browser revalidates `app.css`, and the conditional request goes through `StaticFiles.get_response`), so the 1.5 s delay is real; mutation 1 proves it.
- The live server runs in the test process, so monkeypatching `StaticFiles.get_response` affects it and is undone at teardown.
- All six templates render `base.html`, which holds `<a class="skip">`, so every page `check_axe` sees has the element the style check reads.
- CI at fdade80: all twelve checks green, including tests on ubuntu, macOS and Windows and "browser (Linux, Chromium)".

## Nits (no change needed)

- N1: if a future page has no `.skip`, `document.querySelector('.skip')` is null and the evaluate throws a JavaScript TypeError instead of the readable assertion. No page today lacks it.
- N2: in `test_a_header_sent_twice_is_refused`, an exception inside the worker thread goes to pytest's unhandled-thread warning and the test fails on `seen == []`; a hung call passes `join(10)` silently and fails the same way. The test still fails in both cases, only with a less direct message.
