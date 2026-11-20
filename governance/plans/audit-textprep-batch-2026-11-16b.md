# Light batch audit: textprep v1.2 second batch, PRs 5 and 6, 16 Nov 2026

Scope: the two squash commits on main, #436 6a2aeb3 (parent 71ca0aa) and #450 7cd84bd (parent 1bace26, pinned to b26e993). I read them together as one batch, looking only for cross-PR inconsistencies and layer-contract touches (D-627 item 6). Read-only, one pass, Opus medium. No mutation or nightly runs. I did not re-review either PR's own logic; the review reports (plans/review-pr450-round1..3.md and the #436 rounds) cover that.

Method:
- Read the PR 5 and PR 6 plans and the previous audit (plans/audit-textprep-batch-2026-11-16.md).
- Read the src diff of each commit. Files both PRs touch: `testing/documents.py` (`rebuilt_from_script`), `testing/text_steps.py` (SAMPLE_DOCUMENTS, conformance), `textprep/__init__.py`, `textprep/placeholders.py`, both regression TOMLs and two test files.
- The cross-PR question is how PR 5's new pieces (hidden-run step, affiliation-mark step, figure alt text in the notice, pictures kept in `rebuilt_from_script`) meet PR 6's new pieces (notice names read through the inline chain in a small document, placeholders rebuilt as printed, the D-710 own-output check inside placeholders).
- Probes on main 7cd84bd through the whole chain (`run_steps` with defaults), en and de, with categories on and off. Scripts in the thread's scratch (`/home/user/probe/`), not kept.

## Verdict

**The batch is sound for default settings. Missed findings: B 0, S 2, N 0.** Both are places where PR 5 made an assumption that PR 6 then changed the ground under. Neither breaks the second-run guarantee and neither touches a contract.

What holds:
- `rebuilt_from_script` collects the pictures' alt texts before PR 6's placeholder branch, so a figure rebuilt as printed keeps its alt text and the second-run notice is the same.
- PR 6's small document for `_read_in_place` keeps every line, picture and drawing its blocks use, so the hidden-run step and the links/citations `hidden_removals` act there as in the full document. A hidden run inside a caption label: "Abbildung 3.1 SECRET: Verlauf." reads "Abbildung 3 Punkt 1 wird übersprungen." / "Abbildung 3 Punkt 1: Verlauf." in de.
- `AffiliationMarkStep` takes only PARAGRAPH blocks of the first page up to the first heading, and blocks with parts. PR 6's small documents hold a placeholder plus CAPTION blocks, or a part-less PARAGRAPH (the formula notice), so the step never fires there. No interaction.
- Regression TOMLs: english 215 cases, german 170, no duplicate ids.

## Findings

### Should fix

**S1. Hidden runs inside a placeholder are read when its notice is switched off. Filed as #463 (v1.2, lane:textprep).**

PR 5's `HiddenRunStep` skips every placeholder because "a placeholder is replaced by its notice". With its notice category switched off, the placeholder's printed text is read, and PR 6 (D-710) made that a cleaned reading (soft hyphens, ligatures, line-end hyphens, with an own-output conformance check). Hidden runs and page-break markers are the one cleanup left out.

| TABLE `Group 13 Mean SECRET 4.2` (13 = epub:pagebreak, SECRET = hidden) | reads |
|---|---|
| Tables and figures on (default) | `A table is skipped.` |
| Tables and figures off | `Group 13 Mean SECRET 4.2` |

Fix: skip a placeholder only while its notice category is on; add a sample placeholder with a hidden run so the D-710 check covers it.

**S2. A figure's alt text is read raw inside its notice, unlike the notice's name. Filed as #464 (v1.2, lane:textprep).**

PR 5 (#191) appends alt text to the notice and, by its plan, no inline step reads it. PR 6 (D-707) made notices read their names through the inline chain because raw notices sound wrong. Alt text is free text, so it is the larger case:

| | Notice with alt text | Same text as a paragraph |
|---|---|---|
| en | `It shows: Share of 3.5 % at 12 m² (Smith, 2019), see https://x.org, e.g. p < .05.` | `Share of 3.5 % at 12 square metres, for example p less than .05` |
| de | `Sie zeigt: Anteil 3,5 % bei 12 m² (Müller, 2019), vgl. https://x.org.` | `Anteil 3 Komma 5 Prozent bei 12 Quadratmeter,` |

Fix: read the alt text through `_read_in_place` as a PARAGRAPH, as PR 6 does for a formula notice. Second run stays stable since the figure comes back as printed with its pictures.

## Contract touches (checked, none)

- **Text-step interface, `StepContext`, core dataclasses:** unchanged. `TEXT_STEP_API` stays 1. PR 5 adds two built-in steps (`hidden-runs` in PAGE_FURNITURE, `affiliation-marks` in FOOTNOTES), both INLINE, placed in `BUILT_IN_STEPS` as the registry docstring says. No new category or switch.
- **Public `textprep` names:** PR 5 exports `AffiliationMarkStep` and `HiddenRunStep`; PR 6 exports `read_over` (moved from `testing.documents._mapped`, same body). `Wording` gained a required `shows` field (PR 5); both built-in wordings set it. A plugin that builds its own `Wording` would now need it, but the plugin interface is not public until #216 (v1.4), so no break today; worth a line when #216 freezes it.
- **Removed helper:** `numbers_de.label_numbers_read` (PR 6) has no caller left in src or tests.
- **Layering:** `testing.documents` now imports `textprep.read_over`; testing sits above textprep, allowed. `placeholders._read_in_place` imports `registry` and `runner` inside the function (they import `placeholders`): a cycle inside textprep only, like `links._stop_after_abbreviation` in the last batch. PR 5's `links` and `citations` import `furniture` at module level; `furniture` imports neither, no cycle.
- **`link_removals` language (#428, last audit's S1):** fixed in PR 5, and the `"en"` default on `_block_edits` is gone, so no caller can leave it out again.
- **Reason texts:** PR 5 "a short notice with its alt text is read instead (D-55)" extends the existing notice reason; `affiliation mark "…" is not read` matches the footnote-mark wording. PR 6 changes no reason text.
- **Second-run guarantees and the conformance suite:** PR 5 widened `rebuilt_from_script` (pictures kept); PR 6 changed it (placeholders as printed, `own_output`) and added the D-710 inside-placeholder check. Both are `sci2audio.testing` changes that the plan and review treated as critical. SAMPLE_DOCUMENTS gained the title, hidden-run and alt-text document (PR 5) and two placeholder documents (PR 6); none removed. No property `assume` or test was weakened in either diff.
- **Golden files:** PR 5 changed the corpus, layout-language and furniture snapshots (accepted in its review); PR 6 changed no golden file (corpus byte-identical per round 2/3).

## Not findings (checked, fine)

- A footnote mark glued to a caption label's number ("Abbildung 3.1¹") is not taken out by the footnotes step even in a paragraph (reads "3 Punkt 11"), so the notice ("3 Punkt 1") and the caption differ. This is older than the batch (the footnotes step, not PR 5 or 6) and outside a light audit; left for the coordinator to file if wanted.

## Workflow verdict (D-627 item 6)

| | B | S | N |
|---|---|---|---|
| Found by the batch review (#436 r1–r3, #450 r1–r3) | 4 (#436 r1 B1 B2, r2 B1; #450 r1 B1) | 6 (#436 r1 S1, r2 S1; #450 r1 S1 S2, r2 S1 S2) | 2 (#436 r1 N1 N2) |
| Missed, found by this audit | 0 | 2 (S1 #463, S2 #464; both need a non-default switch or alt text, no second-run break) | 0 |

Thread lifetime: one lane thread did PRs 4, 5 and 6 with 0 compressions, but PRs 5 and 6 each took three review rounds, and both audit findings are PR 5 assumptions that PR 6 overturned. The PR 6 plan reasoned about notices and placeholders as a model ("text read when a notice is off is cleaned", "notices read as the chain does") without walking back over what PR 5 had just added to the same blocks. That is a cross-PR blind spot, not context loss, so a shorter thread would not have caught it. Judgement: **keep lane threads at the current length** (one batch, replace at 2 compressions); add to the plan template for a PR that changes a rule's model: "list what earlier PRs in this batch built on the old model and say what happens to each".
