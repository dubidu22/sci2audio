# Review PR #371, round 1 (textprep follow-ups PRs 5–7: links #326 #337, nests #338 #339 #278, German stop #342)

Heads reviewed:
- 4a47d47 (base main 3fcba56).
- 245323a (main 82d9e0d merged in). `git diff 82d9e0d 245323a` equals `git diff 3fcba56 4a47d47`, except for one CHANGELOG context line.

Plan: plans/textprep-v12-pr5-7-plan.md (D-630). Critical.

**Verdict: not approvable yet. No blocker, one should-fix (S1). One item deferred (#372).**

## What I checked

- **Change against the plan:** all six issues and the fuzz-found `_clear_of_links` change. Commit messages carry no closing keywords; the PR body closes #326 #337 #338 #339 #278 #342.
- **Fast suite on 4a47d47:** 5448 passed, 1 skipped. It includes the regression cases and their second-run check.
- **Probes:** about 110 shapes, whole chain twice, against main 3fcba56. Every PR reading is the same on both runs, and `(Smith, 2019, https://example.org)(Smith, 2019)`, which differs on main, now agrees.
  - Every first-run change is one of the PR table's classes, with one exception (S1). The changes covered: links glued to a following bracket; a join word after a link at a bracket start; a numeric bracket after a removal; a reference word before such a bracket (`See Ref. (Smith, 2019) [3, 4]` now keeps `references 3 and 4`; main dropped them); year shells at depth 2, 3 and 4; the subject row; the German closing quote („“, »«, ›‹, ‚‘, «»).
  - These stay as before: `„Dr.“ Müller`, `„Nr.“ 5`, a lower-case or comma after the quote, ASCII `"usw."`, English `“etc.”`, `((Smith, 2019) 2020 data)` and `(model (Smith, 2019) 2020)`.
- **Nest work cap and timing:** n, 2n, 4n and 8n copies or depths, PR vs main, for year-shell depth (up to 1200), glued link and citation rows, link join rows, link nests (up to 8000 deep), URLs full of ")(", subject rows and nests, numeric-after-removal and the German quote. All grow linearly, as on main.
  - The subject nest grows at about the same rate as main.
  - Many glued link brackets cost about twice main's constant (0.33 s vs 0.14 s at 2000 links), still linear.
  - No shape grows faster than on main.
- Samples, mutants and nightly seeds are left for the approving round.

## Fix list

### Should-fix

**S1. A link bracket glued to a bracket that stays takes the space before it, so the kept bracket is glued to the word.** `_closed_before` now ends the URL at ")(", which is right, but the removal still takes its leading space. These read the same on both runs:

| printed | main | PR |
|---|---|---|
| `Text (see https://example.org)(more) here.` | `Text here.` | `Text(more) here.` |
| `Text (see https://example.org)(Fig. 3) here.` | `Text (. 3) here.` | `Text(Figure 3) here.` |
| `Text (see https://example.org)[Fig. 3] here.` | `Text (. 3] here.` | `Text[Figure 3] here.` |
| `Text [see https://example.org](more) here.` | `Text [ here.` | `Text(more) here.` |
| `Text, (see https://example.org)(more) here.` | `Text, here.` | `Text,(more) here.` |
| `Text (see https://example.org)(a) and (b) here.` | `Text and (b) here.` | `Text(a) and (b) here.` |
| `Text (siehe https://example.org)(mehr) hier.` | `Text hier.` | `Text(mehr) hier.` |

The PR table's row starts the text with the bracket (`(see https://example.org)(results) it holds.` → `(results) it holds.`), so it does not show this. Fix: when the removal ends right before an opening bracket that stays, keep one space between the word before and that bracket. For example, take the space after the link bracket instead of the one before it, as the citations step does for its glued siblings. The rows above should then read `Text (more) here.`, `Text (Figure 3) here.`, `Text, (more) here.` and so on, on both runs. Add these rows (en and de) to `links-a-link-bracket-glued-to-the-next-bracket` or the unit file; they must fail on 245323a. Keep the start-of-text row as it is.

### Nits

None.

### Deferred

- **#372** (v1.2, lane:textprep): a subject nest with more than its first citation in brackets loses names, the same on main. `((Smith, 2019); (Lee, 2018); Jones, 2020) is cited.` reads `is cited.`, and `(Jones, 2020; (Smith, 2019)) is cited.` reads `Jones is cited.`. D-605 asked only for the first-citation row, which this PR fixes.

## Next

Round 2 should be the approving round: the S1 rows must fail on 245323a, then the 13 samples, mutants, nightly seeds and three-system CI (`ci:full`) on the fix head.
