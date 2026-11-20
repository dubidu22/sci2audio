# Review PR #242 round 1 (#130 German numbers, dates, statistics)

Head reviewed: 6cf25e3 (base main 5a254e4). Reviewer thread: "Review German numbers and dates PR".
Verdict: **changes requested** (5 must-fix: 1, 2, 3, 4a, 4b; 1 should-fix: 5; 2 minor: 6, 7). The rest is good work. Inline comments on the PR carry the same numbers.

## What I checked and what held

- Fast suite locally: 3939 passed, 5 skipped (same as the PR body). CI on 6cf25e3: all green.
- German properties (`-k "contract or second_run"`, 50 tests) under `HYPOTHESIS_PROFILE=nightly`, seeds 101 202 303 404 505 606 707 808: 6 clean, **2 failed** (303, 505), see must-fix 4a and 4b.
- English byte-identity: `run_script_job` (with `output_folder`) on all 13 corpus files, main via PYTHONPATH vs branch. The 7 English papers, the EPUB, the English Markdown and text samples are byte-identical. Only the German paper and the two German samples (Beispiel-Notiz, Beispiel-Text) differ, as expected.
- German paper golden: every body/footnote change is a date read in words ("v. achtundzwanzigsten August 2008", "am fünfundzwanzigsten Mai 2018", "neunten Oktober 19 hundert 91"); court file numbers after "Az." stay as printed; the reference-list edits are set aside. "numbers" and "statistics" are off the skipped-steps list (#130 acceptance line met).
- Readings asked for in the brief: "2 Komma 4 5", "am dritten Mai", "t mit 34 Freiheitsgraden", "F mit 2 und 57 Freiheitsgraden", "Chi-Quadrat mit 1 Freiheitsgrad", "95 Prozent Konfidenzintervall 1 Komma 2 bis 3 Komma 4", "Odds Ratio", "Az. 2 O 8/15" as printed: all correct, also on a second run.
- About 80 more hand-written German sentences through the full strict chain, two runs each: no second-run difference.
- English units changes: "1x⁶"/"2x²" now stay; "5 m²̸=1" reads the unit on the first run. Both new English cases fail on main (checked).
- Linear time: 20k-character blocks of 15 shapes (thousands, dates, Az., KI runs, Roman runs, powers, digit runs): at most 0.15 s, growth linear.
- Layering: units.py imports statistics_de, numbers_de imports units, both within textprep; lint-imports clean in CI.

## Must-fix

1. **Court file numbers without "Az." are read as fractions and ranges.** German legal citations usually give the file number after a dash, with no "Az.":
   - `BGH, Urteil vom 13.1.2015 – VI ZR 8/14.` → "... VI ZR **8 von 14**."
   - `BVerfG, Beschluss v. 15.12.1983 – 1 BvR 209/83.` → "... Dezember 19 hundert 83 **bis** 1 BvR 209/83." (the dash before the file number is read as a range from the year)
   - `OLG Köln, 6 U 12/10` happens to be left alone only because 12 > 10.
   The voice reads "8/14" as "acht vierzehn", which is fine for a file number; "8 von 14" changes the meaning. Ask: also keep a file number in its usual shape (Roman or Arabic chamber number, a register of 1 to 5 letters starting with a capital, number/two-digit year, e.g. "VI ZR 8/14", "1 BvR 209/83", "2 O 8/15", "13 W 17/12") as printed, and do not read a dash as "bis" when a file number starts right after it. Regression case with both sentences above.
2. **"Aktenzeichen" keeps the rest of the sentence as printed.** `_FILE_NUMBER` runs from "Aktenzeichen" to the next `;` `,` `(` `)`, newline or ". ". `Das Aktenzeichen lautet 2 O 8/15 und das Urteil fiel am 3.5.2019 mit 2,5 % Quote.` leaves "am 3.5.2019" unread (main reads it the same, but this PR is what reads dates). Ask: limit the kept span to the file number itself (the shape from item 1), not "everything up to the next comma". Unit test.
3. **A thousands point after "von", "um", "ab", "bis", "seit" ... is left as printed, and the voice breaks it.** `von 1.500 auf 2.000 Euro` → "von **1.500** auf 2000 Euro"; `um 1.200 erhöht` → "um 1.200 erhöht". misaki/espeak-ng de reads "1.500" as "eins fünfhundert". Cause: `_thousands` skips 1100 to 1999 when `_is_year` says year, but `_YEAR` never matches a number with a point, so nobody reads it. Suggested fix: when `_is_year` is true, read the thousands number with `year_words` ("von 15 hundert auf", "im Jahr 19 hundert 98"); a second run then sees "15 hundert" and nothing new. Unit tests and a regression case.

4a. **Second run: a glued x after a maybe-year word (seed 303).** `seit 1998x` → "seit 1998 mal" → second run "seit 19 hundert 98 mal"; also `bis 1998x mehr`. First run: the glued x makes `unit_follows` true, no year; second run: "mal" is a lower-case word, so `_is_year` says year. Make both runs decide the same; pin `seit 1998x`.
4b. **Second run: comma and digit glued after an interval (seed 505).** `95 %-KI [1; 1],1–1` → "1 bis 1,1 bis 1" → second run "1 bis 1 Komma 1 bis 1"; `Das KI [1,2; 3,4],1–2 war breit.` the same. `_JOINED_NUMBER` must also stop at `[.,]\d` after the bracket. Pin both.

## Should-fix

5. **English x rule: a superscript sign still gives "times".** `a 3x⁻² slope` → "a 3 times ⁻² slope" (same on main). The new case's goal says an x before a superscript is the variable, but `_times_x` only checks `isdecimal()`, and "⁻"/"⁺" pass `_boundary`. Treat "⁺"/"⁻" followed by a superscript digit like the superscript digit, and add "3x⁻²" to `symbols-x-before-a-power`.

## Minor (fix or say why)

6. **Space before the full stop after a German interval.** `OR = 2,3, 95 %-KI [1,1; 4,8].` → "... 1 Komma 1 bis 4 Komma 8 ." (also `KI = [1,1; 4,8].`). English gives "4.8." with no space. If the pad guards against "8." being an ordinal on a second run, the `_AFTER_KOMMA` check already covers "Komma 8. Wort"; otherwise drop the pad when only a full stop and white space or the block end follow.
7. **Joined years before a noun.** `zwischen 1234 und 1567 Probanden` → "zwischen 12 hundert 34 und 15 hundert 67 Probanden": `_is_year` looks for a capital noun only after the first number, and the second is a year because it is joined to the first. Understandable German, so not blocking; either check the noun after the last number of the run or file a v1.2 issue.

## Deferred by the reviewer

- Pre-existing on main (#113): the units step reads the register letter in "Az. 13 W 17/12" as "13 Watt" (in the German paper's golden). Filed as #243 (milestone v1.1).
- Author's own out-of-scope note ("2 m s⁻²" → "pro Sekunde hoch 2"): the author offered an issue; please file it (v1.2) and link it in the reply.

## Not findings

- "Teil II und III." at a sentence end is left as printed by design (second-run guard). espeak-ng de reads "römisch zwei und römisch drei", so fine.
- "Python 3.12", "2:30 min" left as printed: matches N-de-1/N-de-8 as planned.
