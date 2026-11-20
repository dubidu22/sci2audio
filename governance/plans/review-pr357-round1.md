# Review of PR #357, round 1: SRT and WebVTT subtitles (#214, D-606)

Head reviewed: `9420cd8` on main `79d0cdb`. One commit; its message carries no closing keyword
("(#214)" in the subject only; `Closes #214` is in the PR description only). Critical (two golden
files). Reviewer: review thread "Review subtitles PR 357", 15 Nov 2026.

**Verdict: changes requested. No blocker.** The design matches the plan and D-606 point for
point, and every real-file check passed. The four should-fix items are test additions that
pin the numbers D-606 sets; today several one-line changes to those numbers pass every test.

## What I checked

- **Plan and D-606.** Spoken text from `assemble` into `output.model.Spoken.text`; pure
  `output/subtitles.py` on the read-along's `Timeline`; a cue never crosses a chunk; at most
  2 lines of 42 characters; long chunks cut after `;`/`:`, else `,`, else a space, with the
  half-full rule; time shared by characters, outer times equal to the read-along; chapter
  files at `start - chapter start`; per-chapter pairs beside the MP3s, book pair beside the
  M4B, chosen by `--format`; atomic writes after the audio and before the read-along file;
  existence check and `overwrite` cover them; `JobSettings.subtitles` passed into
  `OutputSettings` (the job setting overrides whatever `OutputSettings.subtitles` a caller
  passed, which is right: one source of truth); `CONFIG_VERSION` stays 1; CLI
  `--subtitles/--no-subtitles` (BooleanOptionalAction, default "as saved"); web checkbox,
  API models (StrictBool), `MEDIA_TYPES`, job file list, record `files.subtitles`. Follow-ups
  #351 and #352 exist. All as planned.
- **Suites on the head.** Fast suite: 5210 passed, 1 skipped, 6 xfailed (the xfails are
  main's #324 cases), 121 s. Browser suite: 56 passed. `ruff check`, `ruff format --check`,
  `lint-imports`, `deptry src`, `zizmor --offline`: clean.
- **Real books with the fake voice** (1700 samples per character, about real speech pace),
  subtitles on, both formats: pymedphys, hardt, the German note (Markdown), the German text
  file and the Time Machine EPUB (1964 chunks, 3276 cues, 38 files). For every book and
  chapter file: strict parse (numbering, time lines, 1 or 2 lines, no empty line, each line at
  most 42 characters unless one word, no `-->`, only `&amp;`/`&lt;`/`&gt;` in VTT, no BOM,
  no `\r`); the cues inside each chunk tile it exactly from the read-along `start` to `end`
  with no gap and no overlap, and no cue lies outside a chunk; chapter cues shifted by the
  chapter start equal the book's cues; SRT and VTT texts equal. Zero issues; no zero-length
  cue; the longest cue 6.1 s.
- **Validators.** The bundled ffmpeg reads every written `.srt` and `.vtt` (all five books)
  with the same cue times. Chromium (the Playwright build) loads all 63 written `.vtt` files
  as a `<track>` and its own parser returns exactly our times and text. A hand-made tricky
  file (`a < b & c > d`, `x --> y`, `<b>…</b>`, a literal `&amp;`, lines `NOTE this`,
  `WEBVTT`, `1`, a time line as text, `Tom & Jerry --> &lt;`) gives 12 of 12 cues with the
  right times and the text kept as escaped.
- **Text as spoken, German.** Notices ("Figure 1 is skipped.", "Fußnote 1."), expanded
  numbers and German quotes and dashes show as the voice gets them. Across the whole corpus
  no spoken text holds a tab, newline or no-break space, so collapsing white space loses
  nothing today.
- **Long words and URLs.** A word over 42 characters gets a line of its own; tested and seen.
  `split` stays fast at the utterance cap (300 characters: 2 ms; even 5000 one-letter words
  take 0.9 s).
- **Write order and the failure clean-up (the addition beyond the plan).** I judge it
  **right and needed**: the app's `_remove_new` removes only files ffmpeg wrote
  (`ffmpeg.finished` identities), so without output's own clean-up a run that fails at the
  read-along file would leave new subtitle files that refuse the next run without `overwrite`
  (`test_a_failed_run_with_subtitles_leaves_nothing_in_the_way_of_a_rerun` shows exactly that
  case). It takes back only files that did not exist before the subtitles were written and
  whose inode is still the one this run committed, the same guard idea as the app's
  `_identity`. With `overwrite`, a replaced older file stays replaced, as for audio. Writing
  the read-along file before the subtitles fails the disk-full test, so the order is pinned.
- **Settings round trip.** `KEPT` and `settings_to_data` gain the key; a file without it reads
  as off; a non-bool is refused with a warning; the API refuses `1` and `"yes"`.
- **Mutation-style breaks** (30 one-line changes, each run against the subtitle, app, CLI,
  settings and web unit tests, and the web ones also against the browser test):
  killed: dropping `at = until`, chapter origin 0, single rounding, no `>` escape, no SRT
  arrow rule, no half-full break, the long-word rule, dropping one line, no clean-up
  `unlink`, clean-up without the "new" check, all subtitle files counted as new, subtitles
  out of the existence check, the app not passing the setting, the app's file list, `KEPT`,
  the bool check, the CLI flag, `names.subtitle_files` always adding the book pair,
  `LINES = 3`; the web `_merged` override, the job file list and the checkbox's `checked`
  are killed by the browser test only.
  **Survived** (the reasons for S1 to S4): `";" ":" ","` merged into one class;
  `LINE = 43`; `len(whole) < LINE` (a 42-character text no longer one line); the half-full
  threshold `// 3`; the inner time share `(done - 1)`; the inode check removed;
  `newline="\r\n"` (all file tests read with `read_text`, which hides `\r\n`).
  Equivalent, no action: a tie in the even-lines choice taken the other way; `.strip()` on
  the spoken text.
- **CI.** Linux run on `9420cd8` green (the red "CI passed" entry is the run the concurrency
  group cancelled when labels changed). I added `ci:full`; the three-system result is below.

## Fix list

### Blockers

None.

### Should fix (tests only, no code change expected)

- **S1. Pin 42 on both sides.** A test with literal numbers, not the imported `LINE`: a text of
  exactly 42 characters is one line, a two-word text of 43 characters is two lines. Kills
  `LINE = 43` and `len(whole) < LINE`.
- **S2. Pin `;`/`:` before a later `,`.** A chunk where a `,` comes after the `;` inside the
  first cue that fits, and the first cue still ends at the `;` (for example
  "Alpha beta gamma delta epsilon zeta eta theta; iota kappa lambda, mu nu xi omicron pi rho
  sigma tau upsilon phi chi psi omega" must give a first cue ending "theta;"). Today's
  `test_a_long_chunk_is_cut_after_a_clause_mark` passes with the marks merged into one class.
  Also pin the half-full threshold: a clause mark just under half (41 characters before it)
  is not used, one at 42 is (kills `// 3`).
- **S3. Pin the inner times.** One exact test of a multi-cue chunk's inner boundaries: given
  the chunk's start and end in milliseconds and the pieces' character counts, each inner
  boundary is `start + (end - start) * done // total` (kills the `done - 1` change).
- **S4. Pin the two clean-up details and the line ends.**
  - The inode guard: a subtitle file this run committed and that is replaced by another file
    before the failure (for example in the failing `write_text` hook) is left alone. Without
    such a test the guard is dead weight; if you prefer not to test it, remove it and say so.
  - `\n` line ends: the file tests check `read_bytes()` has no `b"\r"` (this matters on
    Windows, where `newline="\n"` is what keeps them out; `ci:full` then proves it there).

### Nits

- **N1.** `split`: `wrap(words[:cut]) or (" ".join(words[:cut]),)`: the fallback cannot be
  reached (a prefix of words that fit one cue always fits), so `wrap(words[:cut])` with an
  assertion or a comment is clearer. Optional.
- **N2.** `str.split()` also breaks at a no-break space (U+00A0, U+202F). No corpus text has
  one in its spoken text today (checked), so no action now; if a later text step keeps them,
  wrap could treat them as part of a word. Not an issue unless you see a case.

### Deferred

None beyond the existing #351 (player track, v1.2) and #352 (word times, Later).

## Three-system CI

`ci:full` added on `9420cd8`: `tests (macos-latest)` succeeded (08:46:45Z) and
`tests (windows-latest)` succeeded (08:48:42Z), with Linux tests, browser, lint and layers,
security and licences green in the same run. The fixed head needs this again before the merge.
