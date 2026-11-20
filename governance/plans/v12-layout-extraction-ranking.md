# v1.2 layout and extraction issues: ranking (14 Nov 2026)

Measured on main 57f9fd2 (Python 3.12.3, Linux), all 8 corpus papers through `extract_pdf` + `build_document`.
Open v1.2 (milestone 4) issues labelled lane:layout or lane:extraction: #28 #156 #158 #165 #174 #175 #185 #202 #238 #281 #282 #283 #284 #298.
Not mine: #223 #240 (German line-end hyphens, textprep lane). Layout edge cases #122 #125 #126 #181 are v1.3 (D-460).

| Rank | Issue | What the listener hears wrong today | Corpus reach (measured) | Size | Critical |
|---|---|---|---|---|---|
| 1 | #202 inline stacked fraction glued ("eℏ2me") | numerator and denominator read as one token, e.g. "µB = eℏ2me" | liu: the 3 cases in the issue, all still present. A probe of every no-space join under earlier letters finds 49 in liu and 19 in nowak, but most are legitimate sub/superscripts (σ^ext_OH); the plan must separate true fractions from scripts | S–M (layout `geometry.separators`) | yes: liu (maybe nowak) layout goldens + English regression cases (named in D-457 as "stacked-fraction spacing", D-442) |
| 2 | #174 + #158 + #165 input limits (D-377) | nothing on real files; a hostile or absurd Markdown/text/EPUB (14–45 GB for a 64 MB file) or a 2 MB cover PNG (2 GB in ffmpeg per run) exhausts memory | none (every sample reads far below any sane limit) | M together: one item limit shared by Markdown, text, EPUB + cover pixel limit from PNG IHDR / JPEG SOF; broken-file tests per format | no (needs one decision: the numbers) |
| 3 | #185 (+ #28) PDF in a child process | nothing on real files; a 1 MB Flate bomb costs 3.3 GB and nested forms 2 GB inside PDFium before our limits run | none; corpus must still read, extraction time in baseline.md not worse than process start | L: child process with memory and time limits, Windows needs a job object or watchdog; the same worker also ends the whole-document PDFium lock (#28) | not by the definition, but an architecture decision (process boundary, D-65) |
| 4 | #156 small repeated edge lines taken for running heads | a `\small` continued table header or "Algorithm 1" caption at a page top is dropped as furniture | none (nowak's 5 Algorithm captions are not at page edges; JOSS footers must stay furniture) | M | no, unless goldens move (none expected) |
| 5 | #175 HTML reader result depends on Python patch | broken markup only: differs between Python 3.12.10 and 3.12.11+ | none (well-formed files identical) | M | no; would let us drop the 3.12.16 pin (D-378). Note: uv 0.11.32 in this sandbox has no 3.12.16 download, so `uv sync` fails here without UV_PYTHON |
| 6 | #283 + #281 code notices | "A code block is skipped." twice for a listing over a page break; "A code block" instead of "Listing 3" | none: seaborn has one CODE block on one page, no Listing caption in the corpus | S each | #281 adds a regression case (critical) |
| 7 | #238 figure labels counted as text columns | nothing today (maass p3 reads in order) | maass p3 only | S–M | no |
| 8 | #298 extraction timing tests to ratio helper | nothing (test robustness) | n/a | S | no |
| 9 | #282 code indentation, #284 code in plain text | #282 player view only; #284 pasted code read aloud | none | M each; #284 is a heuristic with false-positive risk | no |

## Recommendation

1. **#202 first.** It is the only one Colin hears on a corpus paper, D-457 names it for v1.2, and it is small. Critical (goldens), so the plan waits for approval.
2. **Then the limits batch #174 + #158 + #165** under one plan: same shape (refuse too-large input before memory runs out with "too large or damaged"), same lane, non-critical.
3. **Then #185 + #28** as one plan: the PDF worker process fixes both; largest item, needs decisions on limits and Windows.
#298 can ride along with the limits batch (same test files, `linear_time.py`) if the coordinator wants it out of the way.
