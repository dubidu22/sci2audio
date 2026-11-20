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

## D-831 (2026-11-20, owner)
The project workspace moved from the claude.ai Project into `./governance` in the product repository (PR #657, merged 20 Nov 2026). Ruleset 1.4.7 was migrated onto the governance generator as 1.5.0 and regenerated for Claude Code as 1.6.0 (role extracts in `governance/rules/`). META-01 replaces D-713. The authority order now puts the ruleset above the decision log; this amends D-714 b.
Owner messages: "Yes, regenerate" and "Yes, apply" (20 Nov 2026).

## D-832 (2026-11-20, owner)
The knowledge base and the design record of `dubidu22/sci2audio-design` moved into `governance/kb/` and `docs/design/` of the product repository (PR #658, merged 20 Nov 2026), with ruleset versions 1.7.0 and 1.8.0. Four privacy redactions are marked in the decision log. The design repository is archived.
Owner message: "Approve" (20 Nov 2026).

## D-833 (2026-11-20, owner)
The governance PR checks, the critical-path labeler and CODEOWNERS live in `.github` (PRs #660 and #661, issue #659). Colin applied the repository settings himself: branch `main` requires the checks "CI passed" and "governance pr checks", and code-owner review was withdrawn because one account authors every PR, so a code-owner lock cannot bind.
Owner messages: "I have done the github settings you proposed originally" and "Done" (20 Nov 2026).
