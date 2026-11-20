# Answer to review PR #700, round 1

Thread docs-b-d1. Fix commit 5465f8f on 1636cc7 (one commit; branch otherwise frozen). Date: 2026-11-20.

## Fixed

- **S1 (stale-doc-claim):** `docs/design/PRODUCT.md:67` now reads "There are no network calls except the voice download the user starts and the update check the user turned on.", as `CLAUDE.md:11` says. A grep of `docs/design/*.md` for "no network" and "only network" finds no other such claim (`IMPLEMENTATION-PROMPT.md:3` says "no network calls" as a rule for the issue planning of 15 Nov; it is a frozen brief and states the rule, not the product's behaviour, so it stays).

## Not changed (notes)

- **N1:** `prototype/app.js:579` ("The one exception: the voice download you start") stays. The prototype is a frozen record of b4a7523, and the plan limits the change to the words #678's grep finds; S1's fix does not touch that file.
- **N2:** the #682 line stays as written; it tells a listener what changed and names every issue.
- **N3:** the German clause stays; it reads correctly and only the prototype shows it.

## Checks

`uv run ruff check` clean; a one-line docs change, so the fast suite was not re-run (round 1 ran it on 1636cc7: 8638 passed).
