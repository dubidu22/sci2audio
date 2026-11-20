# Issues #227 and #229: German sentence ends — plan

Thread "Add German text reading rules", 14 Nov 2026, on main 3b9ac6d plus PR #256 (#101). One PR
for both issues (they are two sides of one rule: where a German full stop ends a sentence),
branch `textprep/german-sentence-ends-227`, base `main`. **Critical**: it adds German regression
cases (golden file) and may change the German paper's utterance counts, so `risk:high`; waits for
the coordinator's approval. #253 (German number second-run cases) stays a separate PR: it is in
`numbers_de.py`, not in the cutter or the units step, and its acceptance criteria share nothing
with these two.

## 1. Measured today (main 3b9ac6d + #256, whole German chain, then `cut_utterances`)

Wrong cuts (#227):

| printed | utterances today |
|---|---|
| Es folgt 2. Teilnehmer Gruppe B. | "Es folgt 2." / "Teilnehmer Gruppe B." |
| Seit 3. Quartal stieg es. | "Seit 3." / "Quartal stieg es." |
| Er wurde 3. Sieger. / Er war 2. Vorsitzender. | cut after "3." / "2." |
| Siehe abb. 3 dazu. | "Siehe abb." / "3 dazu." (cut before a digit) |
| Es gilt o. J. als Datum. | "Es gilt o." / "J. als Datum." |
| Gemessen in Tsd. Euro. | "Gemessen in Tsd." / "Euro." |
| Am 3. 4. 2019 kam es. | "Am 3." / "4." / "2019 kam es." |

Already right, no change needed: "Die 3. Welle", "Im 3. Quartal", "zum 1. Mal", "Der 2.
Weltkrieg" (PR #242 reads these ordinals, and the cutter never cuts inside a replacement);
"S. Müller" (single initial rule); "Nr. sieben", "1. bis 3." (lower case after the stop never
cuts); "usw. Dann" (cut, right: "usw." can end a sentence, D-234).

Lost sentence ends (#229): the units step takes the full stop of "Std.", "Min.", "Mio." along:

| printed | utterances today |
|---|---|
| Die Messung dauerte 2 Std. Danach wurde gewertet. | one utterance, "2 Stunden Danach wurde …" |
| Es dauerte 5 Min. Dann kam er. | one utterance, "5 Minuten Dann kam er." |
| Es kostet 2 Mio. Er zahlte. / 2 Mio. Im Jahr danach | one utterance each |
| 2 Mio. Euro / 3 Mrd. Dollar / 5 Min. Pause / 3 Std. Fahrt | one utterance (right) |

The German corpus (the PrivacyScore paper and the two German samples) has none of these cases:
a scan of their scripts finds no cut after a digit or a short dotted word. So the corpus goldens
should not change; the regression cases carry the rule.

## 2. Design

**One German word list: sentence openers.** `textprep/data/de/sentence_openers.toml` (written
for sci2audio, GPL-3.0-or-later), loaded by `wordlists.py` like the other German lists. About 120
words that start a German sentence but are rarely a noun after a number or a unit: articles and
their forms (Der, Die, Das, Dem, Den, Des, Ein, Eine, …), personal and demonstrative pronouns
(Er, Sie, Es, Wir, Ich, Ihr, Man, Dies, Diese, …), prepositions fused or not (Im, Am, Zum, Zur,
Beim, Vom, In, Auf, Mit, Nach, Bei, Für, Von, Aus, …), conjunctions and adverbs (Danach, Dann,
Außerdem, Daher, Deshalb, Somit, Jedoch, Aber, Und, Auch, Hier, Dabei, Damit, So, Zudem, …),
question words (Wie, Was, Wer, Warum, …). Nouns never go in.

**#229, units step (`units.py`, German table only).** A unit printed with a full stop keeps the
full stop outside its replacement when the next word is a sentence opener, or when a sentence
end can be seen otherwise (an opening quote or bracket then a capital, as today's block-end
rule). "2 Std. Danach" reads "2 Stunden. Danach"; "2 Mio. Euro", "3 Std. Fahrt" keep today's
reading. English has no dotted unit and is untouched.

**#227, utterance cutter (`utterances.py`).**
1. `ABBREVIATIONS["de"]`: built from the German abbreviation list (`data/de/abbreviations.toml`,
   every printed form and each dotted token of a spaced form, lower case) minus the entries with
   `can_end_sentence`, plus the dotted units and magnitudes of `data/de/units.toml` ("std.",
   "min.", "sek.", "mio.", "mrd.", "tsd.") and "o." (left as printed on purpose). Built from the
   lists, not typed again, so a new abbreviation is covered at once. A German row of
   `_BEFORE_NUMBERS` is not needed: the German list reads its number-only forms itself.
2. German only: after "<1 to 3 digits>." (an ordinal or a stop after a number that no step
   read), the cut needs a sentence opener after it, or a digit after it only when the digits
   before are a full date's year (so "Am 3. 4. 2019" stays one sentence). "Es waren 3. Die
   Studie lief." is still cut ("Die" opens); "Er wurde 3. Sieger." is not.
3. The module docstring gains the German rules and their limit: a capital noun after a number
   and a full stop is read as the same sentence ("Es waren 3. Studien zeigen das." is one
   utterance), because German nouns are capitalised and the opener list never holds nouns.

## 3. Open choice (needs the coordinator's answer)

- **Q1. Ordinals before a capital (#227 criterion 2).** The issue keeps the cut whenever a
  capital follows "<digits>.". Recommended instead: cut only before a sentence opener (2.2
  above), the same list #229 needs. It fixes "Er wurde 3. Sieger" and "Seit 3. Quartal" and
  keeps "Es waren 3. Die Studie" cut; it misses a sentence that starts with a noun after a bare
  number ("Es waren 3. Studien zeigen das." becomes one utterance). The other way, as the issue
  says, keeps today's wrong cuts in the table above. Nothing is lost from the text either way;
  only a pause and pitch move.

## 4. Tests

- Unit tests in `tests/unit/test_textprep_utterances.py` (German section) and
  `tests/unit/test_textprep_units_abbreviations.py`: every row of section 1, both directions.
- `tests/regression/german.toml`: cases with `utterances` for each rule (wrong cuts gone,
  "Es waren 3. Die Studie" still cut, "2 Std. Danach" cut, "2 Mio. Euro" not cut).
- Hypothesis: the existing utterance properties (spans in order, text kept) run with German
  documents too; a German property that a dotted unit's full stop is either in the replacement
  or right after it, never lost; the German second-run property of `test_textprep_units_*` keeps
  running (a kept full stop must not make "Stunden." read anything new).
- The word list gets a test that no entry is a noun from the German unit or abbreviation lists.
- English: the English utterance cases and corpus scripts stay byte-identical.

## 5. Size

Small to medium: about 150 lines of code, 120 list lines, 150 lines of tests. One PR, after
PR #256 merges (both touch textprep; no shared files except `german.toml`).

## 6. Decision

Approved by the coordinator 14 Nov 08:43 UTC; Q1 decided as recommended (D-530): cut after
"<digits>." only before a German sentence opener from the shared word list. One critical PR for
both issues, fresh review thread. #253 is a separate small PR.

## 7. Found while building #253 (14 Nov ~09:30 UTC), to fix in this PR

- **Citation after a read abbreviation loses the sentence end** (both languages, on main):
  "Siehe Kap. (Müller, 2019). Dann mehr." reads "Siehe Kapitel Dann mehr.", "See e.g. (Smith,
  2019). Then more." reads "See for example Then more.". The citations step's `_tidied` (M2 of
  the #66 review) takes the full stop after the citation when the kept text ends with an
  abbreviation's full stop ("Smith et al. (2019). Then"), but the abbreviations step then reads
  "Kap."/"e.g." with its full stop. Fix: take it only when the abbreviation stays as printed or
  keeps its full stop (`can_end_sentence`). English regression case needed.
- **An ordinal before a sentence opener** after a removed citation: "Die 12. (Müller & Schmidt,
  2019). Dann mehr." reads "Die 12. Dann mehr." and a second run "Die zwölfte Dann mehr." (D1 of
  the PR #256 review). The numbers step's ordinal rule must not read "<digits>." before a
  sentence opener even after an article: same word list as 2.2.
