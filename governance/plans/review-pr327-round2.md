# Review PR #327, round 2 (head 6463087)

**Verdict: approved.** R1-1 to R1-4 are fixed as listed in the author's reply (https://github.com/dubidu22/sci2audio/pull/327#issuecomment-6882071565).

## Checked

- R1-1: differential run of main against the new head on 12,000 random XHTML snippets (the round 1 set plus 3,000 more): 0 differ, so `Page.order` and link targets match main again. The three round 1 examples are pinned by the new tests.
- R1-2 and R1-3, measured past the limit on the new head (tracemalloc): 1,100,000 empty `<a id>` refused with the EPUB message, peak 94 MB; 1,100,000 empty `<a href>` refused, peak 146 MB; 1,100,000 unclosed `<span>` refused, peak 171 MB; 1,100,000 distinct closed tag names read, peak 42 MB (mostly the input). Round 1 extrapolated about 1 GB per 64 MB chapter for each.
- R1-4: `test_a_book_of_more_items_than_the_limit_fails` passes here in 72 s; `test_a_file_of_exactly_the_limit_still_reads` 3.2 s.
- Fast suite on the head, Linux, `-n 4`, `HYPOTHESIS_PROFILE=ci`: 4775 passed, 1 skipped, 76 snapshots passed. CI on 6463087: all three systems green.

## A 600 s timeout or a cheaper test?

Keep the 600 s timeout. The test costs about 60 to 70 s because tracemalloc traces every allocation while it reads 1,000,000 items; without tracemalloc the same read takes about 10 s. But the memory bound is what this test exists for, and tracemalloc is the only measure that works the same on the three systems. The counting logic is already covered cheaply by the fast twins with `MAX_ITEMS` patched low. A smaller book would not test the decided limit. So the cost is one test of about a minute per system in the nightly slow job, which has no job timeout of its own. 600 s is a ceiling for slow macOS and Windows runners, not what the test costs.

## Deferred

#328 and #329, both on milestone v1.2 (D-582).
