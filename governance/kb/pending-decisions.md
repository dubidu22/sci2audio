# Pending decisions — sci2audio

Decisions that are made but not yet in `decision-log.md`. One writer: the
coordinator. It adds an entry here at the hand-off where the decision is made,
with the next D-number, and removes an entry once it sees it in the decision
log. The KB thread reads this file and compiles it into the decision log on
its cadence (`ROLE-08`); it never edits this file.

Entry format, the same as in the decision log:

    ## D-<n> (<date>, owner | coordinator)
    What was decided, why, and what it supersedes.
    Owner message: "<the owner's words and their date>"   (owner decisions only, `KB-01`)

Until an entry is compiled it ranks just below the decision log (`authority`).

## Entries

## D-834 (2026-11-20, coordinator)
Triage of milestone v1.4 after release 1.4.0 (Colin, 20 Nov 2026: "close what 1.4.0 already covers, move what belongs to v1.5 or v2, and propose the first batch per lane for the rest"). Nothing is covered by 1.4.0, so nothing was closed; nothing belongs to the study layer. Six reading features moved to v2: #135, #134, #122, #49, #41, #32. Eleven issues stay as 1.4.x work: #217, #216, #203, #181, #172, #125, #126, #59, #56, #55, #54. Three new backlog issues in v1.4: #663 (real-espeak tests exit pytest on macOS), #664 (CodeQL scans the design prototype and the governance workspace; default setup cannot take paths-ignore), #665 (lanes.yml owner of governance/** and docs/design/**). Rule applied: a bug stays, a new reading feature goes to v2.

## D-835 (2026-11-20, coordinator)
Plan B-L1 (#125, #126; `plans/layout-b-l1-plan.md`) approved. #125 is fixed in extraction (`extraction/pdf.py`), not layout, because layout keeps every line's text verbatim (D-57) while extraction builds the line text; the PR carries lane:extraction too (precedent D-278, no extraction batch active). Only accents extraction would split into a line of their own are composed; accents inside a line stay for the #65 text step, so its marked edits stay marked. The accent line's id goes missing, no renumbering. #126 measures the row band from the base letters, not the glyph boxes.

## D-836 (2026-11-20, coordinator)
Plan B-P1 (#216, #203; `plans/plugins-b-p1-plan.md`) approved. Public surface is `sci2audio.textprep.api` (re-exports only, `__all__` is the stability promise under `TEXT_STEP_API`); entry-point group `sci2audio.text_steps`, a class or zero-argument factory, entry-point name equals step id; built-in steps of a stage first, plugins after by id, so a built-in edit wins on overlap; a plugin must declare `api_version` itself; a guard gives plugins a document copy, catches `Exception` and `SystemExit`, and abandons a step after 60 s in a worker thread; `JobRunner` loads plugins once at construction. App wiring (`app/runner.py`, `app/report.py`, `cli.py`) is in the PR; `web/player.py` and the web files are not, because B-W1 changes `web/` at the same time (LANE-02): that becomes a web-lane follow-up issue. No plugin off-switch yet (issue). A CHANGELOG line under Unreleased added by each of two parallel PRs is not a lane conflict; the second to merge rebases.

## D-837 (2026-11-20, coordinator)
Plan B-W1 (#217, #172; `plans/web-b-w1-plan.md`) approved. The opt-in update check lives in `app/updates.py`, state in `update-check.json` beside `settings.json` (missing or damaged file means off), one GET to the GitHub releases/latest endpoint at most once a day, `User-Agent: sci2audio` without version, `trust_env` off, redirects refused, only `tag_name` used and the link built by us; runs only in the server, never in the CLI commands; failures are logged locally and never block. Headers Permissions-Policy (autoplay=(self), everything else denied) and COEP require-corp join `SECURITY_HEADERS`. The CLAUDE.md hard rule is widened in the same PR to "No network calls except a voice or model download the user started, and the update check the user turned on (at most one request a day to the GitHub releases API, sending nothing but the request itself; off by default)", so rule and behaviour change together; INV-03 in the ruleset is unchanged (META-01). An AST test pins which modules may import network libraries (META-03). Follow-ups "check now", proxy support and CLI update check go to v2.
