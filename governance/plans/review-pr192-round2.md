# Review PR #192, round 2

Head reviewed: 78caf27. I merged main (255ce4a, #188) into the branch with the update-branch
API, which made 7665c37. Its tree (5a4b73f0) is byte-identical to the merge I tested locally.

## Each round-1 finding checked again

| Finding | Status | How I checked |
|---|---|---|
| M1 | fixed | My probe: "1984 …" now gets the label ""; "2. Real." gets "2"; "3" gets "3"; "*Starred" gets "" (the mark is glued to the word, which is correct by the rule) |
| M2 | fixed | `f(x)=\sin(x)` gets ""; `y = a(2)` gets "" (no space before the bracket); `y = a (2)` gets 2; `\tag{3}` gets 3; `\tag{x}` gets "" |
| M3 | fixed | Figure 2 and Figure 3 now have one caption each and point at the right picture; a two-paragraph figcaption stays one caption; two captioned tables stay apart |
| S1 | fixed | `# $E=mc^2$` is a HEADING with a section; `## Intro[^a] and $x$` is a HEADING titled "Intro and x" |
| S2 | fixed | My two surviving mutants are now killed |
| S3 | fixed | "Intro1" gives the title "Intro"; `1<a>*</a>.2 Intro` gives the title "1.2 Intro" with no label (the label is not in the text, so the kept check is live, as the author says); a heading that is only a mark keeps its text |
| S4 | fixed in layout; inline runs deferred to #193 | A hidden line after a `br` is its own FURNITURE, a shown line after a hidden one starts again, and a hidden `<p>` with a `br` stays one FURNITURE block |
| N1–N4 | done or explained in the PR body | N3 (any `nav` is FURNITURE contents) refines D-411, so it needs a KB entry from the coordinator |

## Mutants

Nine new mutants on the round-2 rules were all killed:

- `reversed` firsts
- `k not in heads`
- the hidden check on `br` lines
- `opens`
- headed maths
- noteref runs left out of the title
- `_opens_with`
- `\tag`
- any `nav`

## Checks on the merged tree (7665c37 = local 967cb61, same tree)

- Regenerated from scratch: `test_layout_corpus.ambr` sha256 cc276ec4… (unchanged from main) and
  `test_layout_tagged_corpus.ambr` 75336e9a… (unchanged from round 1).
- Fast suite: 3108 passed, 1 skipped (Windows only); 60 snapshots.
- ruff and ruff format are clean.
- Nightly Hypothesis on the three layout test files: 86 passed.
- Timing: The Time Machine ×100 took 0.54 s, against 0.004 s for one copy (linear).

## Verdict

Clean. I merge once CI is green on 7665c37.
