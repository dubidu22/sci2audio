# Review PR #577, round 1 (unreadable PDFs stop before the voice; #442 part B, closes #187)

Reviewer: app-lane review thread (B7). Head reviewed: **fc97dac** (base main 5a605e5). Critical (risk:high: a new user-facing stop).
Verdict: **changes required**: 3 items (R1 to R3), all small. The product logic is right and well tested. One fix commit.

## What I checked

- The whole diff (19 files), against plan B7 PR 1, D-762 (the rule), D-772 (PDF only, Q1) and AC-442.3.
- CI on fc97dac:
  - Linux run green. ci:full green on ubuntu, macOS and Windows.
  - Browser Chromium 1/2 and 2/2, ZAP and CodeQL green. The reported-only Firefox and WebKit legs are all green.
  - Mergeable is clean, and the `ci:full` label is removed.
- Local baseline on the 8 affected test files: 156 passed.
- **The order of the stop.** `run_audio_job`: `check_readable` → `check_folders` (makes nothing) → lock → `read_document` → the stop, before `voice_for` and `installed`, the targets check, the cover and any speech.
  - The CLI's `convert` runs the audio job first and the script job only after it succeeds, so exit 5 writes nothing.
  - `UnreadableTextError` is a subclass of `UnreadableFileError`, so `cli.py`'s table maps it to 5 without a change.
- **Goldens:** the report key is added only when set. `test_cli_golden` passes (9 snapshots), and no `.ambr` changed in the PR.
- **D-768:** the CHANGELOG Unreleased / Added line is there. It is accurate: the stop, exit 5 and the pages are named, and a smaller share gets a warning.
- **Mutants:** 20 hand mutants on the 8 test files, 19 killed, each by the new test aimed at it:
  - no stop; `>=` half; `bad > 0`; never stops; every format judged; no JSON key; no warning;
  - Make not blocked; Make blocked on a warning; callout class; callout text swapped; no `unreadable-text` kind;
  - a run of two as a range; every page counted as unreadable; the warning branch swapped; not a subclass of `UnreadableFileError`; "page"/"pages"; the share off by one; the `ranges` key.
  - The survivor, **m8**, is under R3.
- **Hypothesis, nightly profile:** seeds 1, 2 and 3 all pass (21 tests). But see R2: the property never reaches its own subject.

## Required (exact list)

**R1: the exit code 5 line, in the README and in `--help`.**
- The plan has the README line. The README table and `EXIT_CODES_HELP` in `cli.py` both say code 5 means "the file is damaged, protected or can't be opened", and a script that reads exit codes now also gets 5 for a PDF whose text can't be read.
- Add "or its text can't be read" (or close wording) to both.
- Accept the one-line change in `test_cli_golden.ambr` (`--help` output) with `--snapshot-update`, and name that one changed line and its reason in the PR body. The PR is already critical, so a one-line golden change is in its scope. Leaving `--help` unchanged would make it disagree with the README and with what exit 5 now means.

**R2: the Hypothesis property never reaches an unreadable page.**
- I measured 2000 examples of `core_strategies.contents()` under the nightly profile: 742 PDFs and **0** with an unreadable page. So `test_the_verdict_never_fails_and_names_only_unreadable_pages` only ever checks the `None` branch.
- Add a strategy (in the test file, or in `core_strategies` if you prefer) that builds PDF `Content` mixing readable pages with pages `legibility` marks unreadable. For example, lines of U+FFFD or private-use characters, which the measure flags (docs, "a page is unreadable when …"), with varied character counts per page.
- In the property, check that:
  - `found.pages` is a subset of the content's page numbers;
  - `stops` holds exactly when more than half of the characters are on those pages;
  - the verdict never fails.
- Show that the branch is reached: a strategy that always makes at least one unreadable page, or an assert/`event` count. Say in the PR body how often it is reached.

**R3: the report warning's place is not tested (mutant m8, warning appended last instead of first, survives).**
- `docs/unreadable-pdf-text.md` says "The report's warning comes first among its warnings", and `build_report` comments that it decides whether there is an audiobook at all.
- Assert it is `warnings[0]` in a report that also has another warning. For example, a glyph page in a PDF tagged with a language its text contradicts, or any other warning the existing helpers make.

## Notes (no action)

- N1: an audio job started through the API on such a PDF still makes the empty project folder and its `project.json` entry first (`web/tasks.py` calls `audiobook_folder` before `run_audio`), as any failed first run does (#552 N3). The removal clears it, and the page blocks Make, so this is accepted. Your web test already allows an empty folder.
- N2: the stop is decided on the whole document, not on the chosen chapters (D-762 as pinned). A person who left out the unreadable chapters still can't make it. That is the plan's rule; any change is a product question for Colin, not this PR.
- N3: `#442` stays open for part 3 (recovery, Colin's call), and `Closes #187` is right.

## Next round

One fix commit for R1 to R3, then Linux CI green, then `ci:full` again (critical, final round: three systems). I will re-run the 20 mutants, the reach count of the new strategy, and nightly seeds.
