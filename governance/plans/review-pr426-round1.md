# Review of PR #426 (v1.1.0 R2, release day), round 1

Reviewed head **702a318** (draft), base `release/1.1` e9d08ef. Critical (release), Opus high. 16 Nov 2026 ~03:25 UTC. Round 1 covers what is there now; Colin's results (listening scores, VoiceOver, M4 speed rows, Dependabot) come in a second commit, and the final round reviews that head.

**Verdict: nothing to fix in what is there.** Two optional notes. Not mergeable yet by design (draft, results missing).

## What was checked

| Item | Result |
|---|---|
| Diff | `CHANGELOG.md` (one line), `docs/listening-tests/template.md`, new `docs/listening-tests/1.1.0.md`. Docs only. |
| CHANGELOG heading | `## [1.1.0] - 2026-11-16`. The release workflow's date grep passes on it; the notes awk extracts 61 lines (summary to Known issues, stopping before `## [1.0.0]`). If the tag lands on a later day, the date must change in the final commit (the workflow checks the shape only, not that it is the tag's day). |
| Template | "10 paragraphs" becomes 13 with the reason; rows 11 to 13 added. Matches plan choice c. |
| 1.1.0.md rows 1 to 10 | Identical to the 1.0.0 rows (line diff). |
| Rows 11 to 13 | Checked against `sci2audio script` on `arxiv2017-maass-privacyscore.pdf` (default settings) on this head: chapter 3 "2 Verwandte Arbeiten" starts with "Mehrere Dienste erlauben eine automatisierte Untersuchung", followed by "Abbildung 1 wird übersprungen." and its caption "Abbildung 1: Anwendungsfälle und Datenstrukturen"; chapter 4 "3 PrivacyScore im Überblick" has "Flexibilität durch Nutzerorientierung PrivacyScore bietet …" (lead-in run into the paragraph) and the next sentence with "zum Beispiel" ending "… voneinander zu unterscheiden und Zusammenhangsanalysen durchzuführen."; chapter 7 "6 Rechtliche Fragestellungen" has "Zuerst stellt sich allerdings die Frage, wem die zu untersuchenden Daten „gehören“ …" and "Die Begründung von Eigentum kann gemäß § 903 BGB nur an Sachen im Sinne von § 90 BGB bestehen." Every chapter number, title and quoted text is right. |
| Voice line | af_heart rows 1–10, dm_thorsten rows 11–13, speed 1: right (German voice for a German text by default, D-469). |
| CI on 702a318 | Linux run in progress (docs only); lint, licences, security green. |

## Notes (optional, not asked)

- **N1.** The 1.1.0 summary still says "many readings now come out the same when the script is read a second time". Round 1 of #412 changed the Known issues line because a user cannot read the script a second time; the summary uses the same phrase. The Fixed lines use "on a second pass" throughout, so this is accepted wording; change it only if the author touches the line anyway, e.g. "and many readings that changed on a second pass over the script now stay the same".
- **N2.** 1.0.0.md told the listener how to make the audiobooks ("Make the audiobook of each paper with the default settings … then listen in the read-along view"); 1.1.0.md does not. The commands are in the plan's hand step B; one line in the sheet would make it self-contained: `sci2audio voices download --language de` once, then `sci2audio convert <file>` and `sci2audio listen <file>`.

## Final round will check

- The second commit: the scores in every cell of rows 1–13 (or Colin's own words if he gives none, as 1.0.0), Date filled, VoiceOver result, the M4 rows in `docs/baseline.md` (as printed by `scripts/speed.py`), the Dependabot answer, any issues opened, and the CHANGELOG date equal to the tag day.
- Nothing outside docs changes.
- `ci:full` on the final head and three-green before the go; then the exact tag commit for Colin's step F.
