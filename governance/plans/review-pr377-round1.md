# Review PR #377, round 1 (textprep batch 2 PR 1: keys #254, unheaded reference list #92)

Head reviewed: a578dc0 (base main 342a8f5). Plan: plans/textprep-v12-second-batch-plan.md PR 1 (D-646). Critical.

**Verdict: not approvable yet. One blocker (B1), two should-fix items (S1, S2), one nit (N1).**

## What I checked

- **Plan.** The change follows the plan. The PR body closes #254 and #92, and the commit message has no closing keywords.
- **Corpus.** I ran `run_script_job` on all 13 corpus documents on main 342a8f5 and on the PR. 11 documents are byte-identical. The two that change:
  - **maass:** 10 body keys change. 3 needed keys are now read as "Quelle MH17", and 7 asides are removed. Nothing else in the script changes.
  - **Liu:** only lines 223 to the end of the script are removed: blocks 53 to 133, which are entries [1]–[81], the two short continuation blocks 90 and 129, and the note [59]. "Acknowledgments." and its text are still read, and nothing before the list changes. The citations, characters, numbers and links edits that the furniture snapshot moves to set-aside all lie inside the removed blocks.
  - **The other corpus papers:** their headed lists are untouched, because the new rule runs only without a reference-list section.
- **Faithful text (D-57).** A key that is needed is read as printed ("reference MH17"). The problem is with brackets that only look like keys (B1).
- **Second run.** About 40 key shapes and 13 built documents ran through the whole chain twice. Every reading is the same on both runs.
- **Fast suite** on a578dc0 (`HYPOTHESIS_PROFILE=ci`, PR source): 5555 passed, 1 skipped. Mutants, nightly seeds and `ci:full` are left for the approving round.

## Fix list

### Blockers

**B1. Any bracket shaped like a key is treated as a citation, in every document, so printed words that are not citations go or are read as "reference".** The shape `[A-Z][A-Za-z]{1,3}\+?\d{2}[a-z]?` matches common names of things, and a short list of look-alikes (`PM10`, `Win10`, …) cannot cover them. Each of these reads the same on both runs, and main reads each one as printed:

| printed (en) | PR |
|---|---|
| `The [Mn12] clusters are magnetic.` | `The clusters are magnetic.` |
| `We use [Al13] clusters here.` | `We use clusters here.` |
| `The [Fe23] complex binds.` | `The complex binds.` |
| `The [EU27] countries agree.` | `The countries agree.` |
| `The [UK21] study shows it.` | `The study shows it.` |
| `The [SARS19] virus spreads.` | `The virus spreads.` |
| `Press [Ctrl12] now.` | `Press now.` |
| `Cells [AB12] to [AB20] hold 3.` | `Cells to reference AB20 hold 3.` |
| `Values in [Ab12, Cd34] hold.` | `Values in references Ab12 and Cd34 hold.` |

Metal clusters in brackets ("[Au25]", "[Mn12]") are ordinary chemistry notation. A document whose sources are numbered has no keys at all, yet these brackets are removed there too.

Fix: use the document's own evidence. A key-shaped bracket is a citation only if every key in it is printed as an entry label at the start of a block somewhere in the document. Maass's list prints them that way: "[EN16] Englehardt, S.; …", "[Fa14] Fahl, …". Otherwise the bracket stays as printed. The step's `find` already sees the whole document.

The guard must hold on a second run as well. Run 1 removes the list, so the rebuilt document has no key entries left. By then, though, run 1 has already read or removed every key that its list printed, so nothing changes. The look-alike list can stay as an extra guard.

Tests:
- The nine rows above, in a document whose list is numbered, must read as printed. They must fail on a578dc0.
- The same rows in a document whose list prints the key (for example "[Mn12] A. Author …" at a block start) must read as citations.
- Both groups in en and de.
- maass must still change only as it does now.

### Should-fix

**S1. A short block with a year after the last entry is removed, even when it is body text.** `_Run.list()` returns `last_lines` after the last entry. So a document that ends with its list and then "We thank all in 2020 for help." loses that sentence. The same goes for "Received 3 May 2020.".

The plan says a block without "[N]" is a continuation "only if … an entry follows it". Both of Liu's continuation blocks (90 "Europhysics Letters 135, 37001 (2021)." and 129 "(2020).") are followed by an entry, and Liu's last block is the entry [81].

Fix: `list()` returns only the blocks that end at an entry, not trailing `last_lines`. Add a row in which a short dated sentence after the list at the document's end is read. It must fail on a578dc0. Liu must stay as it is now.

**S2. A list right after a heading that does not name a reference list counts as "printed without a heading".** Six entries "[1] …" with years after a heading "Notes" (likewise "Endnotes", "Anmerkungen", "Appendix B") are removed. Main reads them. That list has a heading. The second rule is meant only for lists printed without one, and the first rule leaves out only reference titles.

Fix: a run whose first entry follows a heading block, with only passed kinds between, is not an unheaded list. Rows:
- "Notes" plus six entries is read.
- "Endnotes" plus six entries is read.
- The Liu shape is unchanged.
- A list at the document's end after body text in a document with headings ("Results", text, then entries) is still removed. It is removed now and must stay removed.

### Nits

**N1. A numbered body list whose items each hold a year is removed when it ends the document.** "[1] In 2011 we ran step 1 of the protocol …" through "[6] …" after a "Results" heading reads nothing. This is rare, but it is body text. A stronger sign of an entry would help, for example the year in parentheses "(2011)" or after a comma at the entry's end, or an initial-and-surname pattern "A. Author". If you take this, add the row. Otherwise say in the PR why the year test is enough.

### Deferred

None. "The sets [Ab12] and [Cd34] meet." reads "The sets and reference Cd34 meet.", which inherits the numeric rule's behaviour for a pair ("[1] and [3]"). That is #257, PR 3 of this plan. With B1 fixed, this row reads as printed anyway.

## Next

Round 2 re-checks B1, S1, S2 and N1. If it is expected to approve, it also runs the 13 samples, mutants, nightly seeds, the token fuzz and `ci:full`.
