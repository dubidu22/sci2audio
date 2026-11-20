# Review of PR #222, round 1 (German line-end hyphens #96, German reference-list titles #221)

Reviewed 14 Nov 2026 at head e54e0c4 (base main 31b6d16, main has not moved). Critical (new German golden `tests/regression/german.toml`).

**Verdict: changes requested.** Three fixes, one item deferred to issue #223 (v1.2).

## What I checked

- Plan `plans/v11-german-textprep-plan.md` section 2 PR 1 and D-474, D-475, D-481: matches. German row inside the existing steps, same ids, categories and switches; no change to the core dataclasses, the layer contract or the text-step interface.
- CI: all 13 checks green.
- Fast suite locally: 3341 passed, 1 skipped (`HYPOTHESIS_PROFILE=ci`, `-n 8`).
- Changed test files under the nightly Hypothesis profile (hyphens, placeholders, German regression, conformance): 299 passed.
- **English byte-identity:** `sci2audio script` on all 10 corpus documents (7 PDFs, EPUB, Markdown, text) on main and on the PR, with the default settings. Script, report.json and report.md are byte-identical. Only the stdout differs, and only in the output paths.
- The same 10 documents with `--language de`: the hyphen step now runs (as intended). The reference list is still left out, because English names count in German jobs.
- The German golden file, read case by case. Every expected line is right German reading. It has no compound that breaks.
- The app's chapter choice and the step use one table. The app's `REFERENCE_NAMES` is the same object, and the agreement test covers 36 titles. `app.__init__` still re-exports it.

## Hand probes of the hyphen rule (German job)

Right: Bun-/desregierung, Wis-/senschaft, Über-/prüfung, Grö-/ße, Corona-/Pandemie (kept), Wohnungs-/und, Kinder-/bzw., Kinder-/und/oder, Kinder-/&, Werk-/statt, ab-/sondern, so-/wie, Materi-/als (all joined right).

Wrong (fix 1):
- `sowohl Lehr-\nals auch Lernprozesse` reads "Lehrals auch"
- `Kinder-\nu. Jugendhilfe` reads "Kinderu."
- `Ein-\no. Ausgang` reads "Eino."
- `Lehr-\nversus Lernprozesse` reads "Lehrversus"
- `Lehr-\nvs. Lernprozesse` reads "Lehrvs."

Wrong but deferred (#223): `deutsch-\nfranzösischen` reads "deutschfranzösischen", and `sozial-\nemotionale` and `rot-\ngrüne` are joined the same way.

## Fix list

1. **Missing German conjunctions after a suspended hyphen** (`hyphens.WORDS["de"]`). Add these:
   - "als", only when the next word is "auch" (the "sowohl ... als auch" pattern). A bare "als" must not count, because `Materi-\nals` (des Materials) is a real split.
   - "u." and "o.", abbreviations of und and oder. They count only with the full stop right after them.
   - "versus", and "vs." with its full stop.
   - "resp." ("respektive" is already listed, its abbreviation is not).

   Write the cases first in `german.toml`, so the PR shows the main-to-PR diff, and add unit parameters. Also pin three words as left out on purpose, as "joins" unit cases with a one-line reason each:
   - "statt": `Werk-\nstatt` must join.
   - "sondern": `ab-\nsondern` must join, and "Lehr-, sondern" has a comma, so it never reaches the rule.
   - "wie": `so-\nwie` must join.

   English stays unchanged.
2. **More German reference-list titles** (`GERMAN_REFERENCE_TITLES`). Add these, the German counterparts of "Works cited" and "Literature cited", plus the combined title that is common in German theses:
   - "Literaturliste"
   - "Verwendete Literatur"
   - "Zitierte Literatur"
   - "Quellen- und Literaturverzeichnis"
   - "Literatur- und Quellenverzeichnis"

   Add them to the agreement `TITLES` list and give at least one of them a `german.toml` case.
3. **Dangling path in the golden header.** `german.toml` points to `plans/v11-german-measure-misaki.txt`, which is not in the repository (it is a project-notes file). Point to issue #211 or #96 instead, or drop the sentence.

## Deferred

- #223 (milestone v1.2): an adjective pair with the author's own hyphen is joined at a line end ("deutsch-/französischen"). The approved plan has no German second-word list, and the fix needs a measured heuristic. When it happens, the voice reads one long word, which stays understandable.

## Not asked (no change needed)

- `LineEndHyphenStep.find` raises KeyError for a language outside `WORDS` when it is called directly. The runner and `check_text_step` call it only for languages it handles, so this is fine as it is.
