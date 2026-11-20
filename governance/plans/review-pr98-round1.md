# Review of sci2audio PR #98, round 1 (issue #65: Unicode clean-up and line-end hyphens)

Reviewed head 7502486 (main 660d21f merged in), 13 Nov 2026. Plan:
plans/issue65-unicode-hyphens-plan.md; decisions D-149 to D-153.

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`: clean.
- Fast suite (`HYPOTHESIS_PROFILE=ci`, `-m "not slow and not benchmark"`): 1124 passed, 31 snapshots passed.
- Nightly Hypothesis profile, 3 random seeds, on test_textprep_characters, test_textprep_hyphens,
  test_textprep_conformance, test_app_script, test_textprep_runner: 196 passed on each of 3 seeds.
- Layer plants: `import sci2audio.testing` and `import sci2audio.layout` in characters.py and in
  hyphens.py each BROKEN as they should be.
- CI on 7502486: green on Linux, macOS and Windows.

## Golden files and regression cases, checked line by line

- `tests/regression/english.toml`: the two changed `expected` lines ("development",
  "difficulties", "processing"; "Androff") are what a reader says. All ten new cases checked
  character by character (control characters made visible); each matches its goal.
- `tests/regression/line-end-hyphens-en.toml` (495 rows): I rebuilt every line-end hyphen from
  the corpus layout output with the context around it and the document's own counts. The 114
  rows with no evidence in the paper (my count; the PR says 121, the difference is how a
  hyphen next to digits counts) I read one by one: all correct. The 68 rows settled by a single
  printed form or by conflicting counts (for example "inter-band" 3 joined to 1 hyphenated,
  "pre-training" 3 to 35): all correct. Every keep row (64) is a real compound, a name or a
  number. The 7 misses are real and their reasons are right. No row reads "none" in the corpus.
- `test_textprep_furniture.ambr`: furniture counts unchanged; the new "characters: accepted"
  counts equal the line-end hyphens per paper plus the Unicode edits (chi 159+1, hardt 83+1,
  nowak 72+15, arsiwalla 85+0, liu 83+23, waskom 11, biggs 2). I listed all 40 Unicode edits:
  39 are right, one is wrong (M1).
- `test_app_corpus.ambr`: the script snapshots of hardt and waskom keep their 558 lines; with
  white space, hyphens and spacing accents removed, old and new are identical, so the only
  change is the joined or kept words. The 41 furniture report entries are all still there
  (moved, not changed); 94 hyphen entries and 1 Unicode entry are new.
- Test changes in test_app_script, test_textprep_furniture, _runner and _steps: each one keeps
  what the old assertion meant; nothing is weakened.

## Findings

### M1 (must fix): a maths hat inside a word is composed as an accent

liu-orbital-hall, paragraph: "1/2{Lˆ z, vˆy}" (the hats of L̂_z and v̂_y) becomes "vŷ" with the
reason `accent printed apart from its letter: "ˆy" read as "ŷ"`, which is not true: the hat
belongs to the v. The plan's table allows "ˆ only inside a word", and this is the only in-word
circumflex in the corpus. Proposed fix: compose ˆ only onto a vowel (a, e, i, o, u, also ı and
capitals), the TeX accent case ("J´erˆome" still reads "Jérôme"); a hat over any other letter
is left alone. Tests: this exact liu text, and "J´erˆome". The liu count in the furniture
snapshot then goes from 106 to 105; say so in the PR.

### S1 (should fix here): the hyphen step does not see through TeX accents and ligatures

The one-letter test of rule 4 counts raw characters, and a spacing accent ends a word:
- "Kl¨a-\nui" reads "Klä-ui" (before = "a", one letter, kept)
- "Garc´ı-\na" reads "Garcí-a" (before = "ı")
- "ﬁ-\nnally" reads "fi-nally" (the ligature counts as one letter)

None of the 495 corpus rows is affected, but liu's reference list is full of such names, so a
line break inside one is a matter of time. Proposed fix: let the hyphen step's word pattern
take the spacing accents of `characters.ACCENTS` as part of a word (before and after, and in
`printed_words`), and measure "one letter" on the NFKC-folded word. Tests: the three cases
above, and add one accented word and one ligature word to the property `WORDS`.

### N1 (note for #66, no change here): a DOI split at a hyphen is joined

"https://doi.org/10.18653/v1/2023.acl-\nshort.4" reads "...acl" + "short.4". #66 runs earlier
and wins overlaps, so its URL and DOI edit has to cover a line break inside the address. The
coordinator should pass this to the #66 thread.

### N2 (follow-up issue): the report shows a kept hyphen as an empty quote

The markdown report prints a kept hyphen (the edit removes only the line break) as
`“” → left out`, and a joined one as `“-” → left out`. The reason says what happened, but the
quote looks like an empty edit. This is report code (#70), first reached by this PR. Please file
an issue (show a line break as, for example, "line break").

### N3 (nit): a look-alike reason

The Kelvin sign gives `mathematical characters "K" read as "K"`, which reads as a no-op. For a
letterlike symbol whose plain letter looks the same, name the code point
(`U+212A KELVIN SIGN read as "K"`). Fix or decline with a reason.

### N4 (nit): say what D-150 means for later rules

Add one line to the registry docstring: the rules before the characters steps see the printed
characters (ligatures, maths letters, spaced TeX accents, "eV˚A"), so #66, #67 and #68 must match
those forms themselves.

## Verified, no finding

- Both steps follow the plan's table 2.1 and the six rules of 2.2 in order; ZWJ, ZWNJ and
  U+FFFD stay; white space gets no edits (D-151); the hyphen step is English only (D-152); no
  word list or new dependency (D-149); both steps are last in BUILT_IN_STEPS (D-150).
- Contraction guard ("it´s") does not hit Polish "Wi´sniewski" (the s is followed by a letter).
- Timing: 384k characters of long hyphenated words 0.06 s, 30 000 line-end hyphens 0.9 s for the
  whole run, 100k invisible characters 0.06 s, 50 000 soft hyphens at line ends 0.64 s.
- Hypothesis strategies are weighted toward the characters in question.

## Decisions D-149 to D-153

None changes in substance. M1 narrows one detail of the plan's table 2.1 (a circumflex inside a
word is composed only onto a vowel); D-153 itself (TeX accents set apart from their letter are
composed) stands.

## Nightly result

Nightly profile, 3 random seeds: 196 passed each time (2 min 11 s to 2 min 20 s).
