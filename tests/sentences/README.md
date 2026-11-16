# Sentence sets: where a listener hears a sentence start

Hand-checked sentences of corpus files and two stress sets, for the sentence-boundary metric
(D-715, plan D-719). `tests/unit/test_sentence_boundaries.py` reads each corpus file as a default
job does, takes every utterance that starts a sentence (not one that goes on with a sentence the
length limit cut), and compares where they start with the sentences here
(`tests/unit/sentence_metric.py` says how). Every error it finds must be listed in
`known-errors.toml`, and every listed error must still happen: a fix removes its entry.

## Files

| File | Language | Source | Licence |
|---|---|---|---|
| `acl2023-hardt-ellipsis.txt` | en | `tests/corpus/papers/acl2023-hardt-ellipsis.pdf` (Daniel Hardt, ACL 2023) | CC-BY-4.0, as the paper |
| `acl2023-chi-plue.txt` | en | `tests/corpus/papers/acl2023-chi-plue.pdf` (Chi, Ahmad, Tian, Chang, ACL 2023) | CC-BY-4.0, as the paper |
| `arxiv2017-maass-privacyscore.txt` | de | `tests/corpus/papers/arxiv2017-maass-privacyscore.pdf` (Maass, Laubach, Herrmann, arXiv:1705.08889v2) | CC-BY-4.0, as the paper |
| `sci2audio-sample-plain.txt`, `sci2audio-sample-note.txt` | en | the own English samples in `tests/corpus/text/` and `markdown/` | CC0-1.0 |
| `sci2audio-beispiel-text.txt`, `sci2audio-beispiel-notiz.txt` | de | the own German samples | CC0-1.0 |
| `stress-en.txt`, `stress-de.txt` | en, de | written for sci2audio: shapes a sentence rule can get wrong | CC0-1.0 |

The paper files quote the corpus papers, whose licences allow it with attribution: each file
names title, authors, source and licence at its top (see also `tests/corpus/LICENSES.md`). Only
corpus files and our own writing may be used; never a paper with a personal-use licence. Shapes
found in such a paper are written as our own sentences in a stress set.

## Format

One sentence per line, as printed, in reading order, in UTF-8:

- Line breaks inside a sentence become one space; a hyphen at a line end that only splits a word
  is dropped. Footnote marks and inline maths stay where they are printed (as in the corpus truth,
  `tests/corpus/truth/README.md`). Words are compared by their letters and digits only, so the
  exact punctuation, a ligature or a dash does not change the score.
- A heading, a caption, a title or a list item is a line of its own.
- `~ ` at the start of a line: the line goes on with the sentence above, and a listener may hear
  either one sentence or two (a run-in head before its paragraph, an example set off after a
  colon, a poem's lines). That start counts neither way.
- `---` alone on a line: a gap. The text between is not written down (footnotes, tables, the
  reference list, author blocks, a formula). Each stretch between gaps is matched on its own, so
  stretches may follow in any order (captions are written after the text).
- `# ...` is a comment, `@page N` marks a page for the reader; both are not scored. Blank lines
  are not scored either; in a stress set they end a paragraph of the text file made from it.

A stress set is read from a plain-text file the test writes: the sentences of a paragraph joined
by one space, paragraphs apart by a blank line.

## How a sentence file is made and checked (D-719)

1. Drafted from the PDF with a tool that is not sci2audio (poppler's `pdftotext`, columns cropped)
   and split by hand, never from sci2audio's output, so the truth does not copy the rules it tests.
2. Every disagreement with the script is checked against the page: a truth error is corrected
   (with a `#` comment), a script error is listed in `known-errors.toml` with its Issue.
3. The review checks every disagreement and a random sample of 100 sentence starts per language
   (the seed is in its report).

## known-errors.toml

Each `[[error]]` names its file, `kind` (`FP`: the script starts a sentence the truth does not
have; `FN`: the script misses one), `at` (the truth's words around the gap, as the test prints
them), `class`, `issue` and `why`. `[floors.en]` and `[floors.de]` hold the precision and recall
of the natural sets (all but the stress sets) by language, rounded down to three places; a PR
that raises them raises the floors.
