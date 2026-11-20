# Review of PR #236, round 2 (#219 language guessing)

Head 87455ed (was 32e720b), base main 3715c38 (unchanged, mergeable clean). **Verdict: approved, merge.**

## Round 1 fix list, checked

1. Boundaries pinned: `test_the_boundaries_of_the_guess` (15+5 de, 14+5 "", 15+6 "", 5+15 en, 6+15 "", 20+0 de, 0+19 ""). Re-ran the three hand mutants (`>= language_words`, `german >= ratio*english`, `english >= ratio*german`, each to `>`): every one now fails the suite (3, 1, 1 failures). File restored.
2. Order property: `test_the_guess_does_not_depend_on_the_order_of_lines_or_pages` (pages reversed and renumbered, lines reversed, outline dropped; equal guess). Done.
3. CLI: `test_the_language_warnings_are_printed_once_and_a_clear_guess_is_not` covers fallback (once, only warning), override from `lang: en` with German prose (once, only warning), clear English (no warning). Done.
4. `--language` help and `JobSettings.language` comment now say "else guessed from the text (en or de)"; CLI help golden updated (script and convert). Done.
5. Override warning ends "(on the command line: --language en)."; tests updated. Done.
6. PR body now says the line is a hint under the voice choice, named in aria-describedby. Done.

## Runs

ruff, format, lint-imports (3 kept): clean. Fast suite 3,655 passed, 1 skipped. CI on 87455ed: all checks green, CI passed success. English scripts: the round-2 diff touches only the report warning text, CLI help and a comment, so the round-1 byte-identity result (all 10 corpus scripts identical vs main) stands.

## Deferred

- #237 (v1.1): normalise stated language tags (en_US, und).
