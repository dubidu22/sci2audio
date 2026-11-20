# Review PR #511, round 1 (nightly-green PR 2: #499 #500 #501), lean review under D-736

Head reviewed: b1cb33a, on main 68f322d. Non-critical, tests only, 4 files. Linux CI is green (`tests (ubuntu-latest)`, browser (Chromium), `CI passed`). Branch nightly 44079398176 is green in all four browser jobs: Chromium, Firefox, WebKit on Linux and WebKit on macOS.

**Verdict: approvable, and merged** as 96de4a3 (squash, pinned to b1cb33a). The tree is identical to the reviewed head's. #499, #500 and #501 are closed.

## What I checked
- **#499 key chords.** `Meta+ArrowLeft` is dropped, because it is Back in WebKit on macOS. The chords of the right arrow are added, and each one now asserts that the page stays on Listen.
  - No coverage is lost: `player.js` returns on `ctrlKey`, `metaKey` or `altKey` with one guard before any key, so both arrows go through the same check (`player.js:852`).
  - In the library test, `Control+a` becomes `ControlOrMeta+a`.
- **#500 `change_theme()`** is used only after the dark-mode switch. It awaits only `CSSTransition` animations (with `allSettled`), so a keyframe animation still fails `marked_plainly`'s `all == 0` (D-709). Every other call of `marked_plainly` is unchanged.
- **#501.** The dock's foot is checked with `abs(bottom - height) < 0.5`, for Firefox's sub-pixel layout. The check is still exact at the pixel.
