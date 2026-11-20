# Review PR #425, round 1 (textprep batch 2 PR 4: line-end hyphens #240, adjective pairs #223)

Head reviewed: 12de0d3, on main 6ee82d4. Plan: plans/textprep-v12-pr4-plan.md (D-685). Critical (truth file `line-end-hyphens-de.toml`, the #96 regression case text, the maass corpus snapshot).

**Verdict: approvable at 12de0d3.** It closes #240 and #223. The heavy checks ran in this round. There are no fix items and no new leftovers; the author already filed #423 (English split-again) and #424 (adjective pairs without an ending). Nothing is merged.

## What I checked

- **Plan.** The change follows D-685. `HyphenWords` gets `split_again`, `chain_words` and `adjective_pairs`; German turns all three on, English none. The PR body closes #240 and #223, and the commit messages carry no closing keywords. `mergeable_state` is clean.
- **Probes.** About 50 hand rows (de and en) ran through the whole chain twice, against main 6ee82d4. Every reading is the same on both runs, and every row of both plan tables reads as planned.
  - **#240 split again.** A hyphenated word split at a line end joins unless its last part is a chain word: "Open-Source-/basierte", "Max-Planck-/institute" and "Rhein-Main-/region" join. "Ad-hoc-/Analyse" (capital after), "Peer-to-/peer-Netz" and "Ende-zu-/Ende-Prinzip" (chain words) stay. Chain words are compared as printed, so "Ende-Zu-/ende" joins (a pinned mutant guards `lower()`).
  - **Accepted cost.** "E-Mail-/basiertes" reads "E-Mailbasiertes" and "Ad-hoc-/analyse" reads "Ad-hocanalyse", as the plan says. The three joins above are the same cost class. Accepted.
  - **Kept as printed.** "COVID-19-/bedingte", "SARS-CoV-2-/spezifische", "3-D-/gedruckte" and "EU-DSGVO-/konforme" keep their hyphen.
  - **#223 adjective pairs.** "deutsch-/französische" and the other plan rows keep the hyphen; endings sch, lich, ig, al, iv, iell, uell, rell, nell, mell, är with the five inflections, stems of 3 before and 4 after. "rot-/grüne" joins (#424). "Deutsch-/französische" at a sentence start joins, because the first part must be lower case.
  - **Rule 3 precedence.** A pair printed closed elsewhere in the document is joined, before the adjective rule.
  - **#96 case text.** `de-hyphen-inside-word-kept` now prints "Ad-hoc-\nAnalyse" with a capital. With a capital after the line end the hyphen stays, so the case keeps its purpose (a hyphen inside a word is kept) under the new rule; "Peer-to-\npeer-Netz" stays through the chain word "to". Accepted.
  - **English unchanged.** "state-of-the-/art" is kept, "non-differen-/tiable" reads as on main (#423), and "deutsch-/französischen" in an English text joins as on main.
- **Regression cases.** Of the new German cases, `de-hyphen-split-again-joined` and `de-hyphen-adjective-pair-kept` fail on main; the rest pin behaviour that main already has. The one `[[miss]]` in `line-end-hyphens-de.toml` is gone, because the PR now reads it right.
- **Corpus:** 13 documents against main 6ee82d4. Only maass line 326 changes: "Datenschutz-/Grundverordnung" joins, as the plan says, and the snapshot shows that one join. Every other file is byte-identical.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 6206 passed, 1 skipped.
- **Token fuzz:** 9,000 texts (seeds 21–23, de and en) from hyphen, chain-word, adjective and capital tokens. The whole chain ran twice against main. No crashes, no text that differs on a second run on either side, and no English reading that differs from main.
- **Mutants.** The author's `mut3.py` on ROOT = 12de0d3, baseline passed. The author's 1, 8, 13, 17 and 20 are killed, as claimed. Five of mine are killed too: `last_part.lower()` in the chain check, `>` for `_STEM_BEFORE`, `>` for `_STEM_AFTER`, `_adjective_pair` on the whole `before` instead of its last part, and `chained` forced False. Every KILLED line names a failing test that hits the mutant. The author's full run reports 22 of 22 killed, each with a named test.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`; hyphens, German regression, conformance, runner): seeds 2024 and 123456, 629 passed each.
- **CI with `ci:full`** on 12de0d3: tests on ubuntu, macOS and Windows, browser, lint and layers, licences, security and CodeQL are all green.

## Fix list

None.

## Leftovers

None new. Already filed by the author: #423, #424.

## Merged

Squash-merged pinned to 12de0d3 as **e107f64** (D-690). #240 and #223 are closed.
