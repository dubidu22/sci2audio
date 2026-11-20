# Review of PR #279, round 1 (#271 nested citations)

Reviewed head ad62290 against main d91a074, 14 Nov 2026. Approved plan: D-541 (plans/issue271-nested-citations-plan.md).

## Verdict

The change does what D-541 asks, and all three conditions hold. Before merge: one fix (M1), four test additions (S1 to S4), one follow-up issue (D1). PR #277 must also be merged into main, then main into this branch, with the timing case moved onto the ratio helper.

## What I checked, and how it came out

- **Corpus (condition 2):** `sci2audio script` on all 13 corpus documents, run on main (via PYTHONPATH on a main worktree) and on the PR. All 13 scripts and 26 reports are byte-identical.
- **Re-judgement sees only this step's own inner decisions (condition 1):** `_cited_once_inner_citations_go` writes in `decided[child.open]` and nothing else, and copies only `text[open-300 : close+1]`. The look-back holds raw text, and no other step's edits reach it. OK.
- **Prose residual keeps its prose (condition 3):** "It holds ((Smith, 2019) see also Table 2) here." reads "It holds (Smith see also Table 2) here." on both runs, as on main. German "Es gilt ((Müller, 2019) siehe auch Tabelle 2) hier." is the same. Pinned in both regression files. OK.
- **Hand probes:** about 100 shapes in English and German, through the citations step alone and through the whole chain, two runs each, main against PR. Shapes covered: triple and quadruple nests, nests in subject and noun position, prose residual, semicolon lists, mixed bracket kinds, line breaks inside nests, glued pages, abbreviations (cf., e.g., vgl., z. B.), umlaut capitals, "n.d.", "WHO". The PR adds no second-run change that main lacks. Every remaining unstable shape is the same on main (M1, D1, #102).
- **Random fuzz:** 3,000 random nested texts (en and de, depth up to 4), both runs, main against PR. No new instabilities. 42 that are unstable on main are fixed. Where main was already stable but the PR reads differently, every case I sampled is an empty "()" bracket that now goes, as plan step 2 says.
- **English first run of non-nested citations:** this cannot change. A bracket with no round inner bracket returns at `if not inner` and keeps its old decision. `_subject` gets the same name spans as before. The 13 corpus scripts and the existing regression cases are unchanged.
- **Termination and linear time:** decisions are made in a loop, with no recursion. A 5,000-deep nest runs in 0.55 s (main 0.41 s). Timing the step alone, best of 3 with gc off, on 1,000, 2,000, 4,000 and 8,000 copies:

  | shape | PR 8,000 | ratio 8,000/1,000 | main 8,000 |
  |---|---|---|---|
  | `Text ((Smith, 2019) Jones, 2020) here. ` | 0.86 s | 7.4 | 0.42 s |
  | triple nest | 1.24 s | 8.4 | 0.52 s |
  | subject nest | 0.71 s | 8.4 | 0.38 s |
  | prose residual | 0.40 s | 8.0 | 0.30 s |
  | `(cf. (Smith, 2019) Jones, 2020)` | 0.86 s | 8.2 | 0.38 s |

  Linear, at about twice main's constant.
- **Suites:** fast suite (ci profile) 4,304 passed, 1 skipped. ruff, lint-imports and deptry are clean. Nightly profile on the citation, link, property, contract and second-run tests with my own seeds 4242 and 271: 612 passed each. CI on ad62290 is green.
- **Hand mutations** (18 mutants of the new code, run against both citation test files and tests/regression): 7 killed, 11 survived. Survivors 1 and 2 are equivalent or nearly so (see below). The others lead to S1 to S4.

## Findings

### M1: inner square-bracket citations are not written in (fix, or defer with an issue and a reason)

`inner = [child for child in node.children if text[child.open] == "("]` skips square children. A nest holding a numeric citation therefore still needs two runs, in both languages, just as on main:

- en `It holds ((Smith, 2019) [3] Jones, 2020) here.` reads `It holds ( Jones, 2020) here.`, then `It holds here.`
- en `It holds ([1] Jones, 2020) here.` reads `It holds ( Jones, 2020) here.`, then `It holds here.`
- de `Es gilt ((Müller, 2019) [3] Schmidt, 2020) hier.` reads `Es gilt ( Schmidt, 2020) hier.`, then `Es gilt hier.`

Plan step 2 speaks of "inner citations", numeric ones are citations too, and #271 asks that a nested citation read the same on a second run. Write in the decided edits of square children as well, and pin all three shapes on both runs. The mutant `inner = list(node.children)` survives today, so no test has a square child in a nest. If a square child's reading cannot be written in (a reading longer than the printed bracket), defer it with an issue and say why.

### S1: the guards in `_cited_once_inner_citations_go` are never reached by a test

These mutants all survive: dropping the clamp `start, end = max(...), min(...)`; dropping either half of `start > end or len(replacement) > end - start`; writing blanks instead of `replacement.ljust(...)`. Add a test that reaches each guard and the write-in of a non-empty replacement. If a guard cannot be reached, remove it and give the reason in one line.

### S2: no test pins a page bracket glued after a nest

The mutant `end = node.close + 1` in place of `self._glued_page(...)` survives. Pin `It holds ((Smith, 2019) Jones, 2020)[p. 5] here.`, which reads `It holds here.` on both runs (main: `( Jones, 2020)[p. 5]`, then `It holds here.`).

### S3: an empty nest in subject position

`((Smith, 2019)) is cited.` reads `() is cited.` on both runs, here and on main (de: `((Müller, 2019)) zeigt das.` reads `() zeigt das.`). It is stable, but an empty bracket is read: the #278 family. The mutant that removes such a bracket instead of `return None` survives. Pin today's reading in a unit test that names #278, and add the two shapes to #278.

### S4: the linear-time case does not yet catch the slow version

The mutant `shift = 0`, which copies the whole block for each nest, survives the 2,600-nest absolute-time case. The PR already plans to move the case onto #277's ratio helper. Before merge, show in the round-2 answer that the ratio check fails with `shift = 0` (run it once by hand), and keep the 2,600-nest case.

### D1 (defer, new issue for v1.2): residual that is a mixed list or a bare year

These take two runs, the same as main. They fall outside D-541, which covers only an all-citation residual:

- `It holds ((Smith, 2019) Jones, 2020; see Table 2) here.` reads `It holds ( Jones, 2020; see Table 2) here.`, then `It holds ( see Table 2) here.`
- `Jones ((Smith, 2019) 2020) found it.` reads `Jones ( 2020) found it.`, then `Jones found it.`

File one issue (textprep, v1.2) with both shapes, and link it in the PR body's out-of-scope list.

### Noted, no action

- `It holds ((Smith, 2019) https://x.org, 2020) here.` needs two runs through the whole chain, here and on main, because the link step removes the URL. D-541 condition 1 rules this out of this PR on purpose, and #102 (v1.0.1) covers it.
- Mutant `if not all(cited)`: equivalent. `parts` is None only when nothing in the bracket is dated, and then no inner citation exists.
- Mutant `continue` in place of `return None` for an inner bracket kept as printed: equivalent on every shape I tried ("((Smith) Jones, 2020)" stays as printed either way).
- Mutant with the role always "is part of the sentence": it changes only the reason text. A reason assertion is optional.
- `((Smith, 2019) Jones, 2020; Lee, 2021) found it.` now reads "Jones and Lee found it.", where main read "( Jones, 2020) found it." and then "Jones found it." This is better and stable. It is worth a line in the PR table.

## Merge conditions

1. M1 fixed, or deferred with an issue and a reason. S1 to S4 done. D1 issue filed and linked.
2. PR #277 merged into main, main merged into this branch, the timing case on the ratio helper, and S4 shown.
3. Corpus byte check redone after the merge of main. CI green.
