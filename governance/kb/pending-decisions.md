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

## D-838 (2026-11-20, owner)
The CLAUDE.md hard rule "No network calls except a voice or model download the user started" is widened in PR #675 to also allow the update check the user turned on (at most one request a day to the GitHub releases API, sending nothing but the request itself; off by default). The web/app thread edits CLAUDE.md only on the owner's own word, so the coordinator's D-837 did not suffice; the line goes in with the round-1 fix commit. The ruleset INV-03 is unchanged.
Owner message: "Yes, add the line" (20 Nov 2026).

## D-839 (2026-11-20, coordinator)
Plan B-I1 (#664, #665; `plans/infra-b-i1-plan.md`) approved. CodeQL moves to advanced setup (Colin switched the repository and GitHub opened PR #680, which becomes the batch PR) with a config that ignores `docs/design/prototype/**` and `governance/**`; `.github/governance/**` stays scanned because it is code that runs in CI; the three languages, triggers and alert categories of the default setup are kept so dismissals carry over; permissions are the minimum, actions SHA-pinned. `lanes.yml` lists every governance path explicitly: ruleset, extracts, instructions, `governance-config.json`, `github-setup/**` and `tools/**` are lane:infra; kb, plans, ledger, state, memory, release and `workflow-export.md` are lane:docs; `docs/design/**` is lane:docs. `pr-checks.json` mirrors it and its `governance_paths` narrows to the docs-lane working files, so a PR that changes the ruleset or extracts needs the title format, lane:infra and risk:high (META-03). One PR for both issues.

## D-840 (2026-11-20, coordinator)
Plan B-L2 (#181, #54, #59, #55, #56; `plans/layout-b-l2-plan.md`) approved as one non-critical PR, every rule shaped so the corpus output stays byte-identical; a golden change would make it critical and stop it before the PR. #181 is narrowed from "whatever its width" to: the rule is read before the line, lies under at least half of it, and no footnote or inline host takes it first; the wide reading would move footnote rules, running-head rules and fraction bars in the corpus. New setting `plot_size` (4 em) for uncaptioned scatter plots (#59). #55 takes only text smaller than the body and none when one drawing holds it all (D-57 safe side). #56 keeps small row-mates to the column of the line that brings them unless the table already spans both columns.

## D-841 (2026-11-20, coordinator)
B-L2 (#181) changes one golden line after all: Liu p4's two fraction bars (p4-d1, p4-d2), which the D-90 fallback put into the page-number furniture block, now join the paragraph of their own inline fraction. Accepted as the right reading rather than tightening #181 to keep the corpus byte-identical; the PR becomes risk:high and critical (CRIT-01), with the line explained in the PR body and a three-system run before review. Amends D-840's "non-critical".

## D-842 (2026-11-21, coordinator)
Batch of 20 Nov 2026 closed: six PRs merged (#677, #671, #676, #675, #680, #682), 1.7 review rounds on average, two at most, no revert, no gate override. The finding kind "missing-test" (a test promised in the plan absent from the PR) came up in #671 and #675; per META-03 it gets a check, not a reminder: the batch audit proposes the mechanism and it becomes an issue in the next batch. Two process lessons recorded for threads: removing the ci:full label restarts "governance pr checks", so the label comes off before the merge step; several threads commit in the shared governance worktree, so every commit stages only its own files.

## D-843 (2026-11-21, owner)
Colin: "Start batch 2" (21 Nov 2026, ~04:35Z). Batch 2 of the v1.4 remainder runs as proposed: textprep B-P2 #684 (critical); web/app B-W2 #666 #668 #685 as one web PR (#685 critical), then #667 #669 as one app PR; infra B-I2 #681 #687 (both critical). Threads plugins-b-p1, web-b-w1 and infra-b-i1 each take the batch after a THR-01 fitness check; a mismatch replaces the thread. Afterwards docs #678 #686, layout #679 in a new thread, voices #663; #683 waits for Colin. The local deselect rule for the abort test (20 Nov) is lifted: every branch now starts from main with #677.


## D-844 (2026-11-21, coordinator)
Plugin guard copies: `run_plugins` gives every plugin call its own deep copy of the document (one copy per call, not one per job), and a change to the copy counts as plugin failure. Deviation from plan plugins-b-p1 §3, accepted in review of #676 (note N2); cost is a copy per plugin per stage, acceptable for text documents. Recorded here because the plugins thread's fitness check named it as the one undecided item.

## D-845 (2026-11-21, coordinator)
Plan B-P2 (#684, plans/plugins-b-p2-plan.md) approved. A text-step plugin's import, factory and attribute reads run in the same worker-thread guard as `find`, one entry point after another, each under `PLUGIN_LOAD_TIMEOUT = 30 s` (a module constant, shorter than the 60 s `find` budget because loading sits on the start-up path of every command; long enough for a heavy import on a slow disk). A plugin that runs out of time becomes a `PluginProblem` and the others still load; Ctrl+C is re-raised. `sci2audio.textprep.api` is unchanged. Not chosen: parallel loading under one deadline (non-deterministic order, import-lock contention) and one shared deadline (plugins after a hanging one would get no time).

## D-846 (2026-11-21, coordinator)
Plan B-I2 (#681, #687, plans/infra-b-i2-plan.md) approved as two PRs with no shared file. #681: KB documents are critical by name prefix (`adr-*`, `playbook-*`, `doc-*`, plus `governance/kb/README.md`) in `critical_paths` and the labeler; audits, working files, feature files, the decision log, pending decisions, merged batches and the index are records; a test requires every KB file to be one or the other; no files move. Consequence: a governance sync PR that edits a playbook or ADR now needs `risk:high`. #687: the PR body section `## Tests promised in the plan` lists pytest node IDs; the governance check collects the named files on the PR head and fails naming every ID that does not collect; no section passes unchanged (opt-in), an empty section fails; the body reaches the script through an environment variable only. Condition: the workflow runs on `pull_request` with read-only permissions, asserted by a test, because collection executes PR code. The plan-template wording stays on Colin's list (META-01).
