# Review PR #371, round 2 (textprep follow-ups PRs 5–7)

Head reviewed: 0f43871 (one commit on 245323a). Answer: plans/review-pr371-round1-answer.md. Critical.

**Verdict: not approvable yet. One should-fix (S1), caused by the round 1 fix. Three nits.** Every heavy check already passes on 0f43871, so round 3 only needs to re-check the S1 fix: the fast suite, the S1 rows, one mutant and three-system CI.

## Round 1 item

**S1 is fixed for the reported rows.** These now read the same on both runs:
- "Text (more)", "Text (Figure 3)", "Text [Figure 3]", "Text, (more)" and "Text (mehr)";
- "Text and (more)", "Text ((more))", "Text (a)(b)";
- a line-broken "Text↵(see …)(more)" and two glued links.

The start-of-text row and "Text (see …)(Smith, 2019) more." are unchanged, as the answer says.

## Fix list

### Should-fix

**S1. At a block's end, a removed link bracket now leaves a trailing space in the script.** The new check `text[end : end + 1] in "(["` is true when `end == len(text)`, because the empty string is in every string. So every link bracket that ends its block keeps the space before it:

| printed (whole block) | script on main 82d9e0d | script on 0f43871 |
|---|---|---|
| `Text (see https://example.org)` | `ScriptPiece(text='Text', span 0–4)` | `ScriptPiece(text='Text ', span 0–5)` |
| `Text [see https://example.org]` | `'Text'` | `'Text '` |

The spoken text strips it, so the regression cases and the second-run check cannot see it. But the script piece, its span and its chunk key change for a common shape: a paragraph or footnote that ends with "(see https://…)". This first-run change is not listed. The 13 samples do not contain the shape.

Fix: test for the opening bracket itself, `text[end : end + 1] in ("(", "[")`, or check `end < len(text)`. Add a unit test on the script pieces, not the spoken text, for both rows above. It must fail on 0f43871.

### Nits

**N1. Three new checks that no test pins.** Each mutant below passes every test but changes a reading:
- `_closed_before` without the glued-bracket check: "Text (see https://example.org/a)b)(more) here." reads "Textb)(more) here." (PR: "Text (more) here.").
- `_closed_before` without the depth count: "Lee (see https://x.org/a(b)(Smith, 2019)." reads "Lee ." (PR: "Lee."). The unit rows end with "it holds", not with a full stop.
- `_listed_inner_names` with text allowed before the inner bracket: "(e.g. (Smith, 2019); Jones, 2020) is cited." reads "is cited." (PR: "Jones is cited.").

Add the three rows to `test_textprep_links_in_brackets.py`. A fourth survivor is defensive: `handled[0][2] is not EditKind.REMOVE` changed no reading in about 140 shapes.

**N2. A spaced slash after a link at a bracket's start stays.** "It holds (see https://example.org / Lee, 2019) here." reads "It holds ( / Lee, 2019) here.", the same on main, because `_leading_join` leaves "/" out of the joins. Including "/" would read "It holds here.", as #337 reads "and". Either take " / " when it has spaces on both sides, or say in a comment why "/" stays.

**N3. Fill in the PR table.** Add the S1 rows and the block-end row once it is fixed.

### Deferred

#372 (from round 1).

## Checks on 0f43871

- Fast suite (`HYPOTHESIS_PROFILE=ci`): 5497 passed, 1 skipped. This includes the English and German regression cases and their second-run check.
- Probes: about 140 shapes, whole chain twice, main 82d9e0d vs PR. There are no second-run differences except #358's `y < 2x`, which is on main too. The #359, #361 and #368 probe sets read as before.
- The 13 corpus documents: all 39 files are byte-identical to main 82d9e0d.
- Mutation-style breaks: 13 of 18 fail the tests:
  - `_closed_before` removed, or without its open-bracket check;
  - `_leading_join` removed;
  - the S1 space removed;
  - `_link_starts` emptied;
  - `edge` fixed to `kept`;
  - the reference-word path removed;
  - the leading space removed;
  - the separator check removed;
  - the year shell removed, or with any closer;
  - `_clear_of_links` keeping overlaps;
  - the German quote-at-end check removed.

  Survivors: see N1 and N2.
- Timing (n, 2n, 4n, 8n, at 150 to 1200 deep or long): every shape grows linearly, as on main, within the D-599 cap. A link nest up to 8000 deep runs in 0.86 s against main's 0.49 s, still linear. No shape grows faster than on main.
- Nightly seeds (`HYPOTHESIS_PROFILE=nightly`; links, links in brackets, citations, utterances, conformance, runner): 2024 and 123456 clean, on top of the author's 7, 555 and 8080.
- Commit messages carry no closing keywords.
- CI with `ci:full` on 0f43871: tests on ubuntu-latest, macos-latest and windows-latest, browser, lint and layers, licences, security and CodeQL are all green. `mergeable_state` is clean.
