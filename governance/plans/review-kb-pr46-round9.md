# Review of KB PR #46, round 9 (D-383, D-382 record)

Head reviewed: `8313334`. It adds one commit on top of `88fb2d4`, which was approved in round 8. The commit adds D-383 and adds D-286 to D-382's Record cell.

## Checked and correct

- **D-383 matches the coordinator's handoff** (17:14:31 UTC) and the chat post (17:14:26 UTC). The first chapter stays in the measurement. Skipping it would take the worst error from 24 % to 14 % but move the first estimate from 26 % to 43 % of a two-minute paper. That option goes to a v1.1 issue and is revisited after the M4 run. The cause is the affiliation chunks, spoken about 30 % slower.
- **Status:** "Decided (Claude)", with the time Colin was told set to 17:14:26, the post's creation time. The author was right to use the post's time over the handoff's "17:15".
- **D-159's note** is correctly left at "D-380 to D-382", because D-383 keeps D-159's rule rather than revising it.
- **D-382's Record cell** now cites D-286, which answers round 8's note.
- **Form:** D-383 sits above D-382, has 6 cells, and was the next free number. The PR title and body cover it, and there is still no closing keyword before a link.

## Must fix

**M1. D-382 and D-383 give different worst errors for the same setup.** D-382 says that with D-380 and D-381 and the first estimate at 1,000 characters, "the worst recorded error is 21 %" (and D-380 says 39 % falls to 21 %). D-383 says that keeping the first chapter, which is that same setup, leaves "the worst replayed error on pymedphys" at 24 %, and that skipping it would cut this to 14 %. A reader can't tell which is right. Both numbers come from the coordinator: the 17:00 handoff and post give 21 %, and the 17:14 handoff and post give 24 %. They probably come from different replays (for example before and after the final code, or a different set of runs). I've asked the coordinator which numbers belong together. Then either say in D-383 what the 24 % was measured on, so it doesn't read against D-380 and D-382, or correct whichever figure is wrong.

**Approval is held at 8313334 until M1 is settled.** Everything else in this round is approved.
