# Review PR #289, round 3 (head 52ca852)

## R2-1, checked
Fixed. The MATLAB-style listing with bold "end" lines is one CODE block; a run made only of wholly bold lines stays read; the three-heading probe still gives headings in every font; M1/M3/S1 probes unchanged. Two new unit tests. CI on 52ca852 all green.

## New item

R3-1 (must explain before merge). The new browser tests that make an audiobook from a code PDF failed twice:
- CI, head 159d4d6, job 132470690356 (browser, serial run): `test_a_listing_taller_than_the_window_keeps_its_spoken_notice_in_view` timed out in `listen_to` after 60 s waiting for "Your audiobook is ready". The page snapshot is still the document page, with the banner "A job is running: Audiobook of long-code.pdf" (job ...-audio-2): the job had started but neither finished nor led the page to the job page in 60 s.
- Local, head 159d4d6, `-n 4` while my corpus script runs loaded the machine: `test_a_skipped_code_block_shows_its_notice_and_its_code` failed (detail not kept).
Alone and in four more full `-n 4` runs on 52ca852 both pass; the job for the 44-line PDF takes about 3 s and the move to the job page 0.5 s, also with 3 busy CPU threads. So the job itself is not slow: something stalled for a minute.
Wanted: find the cause (a hang in the audio job or in the page's start flow after `POST /api/v1/jobs`: the settings `PUT` before `location.assign`), and either fix it or show it also happens on main (then a linked issue, and quarantine per D-374 if it repeats). Do not raise the timeout.

## Also seen (not this PR's)
- macOS fast tests on 159d4d6 failed once in `test_textprep_numbers_statistics_de.py::test_long_german_blocks_take_linear_time[sentences]` (3.9 s against a fixed 3 s limit): one of the fixed-seconds timing tests that #276 / PR #277 moves to the ratio helper. Green on 52ca852.

## R3-1, checked (head e5541d3, then main merged in: e4157ee)
Fixed. The cause was a race in the test helper `listen_to`, not a hang in the job. It clicked "Make the audiobook" on a page drawn before the analysis job ended, and the analysis's end then reloaded the page, which cancelled the settings PUT and the move to the job page. I ran the author's probe (plans/review-pr289-round3-probe.py, which holds the analysis 1 s after its report is written): it fails on 52ca852 and passes on e5541d3. The helper now waits for #summary and settled(), then for the job URL. The timeout is unchanged. The page's own race when a person clicks in that moment is filed as #299 (v1.2).
On e4157ee: fast suite 4,376 passed and 1 skipped; browser suite run serially 53 passed; CI all green.

## Verdict
Approve and merge.
