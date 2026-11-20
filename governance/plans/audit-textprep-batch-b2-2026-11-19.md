# Light audit: textprep batch B2 (#572 + #585), 19 Nov 2026

Auditor: B2 review thread (Opus high). Scope: merged diff of #572 (0a72357, #445 #449) and #585
(ad6b94f, #448) read together on main ad6b94f; cross-PR consistency, contract and core touches,
regression readings, CHANGELOG (D-768). **Result: clean, 0 defects.**

## Contract and core

- B2 changes `src/sci2audio/textprep/` only: `footnotes.py`, `furniture.py`, `notation.py`,
  `numbers.py`, `units.py`. No `sci2audio.core`, text-step interface, `lint-imports` layer or
  `sci2audio.testing` change. (`core/content.py` moved on main in the same window, by #562 and
  #575 of B1, not by B2.)
- 18 Nov lesson (grep every `replace(<dataclass>`): no added or removed line in B2's textprep diff
  contains `replace(`, `dataclasses` or a `sci2audio.core` import; the new `raised_numbers` only
  reads content items through `_lines`, as `_raised_marks` already does.

## Cross-PR

- **`removed_span` (#572) x `AffiliationMarkStep` (#585):** #572 widened every affiliation-mark
  removal between spaces by the white space before; #585 changed which marks are removed, not
  their spans. Both go through `AffiliationMarkStep.marks`, which `unread_marks` also calls, so the
  units, abbreviations, numbers and statistics steps read around exactly the marks the step
  removes (#572's `through_unread` cut). Probed on main: "Jane Roe ¹ and Ann Lee ²" with a
  hidden run in the affiliation line reads "Jane Roe and Ann Lee", "Example Observatory City",
  stable.
- **`raised_numbers` (#572) x affiliation shape (#585):** disjoint by construction. A magnitude
  edit needs one letter (K, M, B, k) followed by no letter; `_before_affiliation` needs a
  capitalised word of two letters or more. Probed: "⁴⁰K-⁴⁰Ar dating of ¹¹B-rich rocks" title, an
  affiliation "Kyoto University and ⁴⁰K Lab", German "⁴⁰K-Datierung": all stable on both runs,
  the affiliation marks go, "⁴⁰K"/"¹¹B" kept as superscripts in English, German as printed.
- **Two `_after_name` functions:** `abbreviations._after_name(text, start)` and
  `footnotes._after_name(text, start, end)` are private to their modules with different
  signatures; no import crosses. Not a defect.
- Probe files from both reviews (`/home/user/probe/s1, s3, s6, s7`, 48 shapes; s6 kept as
  `plans/b2-review/pr585-probes.txt`) re-run on main ad6b94f: 0 second-run differences.

## Regression rows

- Added: 10 en/de rows (#572), 7 en/de rows (#585, incl. the two of its round 1). Changed: the 3
  rows named in D-764 P3.3 (author line added only). No `expected` of an earlier row changed
  otherwise.
- Readings pinned that are not ideal, each required by an approved criterion and named as such:
  "We use 40 thousand and 87Rb atoms" (plain "40K", AC-449.2: nothing tells it from "a 40K
  run"); "1Ca' Foscari University", "2Co-design Lab", "3In Silico Institute" (AC-448.2, the safe
  failure, D-57). No row pins a reading that a filed issue calls wrong (#563 to #567, #576, #578,
  #586 have no row).
- Note, by design (D-764 P2.2): only a raised number before a magnitude letter becomes superscript
  digits, so a title can show "⁴⁰K-40Ar" in the script; the voice says both the same way.

## CHANGELOG (D-768)

Both lines under Unreleased / Fixed on main: "Raised mass numbers in a paper's title are read
(#448)" and "Hidden runs and raised mass numbers no longer change a reading (#445, #449)". Both
survived three main merges (CHANGELOG conflicts with #575 and #583, clean with #569, #577).

## Main CI

Main CI on ad6b94f: run 44435792334 green (tests ubuntu, macos, windows; both Chromium shards; `CI passed`).

## Follow-ups from the batch (all filed, lane:textprep)

#563, #564, #565, #566, #567 (author), #576, #578, #586 (review). None blocks a later batch;
#576 and #586 are the two that touch B2's code.
