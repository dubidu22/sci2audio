# Textprep v1.2 follow-ups: plan

Thread "Plan textprep follow-ups for v1.2" (textprep lane), 15 Nov 2026. Base: main 99b8166.
Follows the textprep v1.2 batch (D-577, PRs #330 #332 #333). Waits for the coordinator's approval.

## 1. What I checked

I ran every row of every listed issue through the whole chain twice on main 99b8166
(make_document → run_steps → rebuilt_from_script → run_steps; probe kept in my scratchpad).
All rows still read as the issues say, with two notes:

- **#336:** on main the first run reads `−↵5` as "− 5" and the second run in my harness reads
  the same (the line break stays in the rebuilt text). The listening bug is real either way:
  "minus" is not read before a line break, while `− 5` and `−5` read "minus 5".
- **#321:** "1 resp. 2 V" reads "1 respektive 2 Volt" on *both* runs, so "resp." is no label
  join today at all, unlike "bzw.".

#278 row 1 is fixed by #330 (`Text ((Smith, 2019); Jones, 2020) here.` → `Text here.`); the subject
row still reads `Jones is cited.` (wanted `Smith and Jones is cited.`, as the flat form reads).

## 2. Every PR is critical

Each PR adds English or German regression cases (golden files, D-69), so each one is critical,
labelled `risk:high`, and gets a review thread with `ci:full`. All seven PRs are branched from main
on their own and touch different modules, so they can be reviewed in any order. The only shared
lines are the appended cases in `tests/regression/english.toml` / `german.toml` and the
`SECOND_RUN_EXCEPTIONS` dicts; I merge main into the next branch after each merge.

Every PR: regression cases written first (failing), unit tests that fail when the fix is reverted
(checked by reverting the fix locally), the second-run check over all regression cases green, the
13 corpus scripts byte-identical unless a change is intended and listed, the fast suite, ruff,
lint-imports and deptry clean. Closing keywords only in the PR body, never in commit messages.

## 3. The PRs, in order

### PR 1: second-run rebuild keeps rewritten labels (#324), testing

First, because it widens the safety net for every PR after it: the corpus second-run test then
covers all papers, maass included.

- `sci2audio.testing.documents.rebuilt_from_script`: map the label through the script instead of
  searching for it in the new text. Find the label in the original block text; keep it when a
  script piece with text still covers part of that span (kept or replaced); drop it when every
  character of it was removed or the block has no pieces left. So a label never appears for a
  block whose label really went (the issue's guard).
- Unit tests: German caption "Abb. 1: …" keeps its label, second run reads "Abbildung 1 wird
  übersprungen."; a caption whose label a step removes loses it; unchanged label stays.
- `test_liu_reads_the_same_on_a_second_run` becomes a parametrised test over every corpus paper.
- The four notice cases leave `SECOND_RUN_EXCEPTIONS`.
- Critical as a change to the `sci2audio.testing` helpers plugin authors use (#203) and to the
  second-run gate; no regression case text changes. Size: small.

### PR 2: units reads the same on a second run (#320, #321, #335)

- **#320:** the glued-x rule counts the word "equals" (the units step's own reading of "=") as the
  operator, as citations does for read signs (#101). Both runs: `Let f(x) equals 4x.`
- **#321:** the German label-join words take the readings the abbreviations step gives the joins:
  "beziehungsweise" for "bzw.", and **"resp." / "respektive" become joins too**, so
  `1 resp. 2 V` reads `1 respektive 2 V` like `bzw.` (an intended first-run change; listed).
- **#335:** a unit right after a fraction the numbers step read as words ("1 half", "3 quarters",
  "minus 3 quarters", the German fraction words likewise) is read as a unit on the first run:
  `3/4 s⁻¹` → `3 quarters per second`, and the second run sees a number word before it and reads
  it the same.
- Removes `symbols-x-in-a-formula` and `de-units-german-label-joins` from the exceptions. Size:
  small to medium.

### PR 3: English numbers read the same on a second run (#336, #340, #210)

- **#336:** the minus rule crosses one line break, as #304 did for `~-`: `−↵5` → "minus 5",
  `−↵1/2` → "minus 1 half", `~−↵5` → "about minus 5".
- **#340 and #210 (same rule):** the power rule reads a power whose exponent is followed by a glued
  second power (`10−410^2`) or has space-grouped thousands (`10^250 000 000`) on the first run, or
  leaves both as printed on both runs; I pick the reading that keeps the first run's words and
  makes the second run match, decided per shape in the PR and probed with the nightly seeds 8080,
  555 and the numbers property.
- #210 sits in milestone v1.0.1; it lands on main with this PR (it has the same cause as #340). If
  v1.0.1 needs it on a release branch, that is a separate backport.
- Size: small to medium.

### PR 4: German numbers and dotted labels (#334, #349, #249)

- **#334:** German date ranges with a spaced en dash, an em dash (spaced or not) or a spaced hyphen
  between two dates read with "bis" and the second date in the dative, as the unspaced forms do:
  `Vom 3.4.2019 – 5.4. lief es.` → `Vom dritten April 2019 bis fünften April lief es.` A day alone
  before the dash (`3. – 5.4.2019`) stays as printed (D-562). Probe the neighbours per the #263
  lesson ("vom 1.–3.4.2020", "1.3.–11.3.2020", times "10 – 12 Uhr", page ranges).
- **#349:** the ordinal rule does not take a number right after the word "Punkt" (a part of a
  dotted number), so `Kapitel 1.2.3. Tag.` reads `Kapitel 1 Punkt 2 Punkt 3. Tag.` on both runs.
- **#249 (added, same reading):** German notices and labels with a dotted number read the dot as
  "Punkt": `Formel 3.2 wird übersprungen.` → "Formel 3 Punkt 2 …", `Tabelle 2.1`, `Abschnitt 3.2`,
  matching the dotted-number reading #349 relies on. English unchanged. If the German corpus
  (maass) changes, each line is listed.
- Size: medium.

### PR 5: links inside brackets (#326, #337)

- **#326:** a URL ends before a ")" that closes a bracket opened before the URL when "(" or "["
  follows right after it. `(see https://example.org)(Smith, 2019) it holds.` → `it holds.`;
  `(Smith, 2019, https://example.org)(Smith, 2019) it holds.` → `Smith it holds.` (both runs).
  English and German. The citations sibling property then also draws link brackets glued to the
  next bracket (its current carve-out goes).
- **#337:** a separator or join word ("and"/"und", ";", ",") that a removed link leaves at a
  bracket's edge goes with the link, as after a removed citation (#305); the rest is judged as a
  second run judges it: `It holds (see https://example.org and Lee, 2019) here.` → `It holds here.`
- Size: medium.

### PR 6: citation nests (#338, #339, #278 subject row)

Inside the D-599 work cap; a shape over budget stays as printed, as now.

- **#338 (decision):** a numeric citation glued after a removed author-year citation is judged as
  if it stood where the removed one stood, after a space, so it goes too:
  `As said by Lee (Smith, 2019)[12] it holds.` → `As said by Lee it holds.` (what the spaced form
  reads today). German alike.
- **#339 (decision):** year shells around a citation that goes, go with it, as a nest 2 deep
  already does (`Text ((Smith, 2019) 2020) more.` → `Text more.`): 3 and 4 deep read
  `Text more.` on both runs. Cases for 2 and 4 deep, en and de.
- **#278 subject row:** `((Smith, 2019); Jones, 2020) is cited.` keeps both names as the flat form
  does: `Smith and Jones is cited.` German alike. #278 closes with this PR.
- Probes: the #330 token fuzz (20k texts, en and de, whole chain twice), nests one deeper than any
  look cap, and the timing tests' ratios on main vs branch (#317 lesson).
- Size: medium.

### PR 7: German abbreviation before a closing quote (#342)

- A German abbreviation that ends a sentence before a closing quote („…“, »…«, ›…‹) and a
  capital keeps its full stop as the sentence end, as without the quote:
  `Er schrieb „usw.“ Dann ging er.` → `Er schrieb „und so weiter.“` / `Dann ging er.`
  Probe "„Dr.“ Müller"-style quotes of a title abbreviation before a name (must not end a sentence).
- Size: small.

## 4. Stays open or moves

- **#341 → Later (recommend).** Marks inside a multi-part abbreviation ("z.¹ B.") or between "CI"
  and its bracket are very rare in print (the issue says so), and the fix needs the citations
  step to skip footnote marks, a cross-step change with little gain.
- **The other textprep issues in v1.2** (#92 #93 #97 #100 #114 #131 #150 #191 #193 #223 #230 #231
  #233 #240 #250 #254 #257 #258 #265 #287 #292) are not follow-ups of the batch. I propose a
  second batch plan after PR 7, ranked by what Colin hears in German and in the corpus first:
  #254 alphanumeric keys like [MH17] (the German corpus paper uses them throughout), #92 Liu's
  unheaded reference list (read aloud today), #230 #231 #233 #250 #265 German readings, #257
  #258, #240 #223 hyphens, #93, #193 #191 #292. Candidates for Later in that plan: #97 (no case
  found), #114 (spelling shows only in the script), #131 (needs a locale setting), #100 (needs a
  reference-list match), #287 (hostile input only; the D-599 cap bounds the worst case).
- **#346 abbreviations** stays out, as instructed.

## 5. Decisions asked for

1. Approve the seven-PR split and order 1 to 7 (all critical).
2. #321: "resp."/"respektive" become German label joins (first run changes for "resp.").
3. #338: the glued numeric citation goes with the removed citation.
4. #339: year shells go with the citation they wrap.
5. #249 joins PR 4; #210 (milestone v1.0.1) joins PR 3.
6. #341 moves to Later.
