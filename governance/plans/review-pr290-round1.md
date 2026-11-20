# Review of PR #290, round 1 (issue #286, read-along hyphen display)

Reviewed head: b38951d (base main d91a074). Non-critical (web only, no golden files).

## What was checked

| Check | Result |
|---|---|
| Joins come from the step's own edits, not a second heuristic | Yes: `joined_hyphens` calls `LineEndHyphenStep.find` and keeps its 2-character REMOVE edits (hyphen + line break), which are exactly `_join`'s edits; `_keep` edits are 1 character (line break only). |
| Read-along highlighting still lines up | Yes: spans and chunk numbers are untouched; `shown` only drops characters inside a piece, so every chunk keeps its element. Timing is per chunk (sentence span), not per word, so a joined word cannot split a spoken token. The test with a piece cut between the hyphen and its line break holds. |
| Kept hyphen stays | Yes: "COVID-\n19" shows "COVID-19" (unit test). |
| Categories off restore the printed form | Yes: `characters` in `switched_off` gives "con-tributing" (unit test). |
| Test for "con-tributing" → "contributing" in the view | Yes: `test_a_word_the_hyphen_step_joined_shows_joined_and_a_kept_hyphen_as_printed` (build_view). |

## Corpus comparison (scratchpad script, all 8 papers + EPUB + Markdown + text)

Joins the view shows vs joins the runner accepted (`run_steps`, BUILT_IN_STEPS, default categories):

| Document | view | accepted | view only |
|---|---|---|---|
| acl2023-chi-plue | 140 | 80 | 60 |
| acl2023-hardt-ellipsis | 71 | 58 | 13 |
| acl2023-nowak-prefix-probabilities | 68 | 38 | 30 |
| arxiv2017-maass-privacyscore (de) | 34 | 34 | 0 |
| arxiv2024-arsiwalla-qualia-meaning | 77 | 53 | 24 |
| arxiv2024-liu-orbital-hall | 77 | 77 | 0 |
| joss2021-waskom-seaborn | 9 | 9 | 0 |
| joss2022-biggs-pymedphys | 1 | 0 | 1 |
| EPUB, Markdown, text (4 files) | 2 | 2 | 0 |

Every "view only" join is a line-end-hyphens edit the runner SET ASIDE because an earlier step's edit won (reference-list removal, one citation removal in hardt). Never the other way round.

## Findings

### M1 (must fix): the view joins hyphens the voice never joined

`joined_hyphens` uses `step.find` alone, so it also applies joins the runner set aside. The voice did not read them (the text was removed), but the view now changes the printed text there. Worst case, a URL with a real hyphen at a line end:

- `"See https://www.data-\nbase.org/x for more."` shows `"See https://www.database.org/x for more."`; links removed the URL, the hyphen join was set aside.
- `"See www.mypack-\nage.org ..."` shows `www.mypackage.org`; `github.com/foo/sea-\nborn` shows `github.com/foo/seaborn`.

That is a wrong address on screen, and against the PR's own rule ("a hyphen the step kept, or that the voice did not read, shows as printed"). Fix: take the joins from the settled run, i.e. `run_steps(document, StepContext(document.language), BUILT_IN_STEPS, switched_off=<record's categories>)` and keep the ACCEPTED `line-end-hyphens` edits of length 2. Cost measured: 0.13 s on acl2023-chi-plue vs 0.02 s for `find` alone; fine for a page load. Add a unit test with a URL hyphen at a line end that stays printed (and one join inside a removed citation/reference list, if easy).

### N1 (nit, optional)

The Hypothesis property test now computes its expected text with `joined_hyphens` itself, so it checks no loss or doubling, not the joins. That is fine because the named test checks the joins; no change needed unless M1's rewrite makes it easy to keep the old expectation for documents without line-end hyphens.

## Runs

- Fast suite + ruff + format + lint-imports + deptry at b38951d: all clean; 4,288 passed, 1 skipped (Windows-only junction test).
- Browser suite at b38951d (Chromium 1243): 51 passed.

## Verdict

Changes requested (M1). PR review posted 14 Nov ~13:50 UTC. Main must be merged in (PR #288 landed as 407f5bd).
