# Review PR #377, round 2 (textprep batch 2 PR 1: keys #254, unheaded reference list #92)

Head reviewed: 739a6ac. That is fix 3f757a8 on a578dc0, with main 514dc2f and c841f3d merged in. Round 1: plans/review-pr377-round1.md. Critical.

**Verdict: approvable at 739a6ac.** It closes #254 and #92. Three unpinned guards are filed as #383, which is test-only and fits PR 3. Nothing is merged.

## Round 1 items

- **B1, fixed.** A key bracket counts as a citation only if every key in it is printed as an entry label at a line's start, followed by an author ("[MH17] Maass, M.: …", "[Knu84] D. Knuth. …"). Look-alikes stay excluded in any case. I probed 19 rows (en and de) in four document shapes (a numbered list, a headed key list, an unheaded key list, no list), on both runs, against main c841f3d:
  - The round 1 rows "[Mn12]", "[Al13]", "[Fe23]", "[EU27]", "[UK21]", "[SARS19]", "[Ctrl12]", "[AB12] to [AB20]" and "[Ab12, Cd34]" read as printed wherever no entry prints the key. That includes "[Mn12, MH17]" next to a listed MH17.
  - Where the list prints the key, the bracket is a citation: "references Ab12 and Cd34", "Reference MH17 showed it.", "Quelle MH17".
  - All 76 readings are the same on both runs.
  - The new regression case `citations-key-shapes-without-entries-stay` fails on a578dc0, and the new unit file does not import there.
- **S1, fixed.** `list()` returns only the blocks up to the last entry. Continuation blocks between entries still go with the list. "We thank all in 2020 for help." and "Received 3 May 2020." after the list are read, and "(2020)." between two entries goes. Two new rows fail on a578dc0.
- **S2, fixed.** A run that follows a non-reference heading, with only passed kinds between, is read. This covers "Notes", "Endnotes", "Anmerkungen", "Appendix B" and "Notes" with a footnote between. "Results", text, then entries is still removed. A second list after body text under "Notes" is removed while the first is read. Four new rows fail on a578dc0.
- **N1, done.** An entry counts as cited only with a year and an author ("N. Nagaosa", "Fahl, S."). The round 1 row "[1] In 2011 we ran step 1 …" is now read, and its new row fails on a578dc0.
  - Some side effects are now false negatives, which read the list as printed (the safe direction): "Smith et al." lists, "ATLAS Collaboration" lists, full-name lists, and initials outside ASCII ("Ö. Müller").
  - Body lists with "protocol A. Then" or "the U.S. Army" in each item are still removed. These are rare and cannot be told apart from "J.R. Smith". Accepted.

Another check: with the reference step switched off, entry labels go the same way for keys as for numbers on main ("[1] A. Author" → "A. Author"). That is consistent.

## Checks on 739a6ac

- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 5729 passed, 1 skipped.
- **Corpus:** 13 documents against main c841f3d. Eleven are byte-identical. maass and Liu change exactly as in round 1: their scripts are byte-identical to round 1's, so maass has the same 10 keys and Liu loses only blocks 53–133.
- **Mutants:** 13 of 16 are caught. These are caught: `_keys` ignoring the listed keys, `_keys` ignoring look-alikes, the aside check, an entry without an author, initials only, surname only, `headed` never set, `headed` on any heading, `run.headed` not set, `headed` kept past text, `list()` keeping the last lines, `list()` ignoring `headed`, and a year alone as citedness. Three survive, and each changes one reading in a made-up shape. They are filed as **#383**:
  - `_KEY_ENTRY` without `^`: "The tool of [Mn12] A. Bee works." reads "reference Mn12".
  - `_ENTRY_AUTHOR` without its look-behind: six "[N] In 2011 we went to the USA. Then …" items are removed.
  - `headed` kept after a block that starts no run: "Notes", "[3] A stray note.", then [1]–[6] is read.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`; citations, placeholders, conformance, runner): seeds 2024 and 123456, 572 passed each.
- **CI with `ci:full`** on 739a6ac: tests on ubuntu, macOS and Windows, browser, lint and layers, licences, security and CodeQL are all green. `mergeable_state` is clean.
- Commit messages carry no closing keywords. The PR body closes #254 and #92.

## Fix list

None. Deferred: #383 (test pins, v1.2, lane:textprep).

## Merged

Squash-merged pinned to 739a6ac as **8a8f863**. #254 and #92 are closed.
