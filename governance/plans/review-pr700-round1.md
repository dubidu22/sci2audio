# Review PR #700, round 1 (batch B-D1, #678, #686)

Thread: review-docs-b-d1 (Opus 5.5). Head reviewed: 1636cc7 (one commit on `main` 9066c3d). Date: 2026-11-20.
**Critical: no** (CRIT-01: wording in `docs/design/PRODUCT.md`, the design prototype and `CHANGELOG.md`; no KB process, contract or architecture document, no golden file, no code). Plan `plans/docs-b-d1-plan.md`, section 3, approved as D-854.

**Verdict: changes requested** (0 must-fix, 1 should-fix, 3 notes).

## Verified

- Diff `git diff 9066c3d...1636cc7`: three files, +4/−2, nothing else (`CHANGELOG.md` +2, `docs/design/PRODUCT.md` +1/−1, `docs/design/prototype/app.js` +1/−1).
- `PRODUCT.md:40` against the code: `app/updates.py` has `enabled: bool = False` (off by default), `DAY = timedelta(days=1)` and `due()` (at most one request a day), one `GET` of `RELEASES_URL` (`api.github.com/repos/dubidu22/sci2audio/releases/latest`) with only `User-Agent: sci2audio` and `Accept` (no version, no identifier, cookies and `.netrc` cleared), and it downloads nothing. The wording follows `privacy.updates` (`web/strings/en.toml:480`) and the Settings switch (`settings.updates_switch`, `:587`). Correct.
- `prototype/app.js:578`: only "no update check" → "no update check unless you turn it on" and "keine Update-Prüfung" → "keine Update-Prüfung, außer du schaltest sie ein", the words the plan names.
- `CHANGELOG.md`: both lines sit under `## [Unreleased]` > `### Fixed`, after the #684 line, one per PR, in the section's style. #671 ("layout: accent glyphs join their letter and tall pieces stay on their line", Closes #125 #126, merged 20 Nov 14:49 UTC) and #682 (Closes #181 #54 #59 #55 #56, merged 20 Nov 17:30 UTC) both merged after the v1.4.0 tag (19 Nov), so Unreleased is right. Issue numbers match each PR's closing keywords; the content matches audit F3 and the issue titles.
- #678 and #686 acceptance criteria: met except for the stale line in S1. PR body: `Closes #678`, `Closes #686`, test summary, licence, risk, out of scope.
- Merge with #701: `git merge-tree 1636cc7 b6905d2` is clean (hunks at 37–43 and 52–58/75–81).
- Local run in a fresh `/tmp/review-700` at 1636cc7: `uv run ruff check` clean; fast suite `-m "not slow and not benchmark and not browser" -k "not espeak" -n auto`: 8638 passed, 6 skipped, 6 xfailed.
- CI on 1636cc7: `CI passed`, `tests (ubuntu-latest)`, both Chromium browser shards, `lint and layers`, `licences`, `governance pr checks` green.

## Findings

### Should-fix
- **S1 (stale-doc-claim). `docs/design/PRODUCT.md:67` still says "There are no network calls except the voice download the user starts."** It is in the same file, under "Hard technical rules", 27 lines below the new line 40. #678's grep for "update check" does not find it, but it makes the claim #678 removes. `CLAUDE.md:11` on `main` already lists the update check the user turned on. Failure scenario: a reader of the product record, or a thread that takes its rules from it (`PRODUCT.md` is the binding product truth under D-663), finds two statements that disagree. Line 67 is the stricter one, so the reader writes "the only network call is the voice download" on a new page or in a test, or flags the update check as a breach of the hard rule. Fix: make line 67 say what `CLAUDE.md:11` says, for example "There are no network calls except the voice download the user starts and the update check the user turned on."

### Notes
- N1: `prototype/app.js:579` is still headed "The one exception: the voice download you start" / "Die eine Ausnahme: der Stimmen-Download, den du startest", right below the line that now admits a second call. The prototype is a frozen design record (b4a7523) and the plan limits the change to the words in line 578, so I don't ask for a change. If S1's fix touches the file anyway, "one exception" could become "the exceptions you start".
- N2: the #682 line's "Headings set with a rule … are read where they belong" fits #54 (numbered headings) well. It fits #181 less well: there a narrow rule joins the line above it, and on the issue's own page it marks no heading (#682 body, AC 2). It does not mislead a listener, so it can stay.
- N3: the German list "keine Update-Prüfung, außer du schaltest sie ein, kein Konto" puts a clause inside a comma list. It reads correctly. Only the prototype shows it.

Verdict: changes requested for S1, one line in `PRODUCT.md`. Round 2 only needs to check that line and the diff.
