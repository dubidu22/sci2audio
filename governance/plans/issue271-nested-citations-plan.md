# #271 plan: a nested citation reads the same on a second run (en + de)

## Cause
The citations step judges each bracket on its printed text. In "((Müller, 2019) Schmidt, 2020)" the outer bracket is not a citation as printed ("(Müller, 2019) Schmidt, 2020" is no author-year list), so only the inner one goes and the first run reads "( Schmidt, 2020)". A second run then removes that. English has the same rule and the same gap.

## Change (citations.py only)
1. `_visit` decides every bracket once, inner first (a loop, no recursion, so deep nests stay safe), and keeps the decisions.
2. A round bracket that is not a citation as printed is judged again on what it reads once its inner citations are read (each inner edit written in, padded to the same length, so positions stay put). If that reading is all citations, the whole bracket goes on the first run. A bracket left empty ("((Müller, 2019))") goes too.
3. In subject or noun position the names stay, as for a single citation: "((Smith, 2019) Jones, 2020) is cited" reads "Jones is cited" on both runs (main: "( Jones, 2020) is cited", then "Jones is cited").
4. Anything that stays as printed or whose inner edit lies outside the bracket keeps today's decision.

## Measured on the prototype (first run, second run the same)
- de "Text ((Müller, 2019) Schmidt, 2020) hier." → "Text hier." (main: "Text ( Schmidt, 2020) hier.")
- de "(vgl. (Müller, 2019) Schmidt, 2020)" → removed whole
- en "Text ((Smith, 2019) Jones, 2020) here." → "Text here."
- en "(((Smith, 2019) Jones, 2020) Brown, 2021) is cited." → "Brown is cited." (main needed three runs)
- en/de "such as ((Smith, 2019) Jones and Lee, 2020) could" → "such as Jones and Lee could"
- unchanged: "(see also (Smith, 2019); Jones, 2020)" → "(see also)", "(siehe (Müller, 2019))" → "(siehe Müller)"

## Tests (first)
- English regression cases: two new entries (nested citation in running text; nested subject citation). This makes the PR critical, risk:high.
- German regression/script pins for the same two shapes.
- Unit tests in test_citations.py and test_links_citations_de.py: each shape pinned on both runs; deep nest (5,000 brackets) still no recursion error; linear time via the #277 helper once that merges.
- Full fast suite, corpus byte check (en and de against a fresh main baseline), nightly Hypothesis seeds for the citations files.

## Out of scope (follow-up issue, v1.2)
"((Smith, 2019); Jones, 2020)" reads "()" on main and here; stable on a second run, but an empty bracket is read. Separate issue.

## Size
About 60 lines of code, 80 lines of tests. One PR, labels textprep + risk:high, milestone v1.1.
