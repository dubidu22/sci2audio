# #285 plan: a grant or award number in brackets is not read (en + de)

Source: Colin's listening test, seaborn paper Acknowledgements: "IGERT program (0801700)", "Simons Society of Fellows (527794)". Milestone v1.0.1, textprep lane, critical (English rule, English regression cases, corpus script golden file).

## Measured on main (d91a074)
- Neither chain touches `(0801700)`, `(527794)`, `(DMS-1912345)` or `(FKZ 01IS18026A)`, so the voice reads the digits.
- Across the 13 corpus scripts, only these two seaborn brackets have the shape. The nearest look-alikes are dataset names that must stay: `(OPP-115)` and `(that is, OPP-115 and APP-350)` in acl2023-chi-plue.

## Rule
A round bracket whose whole inside is one or more identifiers is removed for the voice. It uses the same space and punctuation handling as a removed citation: "Fellows (527794)." reads "Fellows."

An identifier is either of these:
1. A bare digit run of 5 or more digits, with no grouping: `(0801700)`, `(527794)`, `(0801700, 527794)`.
2. A code made of letters and digits, joined by "-" or "/", that holds a digit run of 5 or more: `(DMS-1912345)`, `(01IS18026A)`. It may come after a funding word: en "grant", "grants", "award", "contract", "project", "no.", "grant agreement no."; de "Förderkennzeichen", "FKZ", "Projekt", "Nr.".

These stay and are still read:
- years, `(2019)` and `(2019a)`, which are 4 digits
- small numbers, `(3)` and `(12)`
- grouped quantities, `(12,345)`, `(12.345)` and `(12 345)`
- quantities with a sign, unit or label, `(n = 12345)` and `(5 %)`
- names with short numbers, `(OPP-115)`, `(GPT-3)`, `(ISO 9001)`, `(ResNet-50)` and `(COVID-19)`
- anything with other words, `(see grant 527794 for details)`

## Where
In the citations step (`citations.py`), as one more kind of bracket in `_decide`, ahead of the author-year rules.
- The step already owns the bracket tree, the space and punctuation tidy-up, and the second-run rules.
- Category: citations (TP-03), so the existing "Citations" switch also reads identifiers again.
- Reason: 'identifier "(0801700)" in brackets, such as a grant number, is not read (TP-03)'.
- A new module would be the first of its kind and would repeat the bracket parsing, so I don't recommend it.

## What the listener and the reader get
- The spoken script leaves the bracket out.
- The read-along and the review page show the printed text, as for every edit.
- The report lists each removal with its reason.

## Tests (first)
- English regression case: the seaborn sentence shape, a lettered code, and a "keeps" block (`(2019)`, `(12,345)`, `(OPP-115)`, `(n = 12345)`, `(3)`).
- German regression case: the same shapes, plus `(FKZ 01IS18026A)` and `(Förderkennzeichen 01IS18026A)`.
- Unit tests in test_textprep_citations.py and test_textprep_links_citations_de.py: removal and keeps, pinned on both runs.
- The existing Hypothesis contract and second-run properties cover any text.
- Corpus golden file (`test_app_corpus.ambr`): only the two seaborn brackets change, and the PR shows that diff.
- Full fast suite, nightly seeds, corpus byte check against main.

## Open edge (my recommendation in brackets)
An ungrouped count of 5 or more digits in brackets, such as "participants (12345)", would be dropped. [Accept. Papers group large counts or label them ("n = 12345"), and a leading-zero or lettered code is an identifier either way. The alternative is to drop only with a funding word nearby, which would miss both seaborn cases, whose funding words are far before the bracket.]

## Size
About 40 lines of code and 100 lines of tests. One PR with labels textprep and risk:high, milestone v1.0.1. The base is main, and it is forwarded to release/1.0 only if the coordinator wants it in v1.0.1 through the release branch.
