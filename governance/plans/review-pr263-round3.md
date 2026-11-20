# Review of PR #263, round 3 (head b57eb38): approved and merged

Author's answer: https://github.com/dubidu22/sci2audio/pull/263#issuecomment-6876330652

- **G1, fixed.** The pre-check now looks for a link start within 48 characters after the white space. "Siehe Kap. <https://x.org/a> 3 dazu." reads "Siehe Kapitel 3 dazu." and "See Fig. <https://x.org/a> 3." reads "See Figure 3.", both stable on a second run. Bracket forms are pinned in both languages.
- **Optional `_GAP`, dropped.** "Siehe Kap." with ten spaces and then a link now reads "Kapitel" on both runs, and this is pinned.
- **Speed.** The abbreviations step alone is linear: 0.30, 0.69, 1.33 and 2.95 s from 52k to 416k characters of `"Kap. https://x.org/a dazu "`. For shapes that pass the pre-check but hold no link (`Kap. a.b.c.d:`, `Kap. www.x.org`), it takes 2.2 to 2.7 s at 16,000 repeats, against about 0.2 s on main. That is the cost of one links pass per block, roughly what the links step itself costs. The whole German chain on 104k characters takes 1.95 s, against 1.8 s on main. Accepted.
- **Re-run on b57eb38:**
  - Fast suite: 4,196 passed, 1 skipped.
  - Corpus: all 39 outputs byte-identical to main 7174f46.
  - Nightly seed 777: 835 passed.
  - Round 1–2 probe sets: no new second-run changes. The remaining one-time differences are F1, F2 and G1 as intended.
- **CI:** green on b57eb38, all three systems, browser, lint, security, licences and CodeQL. The branch is up to date with main.

Deferred in this review: #265 (v1.2) and #266 (v1.1). Moved by plan: the two sentence-end shapes go to the #227/#229 PR.
