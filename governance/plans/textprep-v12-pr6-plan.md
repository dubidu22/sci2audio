# Plan: textprep v1.2 second batch, PR 6: placeholder labels on a second run (#362, #370, #374; finishes #249)

Branch `textprep/placeholder-labels` from main 6a2aeb3. Lane textprep. **Critical** (`risk:high`): it changes the second-run oracle in `sci2audio.testing` (`rebuilt_from_script`, used by the conformance suite) and adds English and German regression cases. Size: medium (about 300 to 450 lines, half of them tests).

## What happens today (probed on 6a2aeb3, whole chain twice)

| lang | printed | run 1 notice | run 2 notice |
|---|---|---|---|
| en | `Figs. 1–3: Values.` | Figures 1–3 is skipped. | Figures 1 to 3 is skipped. |
| en | `Fig. 1/2 shows x.` | Figure 1/2 … | Figure 1 half … |
| en | `Fig. 10⁶ shows x.` | Figure 10⁶ … | Figure 10 to the power of 6 … |
| en | `Fig. 3x shows x.` | Figure 3x … | Figure 3 times … |
| de | `Tab. 3x: Verlauf der Werte.` | Tabelle 3x wird übersprungen. | Tabelle 3 mal wird übersprungen. |
| de | formula labelled `3.2` | Formel 3.2 wird übersprungen. | the same (wanted: Formel 3 Punkt 2, #362) |

Why: run 2 names a figure by its caption's label as the caption was read (the label is mapped through the script, #324/#353), while run 1 reads the label with the German numbers rule only (`numbers_de.label_numbers_read`, #368) or as printed (English). A formula has no caption: its label is kept on the rebuild only while the notice prints it, so a notice that reads "3 Punkt 2" would lose the label and run 2 would say "Eine Formel wird übersprungen." (#362).

## Design

### 1. Caption labels read as the whole chain reads the caption (#374, #370)

The notice steps name a figure or table by its caption label **as the built-in inline steps read that caption**, not by one step's rule:

- New `placeholders._caption_readings(document, context)`: a small document of the caption blocks alone (same language, same switched-off categories), run through the built-in INLINE steps (`registry.BUILT_IN_STEPS`, imported inside the function to avoid the import cycle), and each caption label's printed span mapped through that run's script. Captions are few, so this is cheap.
- The mapping is the one the rebuild already uses (`testing.documents._mapped`). It moves to `sci2audio.textprep` (public helper `read_over(printed, script, start, end)`), and `sci2audio.testing` imports it from there, so the step and the oracle use one rule.
- `wording.label` still gives the word in full when no step expands it; a label whose span a replacement runs past keeps today's reading, as the rebuild drops such a label.
- `numbers_de.label_numbers_read` is no longer needed by the notice; German readings stay as they are (the German numbers step is part of the chain; the #368 cases must pass unchanged).
- Same result as run 2 by construction, in both languages, for every built-in step and every switch: "Figs. 1–3" reads "Figures 1 to 3", "Tab. 3x" "Tabelle 3 mal", "Fig. 3x" "Figure 3 times", and "Abbildung 3/4: Verlauf" keeps "3/4" as its caption does.

Alternative (not recommended): extend the per-rule reading to English numbers and add the units step's multiplier rule. It fixes the table's rows but not the next rule that reads a label (statistics, abbreviations inside a label), so the second-run gap would come back with each new rule.

### 2. Placeholders rebuilt as printed (#362; the decision the issue asks for)

`rebuilt_from_script` rebuilds a placeholder block (formula, table, figure, code) **with its printed text, label and pictures**, instead of with its notice. The notice is a function of the printed placeholder and its captions only, so the second run makes the same notice again, whatever words the notice uses for the label.

- Then a German formula notice reads its label in its own context: the notice's name ("Formel 3.2") is read through the inline steps as above, so "Formel 3.2 wird übersprungen." reads "Formel 3 Punkt 2 wird übersprungen." (the German numbers step's label rule). English formula notices are unchanged ("Formula 3.2 is skipped."; the English chain reads no label number there; probed).
- The special case that carries figure pictures' alt text into the rebuild (#191) becomes part of this rule (a placeholder keeps its parts).
- **What the conformance suite checks for placeholders (the issue's open point):** `check_text_step` reruns a step on the rebuilt document. A placeholder block now comes back as printed, so a step's second look at a placeholder sees the printed block again, not its own notice. That loses nothing for the built-in steps: notice steps replace the whole block, every other built-in step skips placeholders (`SKIPPED_KINDS`), and the runner never lets a later step edit inside a notice (the earlier edit wins the overlap). To keep that true for any step, the suite gets one new check: an edit inside a placeholder block must replace the whole block. The PR body states this, and the KB note records the rule.
- Rejected alternative: keep the notice as the rebuilt text and carry a label mapped into the notice ("3 Punkt 2"). The oracle would then have to know how each notice spells its label, which is the step's own logic inside the oracle.

### Out of scope

Plugin steps outside the built-in list do not take part in the caption reading (a plugin that rewrites caption numbers would show a second-run difference; none exist). Follow-up issue if wanted.

## Tests (first, failing on 6a2aeb3)

- English regression cases: the five #374 rows and `Fig. 3x`, notices and captions, both runs.
- German regression cases: `Tab. 3x: Verlauf der Werte.` (#370), a formula labelled `3.2` reading "Formel 3 Punkt 2 wird übersprungen." and one labelled `16a` unchanged (#362), "Abbildung 3/4: Verlauf" unchanged.
- `test_testing_rebuilt_from_script.py`: placeholders come back with printed text, label and pictures; captions still mapped (#324 cases unchanged).
- Conformance: the new whole-block check, with a bad sample step that edits inside a placeholder and must be refused; every built-in step still passes.
- Unit tests for `_caption_readings` with a category switched off (numbers off: label as printed, as run 2 reads it).
- Corpus: the 13 documents, scripts and reports diffed against main, each change listed (expected: English figure and table notices with ranges, fractions or powers in their labels; none expected in German).
- Mutation on the changed lines (`mut3.py`, clean worktree, baseline first), fuzz on captions with label shapes (en/de) through the chain twice.

## Decision asked

Approve design 1 (caption labels through the whole inline chain) and design 2 (placeholders rebuilt as printed, plus the whole-block conformance check). D-number for the KB note from the coordinator.
