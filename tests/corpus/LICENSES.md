# Sample corpus: sources and licences

Only texts we may share: our own writing, public domain, CC0 or CC BY (with attribution). Never add copyrighted papers or books, not even for a quick test.

Rules, checked by `tests/unit/test_corpus.py` on every PR:

- Every file in `tests/corpus/` has exactly one row below, and every row names a file that exists.
- `Licence` is one of `CC0-1.0`, `CC-BY-2.0`, `CC-BY-2.5`, `CC-BY-3.0`, `CC-BY-4.0` or `public domain`, as stated at the source.
- No file over 1 MB; the whole corpus under 10 MB; 5 to 10 papers (`papers/*.pdf`) and at least one EPUB (`epub/*.epub`).
- Files are stored exactly as downloaded, so their content matches the source; files written for sci2audio (`markdown/`, `text/`) are stored byte for byte as written (`.gitattributes` turns off line-end conversion).

`Covers` names the layout and text features a file is meant to exercise, so tests can pick the right sample: two-column, footnotes, tables, formulas, citations, URLs, code, pseudocode, examples, chapters, hard-wrapped paragraphs, hyphenation.

| File | Title | Authors | Source | Licence | Covers | Added in |
|---|---|---|---|---|---|---|
| `papers/acl2023-nowak-prefix-probabilities.pdf` | A Fast Algorithm for Computing Prefix Probabilities (ACL 2023, short papers) | Franz Nowak, Ryan Cotterell | https://aclanthology.org/2023.acl-short.6.pdf (ACL Anthology: materials from 2016 on are CC BY 4.0, https://aclanthology.org/faq/copyright) | CC-BY-4.0 | two-column, formulas, footnotes, pseudocode, citations, URLs | #15 |
| `papers/acl2023-hardt-ellipsis.pdf` | Ellipsis-Dependent Reasoning: a New Challenge for Large Language Models (ACL 2023, short papers) | Daniel Hardt | https://aclanthology.org/2023.acl-short.4.pdf (licence as above) | CC-BY-4.0 | two-column, tables, examples, footnotes, citations, URLs | #15 |
| `papers/acl2023-chi-plue.pdf` | PLUE: Language Understanding Evaluation Benchmark for Privacy Policies in English (ACL 2023, short papers) | Jianfeng Chi, Wasi Uddin Ahmad, Yuan Tian, Kai-Wei Chang | https://aclanthology.org/2023.acl-short.31.pdf (licence as above) | CC-BY-4.0 | two-column, tables, footnotes, citations, URLs | #15 |
| `papers/joss2022-biggs-pymedphys.pdf` | PyMedPhys: A community effort to develop an open, Python-based standard library for medical physics applications. JOSS 7(78), 4555, doi:10.21105/joss.04555 | Simon Biggs, Matthew Jennings, Stuart Swerdloff, Phillip Chlap, Derek Lane, Jacob Rembish, Jacob McAloney, Paul King, Rafael Ayala, Fada Guan, Nicola Lambri, Cody Crewson, Matthew Sobolewski | https://joss.theoj.org/papers/10.21105/joss.04555.pdf (licence in the PDF sidebar) | CC-BY-4.0 | citations, URLs | #15 |
| `papers/joss2021-waskom-seaborn.pdf` | seaborn: statistical data visualization. JOSS 6(60), 3021, doi:10.21105/joss.03021 | Michael Waskom | https://joss.theoj.org/papers/10.21105/joss.03021.pdf (licence in the PDF sidebar) | CC-BY-4.0 | code, citations, URLs | #15 |
| `papers/arxiv2024-liu-orbital-hall.pdf` | Dominance of extrinsic scattering mechanisms in the orbital Hall effect: graphene, transition metal dichalcogenides and topological antiferromagnets. arXiv:2308.14878v2 | Hong Liu, Dimitrie Culcer | https://arxiv.org/pdf/2308.14878v2 (licence on https://arxiv.org/abs/2308.14878) | CC0-1.0 | two-column, formulas, citations | #15 |
| `papers/arxiv2024-arsiwalla-qualia-meaning.pdf` | Qualia and the Formal Structure of Meaning. arXiv:2405.01148v1 | Xerxes D. Arsiwalla | https://arxiv.org/pdf/2405.01148v1 (licence on https://arxiv.org/abs/2405.01148) | CC-BY-4.0 | footnotes, formulas, citations, URLs | #15 |
| `epub/wells-the-time-machine.epub` | The Time Machine (1895) | H. G. Wells | https://standardebooks.org/ebooks/h-g-wells/the-time-machine (text public domain in the US; Wells died 1946, so also public domain in life+70 countries; Standard Ebooks dedicates its own work under CC0 1.0) | public domain | chapters, footnotes (one endnote) | #15 |
| `markdown/sci2audio-sample-note.md` | Listening to Papers: a Pilot Note (a made-up research note) | written for sci2audio | written for this repository (#74); no third-party text | CC0-1.0 | headings, footnotes, tables, formulas, code, URLs | #74 |
| `text/sci2audio-sample-plain.txt` | Listening to Papers (a made-up note in plain text) | written for sci2audio | written for this repository (#74); no third-party text | CC0-1.0 | hard-wrapped paragraphs, hyphenation | #74 |
| `markdown/sci2audio-beispiel-notiz.md` | Papers hören: eine Pilotnotiz (a made-up research note in German) | written for sci2audio | written for this repository (#219); no third-party text | CC0-1.0 | headings, footnotes, tables, formulas, URLs | #219 |
| `text/sci2audio-beispiel-text.txt` | Papers hören (a made-up note in German plain text) | written for sci2audio | written for this repository (#219); no third-party text | CC0-1.0 | hard-wrapped paragraphs, hyphenation | #219 |
