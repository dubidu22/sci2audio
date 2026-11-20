# PR #609 review, round 2 (head 6541fad)

Reviewer: B14 extraction review thread, Opus high. 19 Nov 2026. Answer read: plans/answer-pr609-round1.md.
Verdict: **one CI-required test fix**, otherwise every round-1 item is done.

## Round-1 items

- F1 (MAX_TAG, D-783): `TagLimitedParser` + `_check_tag` with `locatetagend.match(rawdata, i + skip, i + MAX_TAG + 1)`; boundary is right (a tag of exactly MAX_TAG characters reads, MAX_TAG + 1 is refused; an unclosed tag at the end shorter than the limit passes to the parser as before). The copied module is untouched. Re-probed on 6541fad (ru_maxrss): 8 MB start tag, `a=">"` row, 8 MB end tag, 8 MB self-closed `<br …/>`, 8 MB nav tag: all refused at 193–196 MB in 0.2 s (were 1,267 MB). `</ a a …>` (bogus comment) reads at 41 MB. One 999,000-character quoted attribute reads at 31 MB. 1,000,000 `<p>x</p>`: 10.0 s, 202 MB (round 1: 9.1 s on 37ec25d, same machine, so the second regex pass costs little). Markdown inline tag of 3.9 MB: refused with the tag message at 644 MB, the peak being markdown-it's before the page reader; under D-579's 900 MB.
- F2: nav label of 60 MB refused (outline dropped) at 140 MB (was 935 MB). F3: SVG title of 60 MB refused at 141 MB (was 935 MB). F4, F5: tests added; the author reports the mutants killed.
- N1 (docstring), N2 (comment): done. CHANGELOG names the tag, title and label bounds and D-783.
- Merge of main 36cb697: only CHANGELOG.md, both sides kept.
- Local nightly Hypothesis profile on 6541fad (`HYPOTHESIS_PROFILE=nightly`, the three extraction modules plus test_extraction_text.py, CPython 3.12.3): 378 passed.

## Fix (CI asks for it)

**R2-F1.** The mutation workflow (run 44460675356, all three runners) is invalid: under mutmut, `test_the_copy_names_its_source_and_keeps_the_psf_notice` sees `mutmut.mutation.trampoline`, which mutmut adds to every file it mutates, so the clean run fails ("failed to collect stats") and all 674 mutants count as "not killed". Fix as the author proposed: the import assert ignores imports whose top package is `mutmut` and stays exact otherwise. Test-only; push it as round 2's single fix commit.

## Round 3 (final)

On the new head: `ci:full` (three systems) and the mutation workflow again (same globs: `sci2audio.extraction.markup* sci2audio.extraction.markdown* sci2audio.extraction.epub.xǁ_NavReaderǁ*`, tests the three extraction modules, 4 runners). The nightly dispatch on 6541fad (run 44460582541: slow tests on Linux, macOS, Windows with the nightly profile, and the property job) counts for the source, since R2-F1 changes one test only.
