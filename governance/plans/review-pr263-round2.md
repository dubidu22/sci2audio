# Review of PR #263, round 2 (head 0c6f415)

Author's answer: https://github.com/dubidu22/sci2audio/pull/263#issuecomment-6876221652

## Round 1 items

- **F1, fixed.** A date after a dash that is not read "bis" now stays as printed: "vom 1.–3.4.2020" and "vom 1.3.–11.3.2020" read as they do on main, and both runs are pinned. New German regression case `de-numbers-date-after-a-dash-without-bis`.
- **F2, fixed.** `_RANGE_DASH_BEFORE` now knows the em dash: "vom 1.3.2020—11.3.2020" reads "bis elften März 2020", and "am 3.4.2020—5.4.2020" reads "bis fünften April" (main: "fünfter"). Pinned.
- **F3, fixed.** `past()` now bisects, and the links pass runs only once a link starts after the abbreviation. The abbreviations step alone on `"Kap. https://x.org/a dazu " * n` takes 0.30, 0.65, 1.26 and 2.63 s from 52k to 416k characters, so it is linear now (round 1: 5.15 s at 416k). The whole German chain on 104k characters takes 1.95 s, against 1.8 s on main. The new timing test compares 4x text at best of 3 against a ratio of 8.

## New in this round

### G1 (should fix, small): the `_LINK_START` pre-check drops the angle-bracket link that round 1 handled

| printed | round 1 head | this head | main |
|---|---|---|---|
| `Siehe Kap. <https://x.org/a> 3 dazu.` | `Siehe Kapitel 3 dazu.` (stable) | `Siehe Kap. 3 dazu.` → second run `Kapitel` | unstable, as this head |
| `See Fig. <https://x.org/a> 3.` | (not probed) | `See Fig. 3.` → second run `Figure` | unstable |

`_LINK_START.match` runs at "<", which the links step removes as part of the link. So the pre-check returns None before `link_removals` is ever consulted. Let the pre-check skip an opening `<` (and any other opener the links step takes with the link), and pin both languages on both runs.

Optional: `_GAP = 8` is not needed for linear time. The white-space walk after each abbreviation is already bounded by the next match, and with the cap, `Siehe Kap.` followed by ten spaces and a link changes on a second run (as on main). Drop it or keep it, your choice; say which.

Not a regression against main, but it is the shape this PR's own D1 fix targets, so it belongs here.
