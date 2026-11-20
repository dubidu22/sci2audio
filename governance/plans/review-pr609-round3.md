# PR #609 review, round 3, final (reviewed head 8b3f0f2; merge head after branch update: 8ec6515)

Reviewer: B14 extraction review thread, Opus high. 19 Nov 2026.
Verdict: **approved.** One deferred item: #632 (test gaps, no behaviour change).

## Round-2 item

- R2-F1 (8b3f0f2): the import check ignores only imports whose top package is `mutmut`; exact otherwise. Test-only, one file.

## Final-round checks

- **Three systems:** CI by hand on 8b3f0f2 (run 44461830525): tests ubuntu, macOS, Windows, both Chromium shards, lint and layers, licences, security, `CI passed`: all success.
- **Nightly seeds:** Nightly by hand on 6541fad (run 44460582541; 8b3f0f2 differs by one test only): slow tests with `HYPOTHESIS_PROFILE=nightly` on ubuntu, macOS and Windows, and the property job with many examples: all success. Local nightly profile on 6541fad, the extraction modules: 378 passed.
- **Mutation (mutation.yml on 8b3f0f2, tests: the three extraction test modules):**
  - New code, targeted runs 44476347182 and 44478836585: `check_line` and `TagLimitedParser` 27/27 killed; `_check_tag` + `PageReader.add` 41/42 (survivor `endpos + 2`: equivalent, the same tags are refused); `PageReader.handle_*` 39/41 (`svg.length = len(data)`: real test gap, #632 item 1; `continues = None` in `handle_endtag`: older, falsy-equivalent); `Budget` 25/27 (unused constructor parameters, #632 item 2); `TooMuchText` 12/18 (default kind and exception args: equivalent); `flush` 35/39 (older code, #632).
  - Run 44461833213: `_NavReader` 108/155 and markdown.py 428/491. Every survivor in lines #609 added is equivalent (`label_length` initial value; `_image` "ALT" and env), and the rest are older gaps listed in #632. `longest_block` and the block check: no survivor. The whole-module markup.py runner was still running at merge time; its result goes into the batch audit.
  - My own hand mutants on 37ec25d (round 1): 24, 22 killed, the 2 survivors fixed as F4/F5 and confirmed killed by the author.
- **Behaviour probe for the #632 gap:** an SVG title of 5,000 pieces of 1,000 characters is refused with the line limit at 36 MB, so the code is right and only the test is missing.

## Branch update before merge (MRG-03)

Main moved to 12f85a7 (#512 dev tools incl. ruff 0.17.5 and syrupy 7.0.1, #611, #616, #630) and CHANGELOG.md is a shared changed file, so the branch was updated with GitHub's update-branch (merge, 8ec6515). Diff-unchanged check: `git diff 8b3f0f2 8ec6515` over every file of this PR (extraction module files, the three test modules, THIRD_PARTY_LICENSES.md) is empty; CHANGELOG keeps both sides. `ruff 0.17.5 format --check` and `check` on the PR files: clean. Three-system CI dispatched on 8ec6515; merge only when it is green, pinned to 8ec6515, with an explicit squash message (the branch history holds "Closes #299/#407/#381" from #601's squash body, which must not be repeated).
