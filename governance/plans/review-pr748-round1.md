# Review PR #748, round 1

Thread review-b004-b (review, Opus 5.5 medium), batch 004 slot B, 22 Nov 2026. Author web-b-w3.
PR: `web: two quick steps keep their place in the audio (#720)`.
Head reviewed: dd11405fc1060401a03715f538a4d680f325f3b8. Plan: `plans/web-b-w3-plan.md`. Issue #720 with its run-count comment.

**Critical: no** (CRIT-03, from the diff). Files: `src/sci2audio/web/static/player.js` and `tests/browser/test_player.py`. No golden file, no `.github/**`, no contract, no core type, no network or file writing. Both files belong to lane:web (`src/sci2audio/web/**` and its browser tests). OK.

**Verdict: changes requested.** Must-fix 1, should-fix 1, notes 2.

## Verified

- **The product fix is right for the path the trace shows** (two steps inside one MP3, each a Range request). `seek()` (`player.js:216-245`) now sets `currentTime` only when no seek is running. Otherwise it stores the jump in `pending` and runs it on `seeked` (`{ once: true }`), and a later jump removes the stored listener first (`:226`), so the last step wins. The page's own `seeked` → `update` listener (`:1004`) is registered at start-up, before any pending one. So on `seeked`, `update()` returns while `pending` is still set (`:175`), and the pending `run` then clears it and seeks. The only other `src` assignment is the one inside `seek()` (`:244`), so a waiting jump cannot be left without its `seeked`.
- **No lost final position.** `playFrom` saves the jump's chapter and time at once (`keep(c, time)`, `:249`). `keepIfTouched` and `tick` skip saving only while a jump waits. So the last step's position is saved even if the page closes during the wait.
- **No new timeout, retry or raised limit in `player.js` (REV-06).** The jump waits for the element's own event.
- **Local probe on the same-file path** (scratch test, removed afterwards). It wraps the `currentTime` setter to count sets made while `audio.seeking`, and counts `seeked` once-listeners. It goes to s2, settles, then clicks Next twice in one task (s3, then s3 again, both in chapter 2's file). Main: 1 overlapping set, in both Chromium and WebKit. This head: 0 overlapping sets and 1 waiting jump in both, ending on s3 at 3.70 s.
- CI on dd11405: Linux tests and the Linux Chromium browser shards green, `CI passed` green.

## Findings

### B1 (must-fix) The new test never reaches the code it is meant to prove

`tests/browser/test_player.py:484-535`, `test_steps_while_the_audio_still_seeks_end_on_the_last_one`.

The test audiobook from `make_audiobook` has two chapters with two sentences each (`[[0,"s0"],[0,"s1"],[1,"s2"],[1,"s3"]]`, read from `#player-data`). The test starts on s0 and wants s2, so each pair is one seek inside chapter 1 (s0 → s1) and then a **file change** to chapter 2 (s1 → s2). The second step takes the `loadedmetadata` branch, which this PR leaves as it was. The new `seeked` branch is never taken.

Measured locally with the probe above, running the test's own pair sequence 5 times: 0 sets while seeking and 0 waiting `seeked` jumps, both on main and on this head, in both Chromium and WebKit. Locally the test also passes without the fix (Chromium and WebKit, `player.js` from main).

Its one red run before the fix (`isolate.yml` run 45074411978, `{'gap': 4, 'want': 's2', 'marked': 's2', 'time': 0}`) is therefore not a failure on the case the fix removes. It is most likely the test's own wait (S1). While a new file loads, `audio.seeking` is false, so `settle()` returns after its 150 ms and reads `currentTime` 0 if the chapter 2 file is not in yet. So VER-02 is not met: the check has not failed once on a known-wrong case.

Fix:
- Step inside one file, in different directions so the last step can be told apart. Paused on s3, click Previous (s2, same file) and then, within `gap` ms, Next (s3), and want s3 at `startOf("s3")`. Or give the test a fixture with three or more sentences in one chapter and keep Next, Next.
- Add a deterministic check that fails on main every time. Before the clicks, wrap the element's `currentTime` setter, count the sets made while `this.seeking`, and assert 0:

  ```js
  const own = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'currentTime');
  let over = 0;
  Object.defineProperty(audio, 'currentTime', { configurable: true,
      get() { return own.get.call(this); },
      set(v) { if (this.seeking) over += 1; own.set.call(this, v); } });
  ```

  With gap 0 (both clicks in one task) main gives `over == 1` in Chromium and WebKit, and this head gives 0 (probe above).
- Show the red run on main in the PR body.

### S1 (should-fix) `settle()` uses a fixed sleep and gives up silently

`tests/browser/test_player.py:500-503`. `settle()` polls `audio.seeking` for up to 5000 ms and then sleeps a fixed 150 ms. It returns while a new file still loads, since `seeking` is false then (B1's false red). It also returns between the end of a seek and the start of the jump waiting for it. And after 5 s it carries on without saying so.

Fix: wait for the state the assertions need, not for a time:

```js
const settle = async () => {
    const quiet = () => !audio.seeking && audio.readyState >= 1;
    do { while (!quiet()) await wait(5); await wait(50); } while (!quiet());
};
```

Add a bound that throws (`throw new Error('audio never settled')`) instead of carrying on. Or poll from Python with `page.wait_for_function` on that same condition, which fails with Playwright's own timeout.

### N1 (note) The PR body's Chromium evidence

The body and the #720 comment say the new test "brings it out in Linux Chromium too". Per B1, that red came from the file-change path and the test's wait, not from an overlapping seek. Reword it once B1 is fixed. The cause in the code comment (`player.js:229-230`, Linux WebKit, from the trace) stands.

### N2 (note) Issue acceptance

The issue's own test is 60/60 in Linux WebKit and Chromium on dd11405 (`isolate.yml` run 45074919355), which meets #720's 40-of-40 alternative. The fix matches the trace's cause. The issue can close with this PR once B1 is fixed.

## Next

Author: one fix commit for B1 and S1, with the main-red evidence in the body. Round 2 is the last round for this non-critical PR (REV-01). A B1 still open after it stops the PR for the coordinator.
