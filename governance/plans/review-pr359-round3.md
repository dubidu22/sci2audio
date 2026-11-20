# Review PR #359, round 3 (textprep follow-ups PR 2, units #320 #321 #335)

Head reviewed: f876880 (91f9324 on ff55995, then merges of main bd3be17 and 0af10d0). Answer: plans/review-pr359-round2-answer.md.

**Verdict: approvable at f876880.**

- **B1, fixed.** `_power_left_after` leaves a German fraction as printed only when the powers rule's own `_unit_chain` leaves the chain's last power, and only when the power after it is no statistics square. All six round-2 rows (`3/4 kg x²`, `3/4 m x⁻¹`, `3/4 m s x²`, `1/2 kg R²`, `1/5 m R²`, `2/3 s t²`) now read the same twice. So do the S1 rows and controls.
- **Probes**, about 140 shapes from rounds 1–3, whole chain twice, main 0af10d0 vs f876880: the PR has only the two known #358 differences (`y < 2x`, `y > 2x`). Every first-run change against main falls in a class the PR lists (D-610). No German shape that main read the same twice changed.
- **Mutants:** all 8 fail the tests. They removed the chain check, dropped `_unit_chain` from it, dropped the statistics-square check, allowed only one letter per chain unit, dropped "·" as a separator, removed the English fraction chain, and dropped the "," look-behind and the `_OUT_OF` look-behind.
- **Fast suite:** 5316 passed, 1 skipped, 0 xfailed. Regression cases EN/DE twice: 575 passed both times. The corpus second-run test passes on 13 of 13. ruff, format, lint-imports and deptry are clean.
- **The 13 sample documents** (`run_script_job`, main 0af10d0 vs f876880): all 39 files are byte-identical.
- **Nightly seeds** 2024 and 123456 (runner, conformance, numbers, units, German numbers/statistics) are clean.
- **Commit messages:** 9d6a8e7, efb2eee and 91f9324, plus the merges, carry no closing keywords. `Closes #320/#321/#335` is in the PR body only.
- **CI on f876880:** tests (ubuntu-latest), (macos-latest) and (windows-latest) are green.

Fix list: none. Deferred: none (#358 already filed).
