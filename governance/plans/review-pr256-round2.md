# Review of PR #256 (#101 German links and citations), round 2

Head 625bb7f (round 1 fixes on 478a485; main 3b9ac6d, branch up to date). Author's answer: https://github.com/dubidu22/sci2audio/pull/256#issuecomment-6874934613

## Round 1 items

- **M1 fixed.** `_starts_sentence` and `only_links_before` skip a full stop that ends one of the language's abbreviations (`LinkWords.abbreviations`, from `data/<lang>/abbreviations.toml` without the `can_end_sentence` entries, plus `utterances.ABBREVIATIONS`). German chains up to two `before` words with the link. Probed again: "Die Daten liegen z. B. unter https://x.org. Dann mehr." → "Die Daten liegen. Dann mehr."; "u. a. unter …" → "unter anderem. Dann mehr."; "ggf." → "gegebenenfalls. Dann mehr."; English "e.g. https://x.org. Then more." → "for example. Then more." (pinned by `links-after-an-abbreviation-keep-the-full-stop`, fails on main).
- **M2 fixed.** "bzw."/"bzw" are German joins and before words; `_dangling_join` keeps joins that end in a full stop. "Die Daten bzw. https://x.org sind neu." → "Die Daten sind neu."; "Mehr bei https://a.org bzw. https://b.org." → "Mehr."
- **S1 fixed.** "(Abruf: 3.5.2017)" goes with its link; "Die Seite https://x.org/r, abgerufen am 3.5.2017, zeigt es." → "Die Seite zeigt es." A note followed by a number keeps the comma ("…, 14 Uhr" → "Die Seite, 14 Uhr."), as it should.
- **D1 deferred** into #253 (v1.1): https://github.com/dubidu22/sci2audio/issues/253#issuecomment-6874934454

## Checks on 625bb7f

- CI: every job green.
- Fast suite locally: 4131 passed, 1 skipped.
- Corpus, all 13 files, main vs PR: English scripts byte-identical except the accepted Markdown line; German paper as in round 1.
- Nightly profile on the German links and citations module plus the English links and citations modules, seeds 11, 21, 31: clean (329 passed each). Seed 41: one failure in `test_no_citation_is_left_and_no_word_is_lost`, "( [12]; see Smith (2019))" read as "()". The same on main 3b9ac6d, so not this PR: filed as #259 (v1.0.1).
- My German fuzz (3000 blocks, new seed): 8 second-run differences, all of the D1 shapes now in #253 (a removed citation before "2019. Dann", "Kap." before a link).

## New in round 2 (deferred, not blocking)

- **#258 (v1.2):** a link removed after an abbreviation that stays as printed leaves two full stops in the script: "Smith et al. https://x.org. Then more." → "Smith et al.. Then more." (main "Smith et al. Then more."), also "Fig..", "Dr..", German "Abb..". The sentence end is now right for listening (two utterances, where main made one), so this is a script-text blemish, and a fix needs the abbreviations step too (when that step reads "u. a." as words, its full stop goes, and the link's full stop must stay). English hand-made text only; the English corpus has no such case.

## Verdict

Approved. Squash-merged on the coordinator's standing instruction: main 1a5950f (14 Nov 2026, 09:08 UTC). Issue #101 closed.
