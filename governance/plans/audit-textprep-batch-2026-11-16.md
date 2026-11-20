# Light batch audit: textprep v1.2 second batch, PRs 3 and 4, 16 Nov 2026

Scope: the two squash commits on main, #408 ffdd2f9 (parent e517873) and #425 e107f64 (parent 6ee82d4). I read them together as one batch, looking only for cross-PR inconsistencies and layer-contract touches (D-627 item 6). Read-only, one pass, Opus medium. No mutation or nightly runs. I did not re-review either PR's own logic; plans/review-pr408-round1.md and plans/review-pr425-round1.md cover that.

Method:
- Read both plans, both review reports and the 15 Nov audit first.
- Read the src diff of each commit, and the regression, truth-file and snapshot diffs.
- The two PRs share no source file. #408 touches `citations.py`, `links.py` and `units.py`; #425 touches only `hyphens.py`. The only file they both touch is `tests/regression/german.toml`.
- So the cross-PR question is how the line-end-hyphens step (first in the chain) feeds #408's rules. I ran 36 shapes through the whole chain twice (`read_twice`) on three trees: tip e107f64, 6ee82d4 (after PR 3, before PR 4) and e517873 (before the batch). The shapes put a hyphenated word split again, an adjective pair or a chain word next to #408's pairs, page brackets, link join words, #258 stops, subject nests and year shells, in en and de.
- Then I checked every caller of the functions #408 changed.

## Verdict

**The batch is sound. Missed findings: B 0, S 1, N 0.**

- All 36 cross-PR shapes read the same on both runs on all three trees.
- Where #425 changes a word inside a #408 shape, the #408 reading carries the joined word through. For example, "((Müller-Lüden-↵scheid, 2019); (Lee, 2018)) wird zitiert." reads "Müller-Lüdenscheid und Lee wird zitiert." (on 6ee82d4 it read "Müller-Lüden-scheid"). "Wir danken https://x.org und Datenschutz-Grundverord-↵nung-Experten." drops the join word and joins the split word.
- The one finding (S1) is a latent mismatch inside #408 that its review could have caught by grepping for callers. No reading changes because of it.

## Findings

### Should fix

**S1. `link_removals` drops the language that #408 added to `_block_edits`. Filed as #428 (v1.2, lane:textprep).**

For #258, #408 gave `LinkStep._block_edits` a `language` parameter (default `"en"`), so that `_stop_after_abbreviation` can ask `reads_full_stop` in the document's language. The helper `link_removals(text, kind, label, language)` (`src/sci2audio/textprep/links.py:935-943`) still calls `_block_edits(0, text, kind, label, words)`. So for German text it judges the abbreviation with the English list. The helper's docstring says it returns "its edits' spans", which is no longer true for German:

| German text | `link_removals(…, "de")` | `LinkStep` on a German document |
|---|---|---|
| `Daten finden sich u. a. https://x.org. Dann mehr.` | (23, 38): takes the link's full stop | (23, 37): keeps it ("u. a." reads "unter anderem") |

- Kap., z. B., Abb., Bd., S. and usw. before a link give the same spans both ways.
- `link_removals` has three callers: `citations` (line 400), `abbreviations._Removals.past` (line 245) and `statistics_de` (line 213).
- 11 German probes changed no reading on any of the three trees: "u. a.", "z. T.", "i. d. R.", "s. o." and "bzw." before a link, followed by a capital, a citation, a numeric bracket, a "KI" interval, a year or "§".
- Fix: pass `language` through, and drop the `"en"` default so that no caller can leave it out again.

## Contract touches (checked, none)

- **Text-step interface, `StepContext`, core dataclasses:** neither PR imports anything new from `sci2audio.core`. Neither touches `StepContext` or `TextStep`, and neither adds or changes a step id, category or switch.
- **Internal signatures:** `LinkStep._block_edits` got `language` (private; see S1). `HyphenWords` got `split_again`, `chain_words` and `adjective_pairs`, all off by default and off for English. `CitationWords` got `page_lead` and `page_words`, with English defaults and German values.
- **Layering:** `links._stop_after_abbreviation` imports `abbreviations.reads_full_stop` inside the function, because `abbreviations` imports `links`. That is a cycle inside `textprep` only, so the layer contract is untouched and lint-imports passed on both PRs. Note that `citations` already imports `reads_full_stop` at module level.
- **Reason texts:** the shapes are consistent with each other and with older reasons.
  - #408 `_pair` uses `citations "…" are part of the sentence: read as "…" (TP-04)`, the plural of the existing single-citation reason at line 1135.
  - #408's #258 suffix "; its full stop goes too, so no two full stops are read" follows the existing `; "x" after it goes too` pattern of `_leading_join`, which `_join_after` reuses.
  - #425 adds only the cause "an adjective pair" to the existing `hyphen at a line end kept, read as one word: "…" (…)` reason. A split-again join uses the plain join reason with no cause, the same as any rule-6 join (the maass snapshot shows exactly that).
- **Second-run guarantees:** both German and English `SECOND_RUN_EXCEPTIONS` are still empty. #408 adds one `assume` to its new property test (`test_textprep_pairs_pages_and_nests.py`), which excludes the #405 shapes ("abbreviation before a bracket that goes"), named in the comment and already filed. #425 adds no exclusion. No test was removed or weakened in either diff.
- **Truth files and regression cases:** `german.toml` is the only file both PRs changed.
  - It holds 151 cases and `english.toml` holds 185, with no duplicate ids.
  - #425 changed one existing case (`de-hyphen-inside-word-kept`, as D-685 approved) and #408 changed none.
  - `line-end-hyphens-de.toml` lost its one `[[miss]]`, and its header now says so.
  - The only snapshot change is the maass join (#425). #408 changed no golden file (corpus 13/13 identical, per its review).

## Not findings (checked, fine)

- #425's chain words "und" and "oder" overlap #408's link join words. They act in different steps on different shapes: inside a hyphenated word for one, a free word after a link for the other. "Ein Ende-und-↵ende-Test https://x.org und Müller." reads "Ein Ende-und-ende-Test Müller." on both runs.
- English is untouched by #425 inside #408 shapes: "Smith-Jo-↵nes" and "non-differen-↵tiable" read as before the batch. That is the already filed #423.
- `units.py` in #408 carries the two PR 2 follow-ups that its review accepted. The batch does not touch them again.

## Workflow verdict (D-627 item 6)

| | B | S | N |
|---|---|---|---|
| Found by the batch review (#408 r1, #425 r1) | 0 | 0 | 0 (#408 law-kind nit only) |
| Missed, found by this audit | 0 | 1 (S1, latent, no reading change) | 0 |

Thread lifetime looks right:
- The old lane thread did PRs 1 to 3 and passed its fitness checks. It ended after 2 compressions, at the PR 3 merge.
- A fresh thread did PR 4 with 0 compressions and no fix rounds.
- S1 sits in PR 3, the third PR of the old thread. It is a caller left behind when a signature changed, the kind of whole-module view a long context loses. One finding is too few to call it a trend, and the existing rule (replace at the fitness check) already caught that thread.
- Lesson for reviews: when a PR adds a parameter with a default to a function, grep for every caller and check that each one passes it.
