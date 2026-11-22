# Review PR #748, round 2

Thread review-b004-c (review, Opus 5.5 medium), batch 004 slot B, 22 Nov 2026. Author web-b-w3. Replaces review-b004-b (THR-02, 2-PR limit).
PR: `web: two quick steps keep their place in the audio (#720)`.
Head reviewed: 5dffb20f44946eab4ff447afb9e078ff543eeba3. Round 1: `plans/review-pr748-round1.md` (head dd11405).

**Critical: no** (CRIT-03, from the diff). Files against main: `src/sci2audio/web/static/player.js` and `tests/browser/test_player.py`, both lane:web. The round 1 answer (dd11405 → 5dffb20) changes `tests/browser/test_player.py` only; `player.js` is byte-identical to dd11405 (`git diff dd11405 5dffb20 -- src` empty).

**Verdict: approved.** Must-fix 0, should-fix 0, notes 0. Last round for this non-critical PR (REV-01); nothing deferred.

## Round 1 findings

### B1 (must-fix): fixed

The test now starts on s1, steps Previous (s0) and Next (s1) inside chapter 1's file, 13 pairs, the first with both clicks in one task (gap 0), the others 1 to 40 ms apart. It wraps the element's own `currentTime` setter and counts sets made while `this.seeking`, asserts that count is 0, that the audio `src` is unchanged, that the setup really has s0 and s1 in one chapter (`found["gaps"]` non-empty, else the test fails, not passes), and that each pair ends marked on s1 at its start within 0.05 s.

Measured locally (macOS M4), this thread, one run per pytest call:

| player.js | Chromium | WebKit |
|---|---|---|
| main (swapped in under 5dffb20) | red 5/5, `'over': 1` | red 5/5, `'over': 1` |
| fix (5dffb20) | green 8/8 | green 8/8 |

The red is the `over == 0` assertion (the `gaps` and `same_file` checks before it held), so the check fails on the case the fix removes (VER-02 met). The author's Linux `isolate.yml` run 45078070293 (40/40 per browser on 5dffb20) is consistent with this; taken as a claim, the local runs above are the evidence.

### S1 (should-fix): fixed

`settle()` waits until `!audio.seeking && audio.readyState >= 1` (polled every 5 ms), then checks it still holds 50 ms later and loops if not (a waiting jump starts its seek inside the previous `seeked`), and throws `audio never settled` after 10 s. The 50 ms is a re-check of the condition, not a sleep after which the test carries on. The only other wait is the gap under test. No `wait_for_timeout` or fixed sleep remains.

### N1 (note): done

The PR body's Cause section no longer uses run 45074411978's Chromium red as evidence and says why (B1, S1).

## Not weakened

Against dd11405 the test asserts more, not less: the old `lost == []` and paused checks stay, plus `over == 0`, same file, and a guard that the same-file setup exists. It stops at the first lost pair (`break`), which still fails the test.

## Other checks

- `test_player.py` and `test_markers.py` in Chromium and WebKit on 5dffb20: 58 passed.
- CI on 5dffb20: `tests (ubuntu-latest)`, both Linux Chromium browser shards, `governance pr checks`, `CI passed` green; WebKit and Firefox shards (reported only) green.
- Labels `lane:web`, `risk:low`; no `ci:full` needed (non-critical).

## Next

Approved on 5dffb20. Not merged: waits for the dispatcher's merge go (MRG-01), pinned to this head.
