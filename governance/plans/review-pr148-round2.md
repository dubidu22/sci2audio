# Review of PR #148, round 2: EPUB extraction and cover images (#73, part 2)

Reviewed head 1e17652 (fix commit c2b1771 plus a merge of main), 13 Nov 2026, against round 1
(`review-pr148-round1.md`) and the author's answer (`review-pr148-round1-answer.md`).
Verdict: **approved**. Every round-1 item is fixed with a test; nothing deferred by the author.

## Round-1 items, checked

- **M1 malformed URL**: fixed. My probes: a manifest href `http://[x` is skipped, the cover gives
  None, a chapter link is recorded as `href:http://[abc`, a picture keeps `ref='http://[x'`.
- **M2 non-text codec**: fixed. hex, base64, rot13, zlib, uu, idna and punycode all read
  (UTF-8 with U+FFFD).
- **M3 damaged nav**: fixed. `<li><a>A</li></a>` gives one outline entry, no error.
- **M4 unbounded tags**: fixed. The round-1 case (100,000 tokens × 2,000 children) now peaks at
  40 MB with 200 tags per run. New limit `MAX_TAGS = 200` is a decision next to D-315: the
  coordinator records it in the KB.
- **Mutants**: I re-ran all 49 round-1 mutants plus five new ones on the fixes (the `MAX_TAGS`
  value and slice, the decode fallback, the `urlsplit` guard, the link-copy guard): 52 killed,
  2 survive, both equivalent: `flag_bits & 0x1` (zipfile raises for an encrypted entry and the
  same message results) and the guard that skips copying runs without a link (an optimisation;
  the output is identical). The `<pre>` line-feed rule was removed as equivalent; I agree: an
  empty first piece is never recorded.
- No test was weakened: the four deleted test lines were replaced by stricter ones (the exact
  `MAX_TAGGED` tuple, a wider markup alphabet, a trailing anchor case).

## Checks on 1e17652

- Golden file unchanged and still 368 of 368 lines equal to my independent `xml.etree`
  re-derivation.
- ruff, format, deptry clean; lint-imports 3 contracts kept; fast suite 2306 passed, 55
  snapshots; nightly Hypothesis profile on the three files 117 passed.
- CI on 1e17652: ubuntu, macOS, Windows, browser, lint and layers, security, licences, CodeQL
  green.

## New, not blocking: follow-up issue #158

Memory is now linear in the input but with a large factor: one 8 MB document of 1,000,000
`<p>a</p>` peaks at 540 MB, and with tags near `MAX_TAGS` at 1.85 GB, so a 64 MB document the
D-315 byte limits allow can need several GB. Real books are far below this. Filed as #158
(milestone v1.1, lane:extraction) with three possible fixes for the coordinator to choose from.

## Merge

PR is one commit behind main: update the branch with a merge commit, wait for CI on the new
head, then squash-merge pinned to that head.
