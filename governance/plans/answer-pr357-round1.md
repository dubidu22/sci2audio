# PR #357 round 1: answers (head 5cf1378)

Commits on top of 9420cd8, no force-push: a40e18e (tests for S1 to S4b, N1), f2deb0f (merge of main 6c91465, PR #345; one clean auto-merge in cli.py), 5cf1378 (N1 again: ruff refuses `assert` in src, S101).

- **S1, fixed.** `test_a_line_holds_42_characters` uses literal numbers. LINE == 42 and LINES == 2. A one-word line of 42 characters stays one line. "a"*20 + " " + "b"*21 (42 characters) is one line; "a"*21 + " " + "b"*21 (43) is two lines. Sixteen words of "abcd" make one cue of two 39-character lines; seventeen make two cues, never a third line.
- **S2, fixed.**
  - `test_a_semicolon_wins_over_a_later_comma_in_the_same_cue`: the reviewer's text gives exactly `[("Alpha beta gamma delta", "epsilon zeta eta theta;"), ("iota kappa lambda, mu nu xi omicron pi", "rho sigma tau upsilon phi chi psi omega")]`.
  - `test_a_clause_mark_counts_from_a_half_full_cue`: a ";" ending a 42-character start is used (the first cue is that start). One ending a 41-character start is not, and the later "," is used instead.
- **S3, fixed.** `test_a_chunks_time_is_shared_out_by_characters` pins two chunks exactly:
  - cues of 46 and 78 characters over 2000 to 4000 ms give [(2000, 2741), (2741, 4000)];
  - sixty words over 2000 to 5000 ms give cues of 79, 79, 79 and 59 characters, timed (2000, 2800), (2800, 3601), (3601, 4402), (4402, 5000). That is start + (end - start) * done // total.
- **S4a, fixed (guard kept).** `test_a_subtitle_file_replaced_by_someone_else_during_the_run_is_left_alone`: the failing read-along write first puts another file over the committed book `.vtt` with `os.replace`, which gives it a new inode. Afterwards only that file is left, with its content "theirs". With the inode check removed, the test fails (`assert [] == ['A Study of Tones.vtt']`).
- **S4b, fixed.** `test_subtitle_files_match_the_read_along_and_ffmpeg_reads_them` checks that `read_bytes()` of every `.srt` and `.vtt` holds no `\r`.
- **N1, done.** The unreachable fallback is gone. `split` appends `cast("tuple[str, ...]", wrap(words[:cut]))` with the reason as a comment, because ruff S101 refuses `assert` in `src`.
- **N2.** No action, as asked.

Checks on the new head:
- ruff check and format, lint-imports (3 kept) and deptry are clean;
- fast suite: 5245 passed, 1 skipped, 6 xfailed (the xfails are from main);
- browser: 56 passed.

ci:full needs a rerun on this head.
