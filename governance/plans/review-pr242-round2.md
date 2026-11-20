# Review PR #242 round 2 (#130 German numbers, dates, statistics)

Round-1 fixes checked on 4a82413. The head is now 6d9b264, which only adds main a475be4 (#248) and the re-recorded goldens. `git diff a475be4 6d9b264` touches only the PR's own 17 files.
Verdict: **changes requested** (2 new must-fix: R2-1, R2-2). All 7 round-1 items are fixed.

## Round-1 items: verified
1. File numbers without "Az." ("– VI ZR 8/14", "1983 – 1 BvR 209/83") stay as printed: fixed.
2. "Aktenzeichen lautet 2 O 8/15 … am 3.5.2019" now reads "am dritten Mai 2019": fixed.
3. "von 1.500 auf" reads "15 hundert", "um 1.200 erhöht" reads "12 hundert", "um 1.200 Euro" reads "1200": fixed.
4a. "seit 1998x" is stable: fixed. 4b. "95 %-KI [1; 1],1–1" is stable: fixed.
5. English "3x⁻²" stays: fixed.
6. There is no space before the full stop: fixed.
7. "zwischen 1234 und 1567 Probanden" stays counts and "zwischen 1990 und 1995 gab es" stays years: fixed.
- Extra: the units step leaves file numbers as printed, so "13 Watt" is gone from the German paper (closes #243). #247 is a duplicate and is closed. #250 (v1.2) is filed for "pro Quadratsekunde".
- File-number false friends ("3 Kinder 15/20", "12 Fälle 3/4", "Teil 1/2", "18 Monate 12/18") are read as before. "3 Mal 10/12" and "4 A 12/15" are kept as printed; that is contrived and acceptable.

## Checks
- CI on 6d9b264: green.
- English corpus: byte-identical to main 98eb92a (all 13 files run through `run_script_job`; only the German paper and the two German samples differ).
- Fast suite on 4a82413 (local, under parallel load): passed, except two `test_core_properties` Hypothesis health-check timeouts ("input generation is slow") caused by my concurrent runs, not code.
- Nightly German properties with seeds 303, 505, 1212, 1313, 1414, 1515, 1616: clean. **1717: failed** (R2-2).

## Must-fix
- **R2-1 Quadratic units step.** `units.py:172` `any(start <= match.start() < end for … in kept)` runs per number. `UnitStep().find` on one block takes 4.6 s at 80k characters of "1 O 1/12 " (0.35 s at 20k); `find_numbers_de` takes 0.17 s. Fix: pointer or bisect over the sorted spans; add a linear-time case.
- **R2-2 Second run (seed 1717).** `Kapitel I %CI` → "Kapitel 1 %CI" → second run "Kapitel 1 %Konfidenzintervall". `_AFTER_PERCENT` needs a digit before "%". Either the Roman rule leaves a numeral before " %" as printed, or the CI rule accepts it. Pin it.
