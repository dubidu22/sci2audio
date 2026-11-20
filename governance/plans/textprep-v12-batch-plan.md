# Plan: textprep v1.2 batch (#304, #305, #306, #308, #309, #310, #315, #316, #318)

Thread: "Fix second-run reading differences" (textprep lane). Base: main aec6e6a.
Status: **waiting for the coordinator's approval** (all three PRs are critical: each adds regression cases).

## What I measured on main (cc7cae2, same textprep code as aec6e6a)

Every row of every issue reproduces (probe: whole chain twice, `rebuilt_from_script`; footnote
shapes in regression format with a real `sup` run and a note block). Two findings beyond the
issues:

- `It is −1/2 here.` reads `minus 1/2`, then `minus 1 half` on a second run. #304's fuzz shape
  `3–33–3 −3/3` is only the odd form of this common one.
- Running all 251 English and German regression cases twice: 6 differ. 4 are a rebuild artifact
  (a figure/table notice block comes back as a paragraph). 2 are real and have no issue yet:
  en `Let f(x) = 4x.` reads `equals 4x`, then `equals 4 times`; de `1 bzw. 2 V` reads `2 V`,
  then `2 Volt`. These get new issues (see D7).

A prototype of the citations fix (PR A, below; not pushed) reads all #306, #308 and #309 rows
the same on both runs, also fixes #278 row 1 and both #291 rows, keeps all 76 snapshots
byte-identical (corpus unchanged), and passes the whole fast suite except three unit tests that
pin today's stub readings (listed under PR A).

## PR A: citations read the same on a second run after a removal (#305, #306, #308, #309)

Files: `textprep/citations.py`, `testing/regression.py` (second-run check), tests.

1. **Looks until nothing changes** (#306, #308, #309). `_Rules.block` already decides the
   brackets a second time on the text without removed identifiers (#285). Generalise it: each
   look decides the brackets on the text without every removal so far: the citations step's own
   removals of the earlier looks and the links step's removals (`links`, which `find` already
   passes in). Stop when a look adds no edit; at most 3 looks. Merge: a later look's edits win;
   an earlier edit inside one goes with it; an earlier edit that crosses one stays and the later
   edit is dropped (no overlap, reading as today). A later edit that spans a link's removal is
   split around it, so the links step keeps its own edit (otherwise the runner sets the
   citation's removal aside). Fixes `(Smith, 2019, https://example.org)`,
   `(527794, doi:…)`, `Lee (Smith, 2019) (2019)`, `Text [12] (2019)`,
   `(see (Smith, 2019) (2019))`, `(e.g., (Smith, 2019), Lee, 2020)`,
   `Smith ((Smith, 2019) 2020)` and the German rows.
2. **Chains in one look.** A year bracket right after a bracket that this look removes is judged
   on the names before that bracket, and a bracket's lead-only test reads its inside with the
   inner brackets' edits made. Without this, `Lee (2019a) (2019b) (2019c) (2019d)` needs one look
   per bracket (prototype: the 4-chain still breaks at 3 looks).
3. **Dangling separators** (#305). A removal inside a bracket that stays takes along a "," ";"
   or join word ("and", "und", "&") that it would leave between itself and the bracket's edge
   (after any lead words): `((527794); 2019)` → `(2019)`, `(see (527794) and Lee, 2019)` →
   `(see Lee, 2019)`, `(527794, (Smith, 2019))` → `(527794)`, `(results and (Smith, 2019))` →
   `(results)`. The next look then judges what is left, as a second run would: the first goes
   after a name ("Text" is a name in English), the second and third go whole.
4. **No join into a number** (#308 last row). A citation bracket stays as printed when its
   removal would glue a "." "," or digit before it to a digit after it
   (`. .(Müller, 2019)12.345`), as `_NUMBER_GLUED_AFTER` already keeps `[1; 3],1`.
5. **Second-run check for every regression case** (`testing/regression.py` + both test files):
   each case's block texts must read the same on a second run over `rebuilt_from_script`
   (compared per block, so a moved note's place does not count). Notice cases are exempt (the
   rebuild loses the block kind), and the two new issues of D7 are listed as known exceptions
   with their issue numbers.

Tests first (fail on main): English and German regression cases for every row of #305, #306,
#308, #309 (and #278, #291 if D1); a Hypothesis property with sibling and nested brackets
(citation, numeric, year, identifier, link; with and without a name before) run whole-chain
twice; `test_a_nest_reads_balanced_and_the_same_on_a_second_run` grows "e.g., " leads, a
" (2019)" tail and a name before the nest (#306's criterion).

Pinned unit tests whose reading changes (they pin today's stub, the new one is what a second
run would read anyway): `(see also (Smith, 2019); Jones, 2020).` → `It holds.` (was
`(see also)`); de `((Müller, 2019)) zeigt das.` → `zeigt das.` (was `() zeigt das.`);
`((Smith, 2019)) is cited.` → `is cited.` (was `() is cited.`; its docstring names #278).

Timing: each look is one pass of today's step; a block without removals takes one look. I will
measure every citations case of `test_linear_time.py` as a ratio against its limit on main and
the branch (lesson of #313), and a block of many removals (the 3-look worst case).

## PR B: numbers read the same on a second run (#304, #310, #318)

Files: `textprep/numbers.py`, `textprep/units.py`, `textprep/numbers_de.py`, tests.

1. **#304 part 1, English fraction after a minus sign.** `_FRACTION`'s look-behind refuses
   U+2212, but N1 reads that sign "minus ", so a second run sees `minus 1/2` and reads the
   fraction. Allow U+2212 before a fraction where `_MINUS` reads it (not glued after a letter,
   digit, "." or ","): `−1/2` → `minus 1 half`, `−3/3` → `minus 3 out of 3`. `5−1/2` and `-1/2`
   stay as printed, as today. (German has no minus reading; `−1/2` stays there on both runs.)
2. **#304 part 2, tilde before a line-end hyphen.** `_TILDE` in `units.py` looks for a sign and a
   digit after "~"; `~-\n0` has the line break between. The hyphens step keeps a hyphen before a
   digit, so the second run sees `~-0` and reads "about". Allow `-\n` as the sign:
   `0:~-\n0` → `0: about -0` on both runs.
3. **#310, German yearless date before a fraction.** `_NUMERIC_DATE` leaves `3.4.` as printed
   before a space and a digit unless a full date follows (D-567). A fraction "1/d" that N-de-7
   reads as "ein halb", "ein Drittel" … starts with a letter on the second run, so the date is
   read then. Read the date on the first run when the number after it is such a fraction (only
   n = 1: `2/3` reads "2 Drittel", whose digit keeps the date as printed on both runs).
   `Am 3.4. 1/2 Tag.` → `Am dritten April ein halb Tag.`
4. **#318, German hyphen or dash ranges with a yearless end.** Read
   `3.4.-5.4.2019` and `3.4.–5.4.2019` as `dritten April bis fünften April 2019`, and
   `3.4.2019-5.4.` and `3.4.2019–5.4.` as `dritten April 2019 bis fünften April` (the en-dash
   form now gives `… 2019 bis 5.4.`). The second date takes "-en" as after a range dash. A
   yearless second date is read only as part of a range whose first date is read. `3.–5.4.2019`
   (day only) stays as printed, as D-562 decided.

Tests first: English regression cases for `It is −1/2 here.`, `3–33–3 −3/3`, `0:~-\n0`; German
cases for the #310 row (and `1/3`, `2/3` as the keep) and the #318 rows (D4); second-run unit
tests in `test_textprep_numbers*.py`; the nightly seeds 2026 and 7 from #304 rerun.

## PR C: footnote marks and German closing quotes (#315, #316)

Files: `textprep/utterances.py`, `textprep/notation.py`, `textprep/footnotes.py`, the steps
that call `through_unread` / `edits_through_unread` (abbreviations, numbers, units, statistics),
tests.

1. **#315.** In German, a full stop, "!" or "?" followed by "“" (closes „…“), "‘" (closes ‚…‘) or
   "»" (closes Swiss «…») ends a sentence, as `.”` does in English. German only (D5). The
   footnote-places step uses the same rule, so a note marked after `„ja.“¹` moves after that
   sentence.
2. **#316.** `through_unread` already lets the number, statistics, units and abbreviation rules
   read the text without characters a later step drops. It gets the found footnote marks of the
   block as more unread ranges: `FootnoteStep.marked()` gives them; each of these steps computes
   them once per document. So `bzw.¹` reads "beziehungsweise", `z. B.¹` "zum Beispiel", `e.g.¹`
   "for example", `Abschnitt 2.¹ Dann` no longer "2 Punkt". An edit never covers a mark (the
   footnotes step owns that span). Plain numbers glued to a mark (`3.5¹`) stay D-143's.

Tests first: German regression cases with a footnote after `„ja.“`, `bzw.`, `z. B.`,
`Abschnitt 2.` and English ones after `e.g.` and `Section 2.`; each with a second-run check of
the block texts. German corpus: I expect no change (measured before the PR; any change is
explained in it).

## Critical and API

- All three PRs add regression cases (golden by CLAUDE.md), so all three are critical
  (`risk:high`) and each gets its own review thread.
- No core dataclass, layer contract or KB change. `TEXT_STEP_API` stays 1: `through_unread`
  and the citation rules are internal.
- Corpus: PR A's prototype keeps all snapshots byte-identical. PR B and C are measured over all
  13 corpus documents before each PR opens; any change is explained in the PR.

## Order

A first (largest, and it adds the second-run check for all regression cases), then B, then C.
They touch different files except the two regression TOMLs, where each PR adds its cases in its
own section; the later PRs merge main in.

## Decisions (with my recommendation)

- **D1. Fold #278 and #291 into PR A?** Recommend yes for #291 (both rows are fixed by the same
  looks) and #278 row 1 (`Text ((Smith, 2019); Jones, 2020) here.` → `Text here.`). #278's
  subject row (`((Smith, 2019); Jones, 2020) is cited.` should keep "Smith and Jones") reads
  `is cited.` with the looks, not the names; I would leave #278 open for that row only.
- **D2. At most 3 looks**, with chains resolved in one look (PR A item 2). Recommend 3: it bounds
  the cost at 3× on blocks with removals, and the nest and sibling shapes need at most 2.
- **D3. `. .(Müller, 2019)12.345`**: keep the bracket (recommend) rather than replace it with a
  space. A space would add a character the page does not print.
- **D4. #318 with both ends yearless** (`3.4.-5.4.`, `3.4.–5.4.`): read as a range too, when the
  first date is read (it has a word such as "vom" before it). Recommend yes; same rule, no new
  risk.
- **D5. #315 German only.** Recommend German only, so English utterances stay byte-identical;
  English already ends at `.”`.
- **D6. #316 cost**: each of four steps finds the marks again (linear). Recommend that over a
  shared cache, which would need the step interface to change.
- **D7. New issues** for the two second-run breaks found with the regression check
  (`f(x) = 4x`, de `1 bzw. 2 V`), v1.2, filed by this thread once the plan is approved; PR A
  lists them as known exceptions.
