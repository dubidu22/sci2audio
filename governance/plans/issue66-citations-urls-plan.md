# Plan: issue #66, citations, URLs, DOIs and e-mail addresses (TP-03, TP-04, TP-07)

Thread "Read citations, URLs, DOIs and e-mails", 13 Nov 2026. Lane textprep. Builds on the
text-step interface (PR #83, a57d135) and the utterance cutter (PR #86, 006c964).

**Critical: yes.** The PR changes golden files: `tests/regression/english.toml` (the
`expected` of three audit cases changes, about 30 cases are added), the corpus summary
snapshot of `test_textprep_furniture.py` (new "citations" and "links" rows), the script-job
snapshots of #70 (`test_app_corpus.ambr`) and a new corpus snapshot of every edit the two
steps propose. **No change to core dataclasses, the layer contract or the text-step
interface; no new dependency** (only `re` and `unicodedata`). Label `risk:high`.

Binding inputs: D-57, D-61, D-105, D-108 (the categories Citations and "URLs, DOIs and
e-mail addresses"), D-113, D-128, Q4, Q15, D-150 (characters and hyphens run last), issue #66.

## 0. What the corpus shows (survey and prototype on the 7 papers, layout output of main)

Counted outside reference lists, furniture, tables and formulas.

- **Numeric citations** (Arsiwalla, Liu): about 140 brackets of whole numbers, lists and
  ranges, some inside Liu's unheaded reference list ("[45]", "[2–6, 16, 17]", "[52,63,68,74]", "[11, 12, 20, 34, 40–43]"). About 20 are
  part of the sentence: "discussed in [26, 61, 86, 93, 128].", "in Ref. [1] for", "the
  blueprint of Refs. [53, 58].", "( [53] discusses the ...", "8See [47] for discussions",
  "(see also [15] for a recent perspective)". Three are only lead words plus citations:
  "(see also [48, 135])", "(see [113,131])", "(see also [23, 24])".
  Brackets that look similar but are maths or data: "Tr[⟨ρˆ⟩ ˆj]", "[n (−1) E ]",
  "p: R → [0, 1]", "[3e-4, 1e-4, ...]" (a table), and the audit's "95% CI [1.2, 3.4]".
- **Author-year in brackets** (Chi, Hardt, Nowak, Waskom, Biggs): 68 brackets with a year.
  A first prototype of the grammar in 1.4 reads 62 as citations only. Of the other 6, one is
  truly mixed ("(RNNGs; Dyer et al., 2016; Dyer, 2017; Kim et al., 2019)"), one is not a
  citation ("(Dated: April 5, 2024)"), and 4 are citations the prototype missed for reasons
  1.4 fixes: two nested ("(e.g., BERT (Devlin et al., 2019))", "(see e.g. Althoen and
  McLaughlin (1987))", handled by working innermost first and by "see e.g."), Hardt's
  "(Khullar (2020), Zhang et al. (2019); …; Bos and Spe-\nnader (2011))" (parts joined by a
  comma, a name split at a line end), and a Biggs list with "Rodrı́guez" (a combining mark).
  Variants seen: "et al.", "and", "&", several years "2016a,b", no comma
  ("Corazza et al. 1994"), locators ", Chapter 9", ", inter alia".
- **Narrative citations** ("Name (2020)"): 45, all in Chi, Hardt and Nowak: "Devlin et al.
  (2019)", "Jelinek and Lafferty’s (1991)", "Baker’s (1979)", "Kocijan et al.\n(2022)[p. 8]",
  and a bracket used as the subject: "(Dasigi et al., 2019)[p. 1] note that". Hardt also
  nests them: "Quoref (Dasigi et al. (2019); Zhang and Zhao\n(2022)) is ...".
- **URLs**: 7 outside reference lists, about 50 inside. **Line breaks inside URLs are common**:
  "https://github.\ncom/citp/...", "https://github.com/DanHardtDK/\nellipsisGPT3.",
  "https:\n//doi.org/...", "https://doi.org/10.1002/acm2.\n13207",
  "http://www.spectronic.se/files/Whitepaper_\nTFE_202106.pdf". The sentence ends right after
  most of them: "released at https://github.com/JFChi/PLUE.".
  A footnote that is only a URL: Chi note 5 "5 https://github.com/huggingface/transformers".
- **DOIs**: almost all inside reference lists as `https://doi.org/` URLs; one bare DOI
  "10.1038/s41565-023-01470-8." (Liu, whose reference list has no heading, issue #92).
- **E-mail addresses**: 5 addresses or groups, in author blocks and one footnote, with brace
  groups:
  "jianfengchi@meta.com,{wasiahmad,yuant,kwchang}@ucla.edu", "{franz.nowak,
  ryan.cotterell}@inf.ethz.ch", and a footnote "∗x.d.arsiwalla@gmail.com".

## 1. Design

Two inline steps, one per category (D-108), in a new module each, English only in v1.0:

| Step id | Module | Category | Stage | Languages |
|---|---|---|---|---|
| `links` | `textprep/links.py` | URLs, DOIs and e-mail addresses | inline | `en` |
| `citations` | `textprep/citations.py` | Citations | inline | `en` |

Registry: right after the block steps, `links` then `citations`, before `footnotes` (#64),
the number and abbreviation steps (#67, #68) and the characters steps (#65, D-150), as the
registry docstring already plans. Links go first because a URL can contain things that look
like citations or numbers, and a URL removed whole must not be cut up by a later rule.

Both steps skip furniture, formula and table blocks (furniture and placeholders are whole
block edits that win anyway, D-128) and work on every other kind: paragraphs, headings,
captions, list items, footnotes. Nothing proposes `ask`. Every edit's reason names the
citation or link **as printed** (runs of white space as one space, line breaks inside a URL
dropped), so the report can be searched for it (the design principle "everything
referenceable"); the report already holds the original span as printed (D-134).

### 1.1 `links`: what counts as a link

- **URLs**: `http://`, `https://`, `ftp://` and `www.` addresses, with `<...>` around them;
  bare `host.tld/path` only with a path and a top-level domain from a short list (com, org,
  net, edu, gov, io, ai, de, uk, eu, ...), so "e.g./i.e." or "and/or" never match.
- **DOIs**: `doi:10.x/...`, `DOI: 10.x/...`, `doi.org/...` and a bare `10.NNNN/...`.
- **arXiv identifiers**: `arXiv:2311.03973` (with an optional `v2`) and the old form
  `arXiv:hep-th/9901001`. Not named in the issue, but a link in all but name, spelled digit by
  digit when read (decision L3).
- **E-mail addresses**: `name@host.tld`, `mailto:` addresses, and brace groups
  (`{a,b,c}@host.tld`, also with spaces inside the braces). Neighbouring links joined by
  ",", "and", "or" or "/" form one **link run**, removed as one edit.
- **Line breaks inside a URL**: a URL that reaches a line break continues on the next line
  when it ends in `/ - _ ~ = & ? # %` or in `:` after the scheme ("https:\n//doi.org"), or when
  it ends in "." and the next line's first word starts with a lower-case letter or a digit and
  holds a "/" or only digits ("github.\ncom/citp", "acm2.\n13207"). Otherwise the URL ends at the
  line break.
- **End of a URL**: closing punctuation at its end (`. , ; : ! ? ' "` and an unbalanced `)`,
  `]`) belongs to the sentence, not to the URL ("…/PLUE." keeps its full stop).

### 1.2 `links`: sentence repair (TP-07)

The first rule that applies decides what goes with the link run. In every case the white
space before the removed text goes too (after it, at the start of a block), so no
"available ." is left.

1. **A bracket holding only the run** (and optionally "see", "see also", "cf.", "e.g.",
   "at", "from", "available at", "online:", "URL:"): the whole bracket goes.
   "(see https://x.org)" → nothing.
2. **A label before it** ("Contact:", "E-mail:", "Email:", "Correspondence:", "URL:",
   "Website:", "Homepage:", "Code:", "Data:", "Available at:", "Available online:", "DOI:",
   "Project page:", ...): the label goes with it; if the label starts the sentence and the run
   ends it, the whole sentence goes, full stop included. "Contact: j.doe@uni-example.edu." →
   nothing.
3. **Another colon before it**: the colon goes with it. "University of Oxford: https://…" →
   "University of Oxford".
4. **A preposition or verb before it** (at, from, on, via, in, under, to, see, visit, using,
   through, cf.): the word goes with it. "The code and models are released at https://…." →
   "The code and models are released."; "Calculated using https://…, based on" →
   "Calculated, based on"; "the tool at https://… to compute" → "the tool to compute".
5. **Otherwise** only the run goes.

**A block that holds nothing but links** (and punctuation), or a footnote that holds nothing
but its label and links: one edit removes its whole text, so the footnote step of #64 does
not read a lone "Footnote 5." (its intro edit overlaps and is set aside, with this edit as the
winner in the report). Chi note 5 and Nowak's "https://github.com/rycolab/" read nothing.

Known leftovers, accepted for v1.0: "see https://x.org for details" reads "for details", and a
link inside a bracket that also holds a citation is removed by `links` first, so the
citation step's whole-bracket edit is set aside ("(Smith, 2020; https://x.org)" reads
"(Smith, 2020)"). Neither occurs in the corpus.

### 1.3 `citations`: numeric citations (TP-03, TP-04)

**What counts**: a square bracket holding only whole numbers from 1 to 9999 (an optional
letter: "12a"), separated by "," or ";", and ranges with "-", "–" or "—", white space and line
breaks allowed anywhere. **Not a citation**: a bracket glued to a letter, digit or closing
bracket before it ("Tr[...]", "x[1]"); after a maths or statistics sign or word (`= ∈ → < >
≤ ≥ ×`, "CI", "interval", "range"); holding 0, a decimal point or a letter other than the
one suffix. Parentheses are never numeric citations ("(1)" is an equation or list number).

**What is read**, by the first rule that applies:

1. **Only lead words and citations in a bracket** ("(see also [48, 135])", "(see [113,131])",
   "(e.g., [3])", "(cf. [4, 5])"): the whole bracket goes.
2. **Part of the sentence**: the word before is a preposition or link word (in, by, of, from,
   to, see, also, and, or, with, following, than, like, on, under, via, cf., e.g., i.e.), or
   "Ref.", "Refs.", "Reference", "References" (replaced along with the bracket), or the
   citation starts a sentence, a block or a bracket ("( [53] discusses"). Then it is
   **read as "reference 12"**, "references 3 and 5", "references 2 to 6", "references 8 to 10,
   16, 44 and 115", one `replace` edit: "discussed in [26, 61, 86, 93, 128]." → "discussed in
   references 26, 61, 86, 93 and 128."; "( [53] discusses" → "(reference 53 discusses"; "Refs.
   [53, 58]" → "references 53 and 58". Digits stay for misaki (#67).
3. **Otherwise it is an aside and goes**, with the white space before it: "However,
   findings remain inconsistent [2–6, 16, 17]." → "However, findings remain inconsistent."

### 1.4 `citations`: author-year citations (TP-03, TP-04, K2)

**A citation part** is: optional lead words (see, see also, e.g., cf., i.e., for example, but
see, for a review see), **authors**, then one or more **years** (1500 to 2099 with optional
letters "2016a,b", or "in press", "n.d.", "forthcoming"), either after a comma or a space or in
their own brackets ("Dasigi et al. (2019)"), then optional **locators** (", p. 8",
", pp. 3–5", ", Chapter 9", ", Sec. 2", ", §3", ", inter alia"). **Authors** are one or more
names joined by ",", "and" or "&", each optionally followed by "et al."; a name is a word
starting with a capital letter (diacritics, combining marks, hyphens, apostrophes and the
particles van, von, de, der, da, del, di, la, le, du, ten, ter allowed; "Mc" and "O'"
prefixes), or an all-capital word of 2 to 6 letters before a comma ("WHO, 2020"); month names
are never names ("(Aug 2013)"), nor mixed-case words like "CoNLL"; a name split at a line end
("Spe-\nnader") counts as one word.

Brackets are worked innermost first, so a nested citation is handled before its outer
bracket. A bracket's parts are split at ";" (and at "," between parts that each end in a
bracketed year, as in Hardt's "(Khullar (2020), Zhang et al. (2019); …)"):

1. **Every part a citation**: the bracket goes, with the white space before it.
   "(Smith et al., 2019; Jones & Lee, 2020)." → "."; nested: "Quoref (Dasigi et al. (2019);
   Zhang and Zhao (2022)) is" → "Quoref is".
2. **Some parts citations**: those parts go with their separators, the rest stays.
   "(RNNGs; Dyer et al., 2016; Dyer, 2017; Kim et al., 2019)" → "(RNNGs)".
3. **Used as the subject** (the bracket starts a sentence or block and a lower-case word
   follows): **the names stay, the rest goes** (TP-04): two `remove` edits around the kept
   names. "(Dasigi et al., 2019)[p. 1] note that" → "Dasigi et al. note that". Several parts
   keep their names joined by "and" (a `replace` of the separator).
4. **Narrative citation**: a bracket holding only years and locators, right after a name
   (possessive "’s" allowed) or "et al.": **only the bracket goes, the names stay** (TP-04,
   K2). "as shown by Smith (2019)" → "as shown by Smith"; "Kocijan et al.\n(2022)[p. 8],
   “Solving" → "Kocijan et al., “Solving"; "Baker’s (1979) algorithm" → "Baker’s algorithm".
5. **A page locator bracket glued to a citation** ("[p. 8]", "(p. 12)", "[pp. 3–5]") goes
   with it; one standing alone right after a closing quotation mark goes on its own.

"et al." stays as printed and is #68's to read (its acceptance list names it). With the
Citations switch off, every citation reads as printed.

### 1.5 Wording

The spoken words of the steps ("reference", "references", "and", "to") and the English word
lists (prepositions, labels, lead words, particles, months, top-level domains) are module
constants keyed by language (`{"en": ...}`), so German adds a row later (D-50). If #64's
`textprep/wording.py` has merged when I code, the spoken words go into its table instead.

## 2. Issue #91 (the cutter splits inside "(2022)[p. 8]")

**Recommendation: #66 stays clear of the cutter; #91 gets its own small PR from this thread,
right after the #66 PR is open.** With the Citations step on, the hardt sentence no longer
reaches the cutter with "(2022)[p. 8]" in it, so #66 fixes the corpus symptom; the cutter bug
remains for any other glued abbreviation ("[Fig. 3]" after a bracket, "(e.g. Smith"), and
with Citations switched off. One issue per PR (CLAUDE.md), and the two PRs touch the same
hardt snapshot, so serial is simpler than one mixed PR. Alternative: fold #91 into this PR
(one review, but two issues and two feature IDs in one critical PR).

## 3. Decisions for the coordinator (D-numbers from you)

- **L1: two inline steps `links` and `citations`, English only in v1.0, placed right after
  the block steps, links first** (1, 1.1). Alternatives not chosen: one step for both
  (one switch would turn off two categories, against D-108); any-language links step (its
  repair words are English; a German document would get English repairs). Follow-up issue:
  German rows (v1.1, with #79).
- **L2: links are removed with sentence repair by the five rules of 1.2, and a block or
  footnote holding only links reads nothing.** Alternatives not chosen: read the host name
  ("released at github dot com"; the issue asks for removal, and "doi dot org" tells a
  listener nothing); a short notice "A link is skipped." (fills the audio with notices where
  most papers have a dozen links).
- **L3: arXiv identifiers count as links.** Alternative: leave them (they are read digit by
  digit, nearly always in reference lists, which #64 removes).
- **L4: line-broken URLs are joined by the rule in 1.1.** Measured with a
  prototype on the corpus: all 30 URLs broken at a line end (all but 3 in reference lists) are joined correctly, and the one URL
  that ends at a line end before more text ("https://mlco2.github.io/impact," then "based on") is
  not run on into the next line.
- **C1: a numeric citation is a square bracket of whole numbers, lists and ranges only, with
  the exclusions of 1.3.** Alternative: also superscript numbers (Nature style); they are
  indistinguishable from footnote marks without the reference list, so they wait for a
  follow-up issue.
- **C2: a numeric citation that is part of the sentence is read as "reference 12",
  "references 3 and 5", "references 2 to 6"; one that is an aside is removed; a bracket of
  only lead words and citations is removed whole** (1.3). Alternatives not chosen: removing
  the preposition with it (changes the meaning: "similar to [12]." → "similar."); always
  removing (leaves "as shown by ." and "discussed in ."); reading the bare number ("as shown
  by 12").
- **C3: author-year citations by the grammar and five rules of 1.4: removed in brackets,
  names kept where the citation is part of the sentence (narrative or subject), mixed
  brackets keep their other parts, page locators go with their citation.**
  Alternative not chosen: the old app's spoken note ("Sources: Smith and colleagues, twenty
  nineteen"), which the audit marked right but which makes every paragraph longer; and
  K2's Paper2Audio style is exactly rule 4.
- **C4: #91 stays a separate PR** (section 2).
- **C5: the reason of every edit names the citation or link as printed.**

Each decision gets a row in the KB decision log (a KB PR from this thread, reviewed in its
own thread, D-78).

## 4. Tests (test-first)

1. **Regression cases first** (`tests/regression/english.toml`), the before/after diff in the
   PR:
   - `expected` changes for the audit cases:
     - `author-year-citations` → "Several studies have examined the effects of
       environmental noise on young children."
     - `numeric-citations` → "However, findings remain inconsistent."
     - `url-and-e-mail` → "Data are available." (utterances: one).
   - New cases (`audit = 0`, `issue = 66`), each one pattern:
     - numeric: single, list, range with "-" and "–", semicolons, line break inside;
       "discussed in [26, 61]." (reference reading); "Refs. [53, 58]"; "Ref. [1]"; subject
       "( [53] discusses"; "(see also [48, 135])" removed; "(see also [15] for a recent
       perspective)" kept and read;
     - not numeric citations: "x ∈ [0, 1]", "Tr[ρ]", "95% CI [1, 3]", "the interval [2, 5]";
     - author-year: "(Wickham, 2016)."; "(Smith et al. 2019a, 2019b; Jones, in press)";
       "(Eisenstein, 2019, Chapter 10)"; "(e.g., Smith, 2019; see also Lee, 2020)";
       "(WHO, 2020)"; mixed "(RNNGs; Dyer et al., 2016)"; nested "(e.g., BERT (Devlin et al.,
       2019))"; Hardt's "Quoref (Dasigi et al. (2019); Zhang and Zhao\n(2022)) is";
     - narrative and K2: "as shown by Smith (2019)"; "Smith et al. (2020) show";
       "Baker’s (1979) algorithm"; "Kocijan et al.\n(2022)[p. 8], “Solving"; subject
       "(Dasigi et al., 2019)[p. 1] note that";
     - not author-year: "(Aug 2013)", "(CoNLL 2017)", "(1931 - 1958)",
       "(Dated: April 5, 2024)", "the 2020 census (2020)";
     - links: URL at sentence end; URL broken after "." and after "/"; "https:\n//doi.org/…";
       URL in brackets; "Code: https://…"; "Calculated using https://…, based on";
       mid-sentence "the tool at https://… to compute"; trailing ")" and "." outside the URL;
       e-mail brace groups (both corpus forms); "mailto:"; "doi:10.1000/xyz123";
       "DOI: 10.1038/…"; bare DOI; arXiv id; a footnote that is only a URL (with its label).
2. **Unit tests** per rule, with the exact spans, kinds, replacements and reasons; the
   switches (each category off reads its text as printed); set-aside interplay with #64's
   footnote intro and #65's hyphen step on "privacy-policy-\nhistorical" (when they are on
   main).
3. **Conformance**: both steps pass `check_text_step(step, allow_ask=False)` automatically
   through `test_textprep_conformance.py` (no crash, valid spans, deterministic, no network,
   idempotent on their own output). `SAMPLE_DOCUMENTS` gets a citation and a URL so every
   conformance check exercises them.
4. **Hypothesis properties** (ci and nightly profiles), with strategies that build sentences
   from words, citations of every form above and links (with line breaks, trailing
   punctuation and repair words), so most examples exercise the rules (I count it with a
   probe, the #83 lesson): no crash on any text; `check_text_step` on generated documents;
   no generated link or numeric citation is left in the spoken text; every removed
   character lies inside a citation or link or is one of the listed repair words, white space
   or punctuation next to it (no other word is ever lost); no spoken text gains " .", " ,",
   "()", "( )" or a preposition right before a full stop.
5. **Corpus** (fast): a new syrupy snapshot `test_textprep_citations_links_corpus.ambr`
   listing, per paper, every edit of the two steps: block, printed text with 20 characters on
   each side, what is read instead, and the rule. The reviewer checks it against the PDFs.
   Plus assertions: outside reference lists no URL, e-mail, DOI or numeric citation remains in
   the spoken text; every narrative citation keeps its names; no repair leaves "at.",
   "Contact:.", "()" or a space before punctuation.
6. **Snapshot changes**: the per-paper outcome summary of `test_textprep_furniture.py` gains
   "citations" and "links" rows; the script-job snapshots of #70 change where citations and
   links are read; the PR explains both diffs.

## 5. Size, order of work, follow-ups

About 450 lines of source in two modules and 700 lines of tests and data. One PR, branch
`textprep/issue66-citations-links`, `Closes #66`, feature IDs TP-03, TP-04, TP-07. #64 (PR
#94) and #65 (PR #98) touch `registry.py`, `english.toml` and the #70 snapshots; I keep my
registry change to two lines and merge main in as they land. Then the KB PR with L1 to L4 and
C1 to C5. Then, if C4 is approved, the #91 PR.

Follow-up issues to file: superscript numeric citations (C1); German word rows for both steps
(L1); a link inside a citation bracket (1.2 leftovers).
