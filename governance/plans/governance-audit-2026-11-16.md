# Ruleset audit: sci2audio (rules/project-rules.yaml, version 1.3.0, dated 2026-11-16)

Audit run 16 Nov 2026, 15:45 to 16:15 UTC, with the `project-governance-init` skill (Mode B) from `dubidu22/claude-project-setup-skill`. Read-only: nothing in the code repo, any PR, or the rules file was changed.

Inputs read: `rules/project-rules.yaml` and `.json` (the JSON twin matches the YAML exactly); the project instructions (session context) and `workflow-export.md`; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`, `.github/lanes.yml` and the `on:` triggers and OS matrix of every workflow in `dubidu22/sci2audio` at main 12fd90d; the decision log in `dubidu22/sci2audio-design` at main 57eb6ae (through D-690); `kb/kb-batch-2026-11-17-pending.md` (D-691 to D-709); both ledgers.

Facts taken as current (from the coordinator's brief, all confirmed in the pending KB batch or Colin's messages): D-705 one implementation plus one review thread; D-703e round-4 hard stop; D-702h 60-minute watchdog; coordinator merge go pinned to a head; main merged in, never rebased or force-pushed (D-698); control words of D-702e; a pause active since 13:24Z.

Known gap, noted and not flagged: KB main stops at D-690. D-691 to D-709 exist only in the 17 Nov pending batch, which has not been opened as a PR because of the pause. D-710 and D-711 exist only in the review reports `plans/review-pr450-round1.md` and `plans/review-pr451-round1.md` and the coordinator's memory. They are not in the pending batch yet.

## Verdict

The ruleset is sound in substance. The merge protocol, the round-4 hard stop, the ban on force-push and rebase, the atomic replacement rule (THR-04) and the release-branch CI exception (CI-05) are all stated correctly, and the workflows can deliver what the rules ask for (`ci.yml` widens to three systems on `ci:full` for PRs into any branch). **Do not resume threads from this file as it stands.** First fix M1: the file says `paused: false`, but the project has been paused since 13:24Z, so a thread that re-reads the rules after a compression would read itself as free to run. M2 to M4 should be fixed in the same pass. They are contradictions in `CLAUDE.md`, which every implementation thread loads from the repo, and in REV-01. Two of them break architectural invariants: release CI precedence (M3) and KB criticality scope (M4). M5 and M6 are wording contradictions that have not caused damage yet, and they are cheap to fix. Everything else is scope, state leakage and size. Fixing those would cut the file from about 8,400 to about 4,500 tokens per read.

## Must fix (contradictions and invariant violations)

- **M1. `active_now.paused: false` and CMD-05 `active: false` vs the live pause (Colin, 16 Nov 13:24:08Z, "pause all threads", D-702e).** This is stale state and it is a pause flag. A thread that reloads the rules after a compression sees no pause. In the same block, `notify_when_reader_usable: pending` is also stale, because the notice was sent at 08:32Z. **Fix:** move `active_now` and the `active:` flags of `control_commands` out of the rules into a new `rules/project-state.yaml`, which only the coordinator edits as things happen. Add a pointer and this rule:
  > **META-02** (all): "This file holds standing rules only. Current state (pause, slow down, freeze, autonomy horizon, milestones in progress, batches finishing under an old limit, pending notifications) is in `rules/project-state.yaml`. Read both after every compression."

  Proposed `rules/project-state.yaml` as of now:
  ```yaml
  project: sci2audio
  updated: "2026-11-16T15:45Z"
  active_now:
    autonomy_horizon: "until v1.3 finished"          # CMD-01, D-702a
    paused: true                                     # Colin 16 Nov 13:24:08Z; lifted only by "continue"
    pause_exceptions: ["a thread still answers Colin's own messages in its thread"]
    slow_down: false
    thread_freeze: false
    watchdog_interval_minutes: 60                    # D-702h
    milestones_in_progress: [v1.2, "v1.3 The Working Reader", "v1.1.0 release (Colin's hand steps)"]
    finishing_under_old_limit: ["web lane batch D (#451)", "textprep batch 2 PR 6 (#450)", "release v1.1 (#426)"]   # D-705
  notifications_pending:
    - "v1.3 complete: notify Colin with run commands (CMD-02)"   # reader-usable notice sent 16 Nov 08:32Z
  control_commands_reference:
    "continue working until v1.3 finished": "autonomy horizon (CMD-01)"
    "slow down": "see CMD-04"
    "pause all threads" / "stop": "see CMD-05"
    "continue": "lifts pause, slow down or freeze"
  ```

- **M2. `CLAUDE.md` Workflow item 2 ("At most three implementation threads run at once, one per lane", D-626) vs LANE-02 (one implementation thread plus its review thread, D-705).** `CLAUDE.md` was last aligned by PR #441 at 08:38Z. D-705 came at 08:55Z, so the repo file never got it. Implementation threads load `CLAUDE.md` automatically, and the rules rank it last, so a fresh thread meets the stale limit first. **Fix** (docs PR to sci2audio after the pause). Replace item 2 with:
  > "2. **Lanes.** PRs are batched by lane (extraction/voices, layout, textprep, app/release): one PR per lane covers several related Issues. Only one implementation thread and its review thread are active at a time (D-705); a lane thread lives for one batch (D-626). A PR changes files of its own lane only (`.github/lanes.yml`). Stop if an Issue lacks acceptance criteria."

- **M3. `CLAUDE.md` Workflow item 8 ("PRs into a `release/N.N` branch run Linux CI only (D-702g)") vs CI-05 and MRG-02 (a critical PR into a release branch still gets a `ci:full` three-system run on its final round, D-703b).** This breaks invariant 2, release CI precedence. The repo states the branch trigger without the critical exception, and release PRs are critical by definition (packaging and release). **Fix:** replace that sentence with:
  > "PRs into a `release/N.N` branch start Linux CI only; a critical one still gets a `ci:full` three-system run on its final round before merge (D-702g, D-703b)."

- **M4. REV-01 ("Every PR except KB PRs is reviewed…") vs CRIT-01 and CRIT-03 (KB process, contract and architecture documents are critical and get the full process, D-703c).** This breaks invariant 3, KB criticality scope. REV-01 exempts every KB PR, and CRIT-01 exempts only the daily decision-log PR. `CLAUDE.md` items 7 and 10 repeat the broad exemption, and the project instructions say "Critical means any change to … the KB" without the exemption. **Fix:**
  > **REV-01** (review): "Every PR is reviewed before merging in a separate thread that did not write it. The only exception is the daily decision-log PR of KB-03. KB process, contract and architecture documents are critical (CRIT-01) and are reviewed like code."

  In `CLAUDE.md` item 7, change "Every PR except KB PRs" to "Every PR except the daily decision-log PR". In the project instructions, change "the KB" in the critical list to "the KB's process, contract and architecture documents (the daily decision-log PR is exempt, D-703c)".

- **M5. `authority` order vs ROLE-01 and ROLE-03.** The list puts `kb_decision_log` and `pending_kb_batch`, which are mostly "Decided (Claude)" rows, above `colin_messages`. Taken literally, an older coordinator ruling beats a newer message from Colin, while ROLE-01 says Colin may revise any "Decided (Claude)" entry at any time. The live case is the pause: it exists only as Colin's message and a note in the pending batch, and the rules file (M1) says the opposite. Separately, the project instructions call the KB *and* `CLAUDE.md` the source of truth without ranking them, while the rules rank `CLAUDE.md` last. `workflow_export` is ranked above `CLAUDE.md` and memory, but it is a write-up meant for sharing and still says "three implementation threads" (lines 25, 70, 280). **Fix:**
  ```yaml
  authority:   # first wins; within one source the newest entry wins
    - colin_messages_newer   # a message of Colin's newer than the conflicting entry
    - project_instructions
    - kb_decision_log        # a "Decided" (Colin) row beats a "Decided (Claude)" row
    - pending_kb_batch
    - project_rules          # this file + project-state.yaml; a summary that must match the above
    - claude_md
    - project_memory
  ```
  Drop `workflow_export` from the list (CMD-04 already carries its meaning of "slow down" via D-702e). In the project instructions, replace "Source of truth: knowledge base … and CLAUDE.md" with: "Source of truth, in this order: Colin's newer messages, these instructions, the KB decision log (docs/kb), CLAUDE.md. `rules/project-rules.yaml` summarises them and `rules/project-state.yaml` holds current state."

- **M6. PR-05 (a critical PR needs the author's own green `ci:full` *before* review) vs REV-03 (the three-system matrix runs for critical PRs "only, on the final round").** Both come from D-626 and D-698, and read together they disagree. There is also a side effect in the workflow: `ci.yml` keeps the three-system matrix on every `synchronize` while the `ci:full` label stays on, so every fix commit of a critical PR runs macOS and Windows. **Fix:**
  > **PR-05** (implementation): "A PR goes to review only after its Linux CI is green. A critical PR also needs one green `ci:full` run on the head handed to review; the author then removes the `ci:full` label so fix commits run Linux only."
  >
  > **REV-03** (review): "For critical PRs, on the final round only, the review thread adds `ci:full` for the three-system run on the final head and reads mutation and nightly-seed results from dispatched workflows instead of running them. Earlier rounds run Linux CI only, apart from the author's pre-review run of PR-05."

## Should fix (scope, state leakage, drift from generator)

- **S1. 105 of 115 rules have no `applies_to`.** Only ROLE-01 to ROLE-10 and WD-01 are scoped. A thread cannot filter for the rules that bind it. Proposed scopes:

  | Section | `applies_to` | Exceptions |
  |---|---|---|
  | autonomy, models, release | coordinator | REL-04 → owner |
  | lanes, plans, pull_requests, testing, code_hard_rules | implementation | LANE-02, LANE-04, PLAN-02 → coordinator |
  | reviews, merging | review | REV-06, MRG-04 → coordinator |
  | threads, critical, ci, github, reporting, owner_preferences | all | THR-01, THR-03, THR-07, THR-08, GH-05, REP-01, REP-04 → coordinator |
  | kb | kb | — |

  A scratch copy with these scopes, M1 applied, and CI-01, LANE-02 and THR-05 reworded as below comes back from `audit_rules.py` with **0 errors** (2 warnings: no lane mapping note, 106 rules).
- **S2. Other state inside the rules.** These change before the next milestone, so they belong in `project-state.yaml` or should be deleted:
  - LANE-02's "From 16 Nov 08:55Z" and its list of batches that finish under the old limit.
  - LANE-04's note on the v1.1 release.
  - PR-08's "release/1.1"; make it "the open release branch".
  - GH-03's note on closing milestone v1.0, and its milestone number map.
  - GH-05's roadmap order.
  - `sources.pending_kb_batch` ("D-691 to D-701; D-702 to be added"; it now holds D-691 to D-709).
  - `sources.claude_md` pinned to main 8fb51ac, which is older than #441.
  - `sources.kb_decision_log` pinned to 57eb6ae.
- **S3. Dead history.** The script flags LANE-02 ("superseded") and THR-05 ("D-376 … is retired"). Also history, not rules:
  - AUTO-01's note ("History: D-80 until v1.0…").
  - WD-01's note (20 to 30 minutes promised at 07:52Z).
  - CMD-04's note and CMD-06's "Last used 15 Nov 15:48Z".
  - CMD-07, CMD-08 and CMD-09, which are all inactive and kept as history.

  Replacements:
  > **LANE-02** (coordinator): "One implementation thread and its one review thread are active at a time (D-705). Exceptions in force are listed in `project-state.yaml`."
  >
  > **THR-05** (coordinator): "One review thread per batch handles all its PRs and rounds; it may serve the next batch of the same lane while it passes THR-03."

  Delete CMD-07 to CMD-09. Move CMD-01 to CMD-06 to `control_commands_reference` in the state file, keeping their `meaning` text.
- **S4. Atomic replacement is stated in THR-04 but missing where replacement is triggered.** THR-01 ("replaced when its PRs are merged or when the coordinator judges it unfit"), THR-03 ("If it cannot, it is replaced") and project-instructions rule 1 ("replaced … when it reaches two context compressions") have no "at the next hand-off". No live contradiction exists, but a reader of the project instructions alone, which rank first, could replace a thread mid-round. **Fix:**
  > **THR-01** (coordinator): "A lane thread lives for one batch (its plan and its PRs). It is replaced when its PRs are merged, at its second compression (THR-04) or when it fails a fitness check (THR-03); in every case it first finishes its current step and hands over at the next hand-off, never mid-round."

  Add "at the next hand-off, never mid-round," to project-instructions rule 1.
- **S5. No rule says who may edit the rules file.** In practice the coordinator edits it itself (python, `json default=str`). That matches the autonomy grant, but no rule states it. The skill's default (META-01) treats any ruleset edit as critical and owner-approved. **Proposed**, keeping today's practice:
  > **META-01** (all): "Only the coordinator edits `project-rules.yaml`, `.json` and `project-state.yaml`. A rules edit records a decision that already has a D-number or a message of Colin's, bumps the version and is logged in the pending KB batch. Other threads never edit them; they report a stale rule to the coordinator."

  If Colin wants the skill's stricter default instead, add: "…and a rules edit that is not Colin's own decision waits for his go."
- **S6. WD-01 has no escalation and no pause behaviour.** The coordinator already applies both ("no nudges while paused"), but neither is written down. **Fix:**
  > **WD-01** (coordinator): "While a thread owes a result, the coordinator keeps a check 60 minutes out. When it fires it reads the silent threads and nudges them. After two nudges without progress it replaces the thread at the next hand-off, or for a critical PR tells Colin. No checks fire while paused."
- **S7. CMD-04 "slow down" vs CRIT-03 and MOD-02.** Under "slow down", critical reviews drop to Opus medium (D-702e, Colin's wording), while CRIT-03 requires Opus high for critical review. The skill's governance model warns against tying model quality to pace, because critical review rounds are where a weaker model costs most. **This is Colin's choice:** (a) keep it as written; (b) recommended: under "slow down" non-critical reviews move to medium (they already are) and critical reviews stay on high, so the command only lowers concurrency and pace. Either way, CRIT-03 should say "unless CMD-04 is active" so the two rules stop contradicting.
- **S8. LANE-03 drifts from `.github/lanes.yml`, and labels are not mapped.**
  - `lanes.yml` gives the textprep lane `src/sci2audio/testing/**` (the conformance suites), which LANE-03 omits.
  - LANE-03 says core "needs lane:infra", but `lanes.yml` declares `core` as its own label (`lane:core`), and `infra` covers `.github/**`, `pyproject.toml` and `uv.lock`.
  - "core, app, web and infra are single-threaded" no longer matters under D-705.
  - At 468 characters it is the longest rule.

  **Fix:**
  > **LANE-03** (implementation): "A PR changes only files its lane owns, plus their tests and docs. extraction/voices: extraction, voices, output. layout: layout. textprep: textprep, testing. app/release: app, web, cli. core and infra are shared: a PR touching them is critical and carries lane:infra as the lock as well as lane:core where core changes."

  Add `project_profile.lane_mapping_note` with the same mapping. That clears the script's last A04 warning.
- **S9. Review effort in a reused review thread.** MOD-02 puts non-critical reviews on Opus medium. But a review thread's effort is fixed at start (MOD-03), so the batch D review thread, started on high for D1 (D-704), also reviews the non-critical D2 and D3 on high. That is legitimate but unstated. **Add to MOD-02:** "A review thread that serves a whole batch is started at the effort of the batch's most critical PR."
- **S10. Further `CLAUDE.md` drift** (fix in the same docs PR as M2 to M4):
  - "Goal of v1.0" is history; replace it with one line pointing to the current milestone.
  - The critical list lacks CI and safety mechanisms, which CRIT-01 has.
  - There is no pointer to `rules/project-rules.yaml`, which D-702i asked for. Add: "The machine-readable summary of the active rules is `rules/project-rules.yaml` in the project files."
  - The licence line in the Hard rules omits SSPL. The imported `.claude/rules/licences.md` has it, so there is no conflict; it is just incomplete.
- **S11. Ledgers do not support THR-06 and THR-07.** The implementation ledger's "turns" column holds "~780 lines, 18 files" in the batch D rows. The review ledger shows turns of "~1600" and "~740" for single merge steps. The last review entry (#451 round 1) is a bullet, not a table row. The batch audit cannot judge thread length from these numbers. **Fix:**
  > **THR-06**: "…turns = this thread's turns on that PR or round, counted, not estimated; size goes in the notes column; one table row per entry."
- **S12. KB batch files.**
  - `kb/kb-batch-2026-11-14`, `-15`, `-16` and `-16b-pending.md` are merged into KB main (through D-690) but still carry "pending" in their names. THR-02 tells new threads to read "the newest KB", so these invite double reading. Rename them to `-merged` or move them to `kb/archive/`.
  - The 17 Nov batch ends with "Next free D-number: D-710", but D-710 and D-711 are already assigned. ROLE-05 keeps numbering with the coordinator, so the risk is low, but correct the footer when D-710 and D-711 are added.

## Token savings

The file is 33,681 characters, about 8,400 tokens, and is read by every thread at start and after every compression.

- **`source:` fields:** 5,028 characters (15%). Keep D-numbers and Colin's message ids. Drop `project_memory`, `workflow_export`, `claude_md` and memory-file names as sources: they are summaries of the D-rows, not authorities. This saves about 700 tokens.
- **`control_commands` plus `active_now`:** about 3,600 characters. Move them to the state file and delete CMD-07 to CMD-09 (S3). This saves about 900 tokens from the rules.
- **Duplicates to merge** (about 1,000 tokens). Each pair says the same thing:
  - PR-07 = ROLE-07 (never merge or force-push).
  - REL-07 = PR-08 (port word for word).
  - TST-02 = the end of REV-07 (safety mechanism test).
  - GH-02 and TST-08 into TST-07, with REL-06, giving one flaky-test rule.
  - MRG-04 = THR-08 (after a merge).
  - The second half of REL-03 = CI-05.
  - KB-06 is already in THR-09 and REV-04.
  - REV-01 into ROLE-08, after M4.
  - AUTO-04 is in AUTO-01 ("except roadmap and product scope").
- **Belongs elsewhere:**
  - MOD-01 to MOD-03 → `execution_profile.model_routing`.
  - CODE-01 to CODE-04 restate `CLAUDE.md` Hard rules, which every repo thread already loads. Replace them with one line: "CLAUDE.md Hard rules and the layer contract bind every PR."
  - CI-03, CI-04, CI-07, CI-09 and REL-05 describe workflows rather than thread behaviour; move them to a references section or the release checklist.
  - THR-07 is the coordinator's judgement and is already in ROLE-10.
  - Together about 900 tokens.
- **Long rules:**
  - LANE-03: 468 → about 300 characters (S8).
  - LANE-02: 403 → 120 (S3).
  - CRIT-01: 366 → about 230 ("…the KB's process, contract and architecture documents (not the daily decision-log PR)…").
  - ROLE-04: 338 → about 200 (drop the items that ROLE-05, REV-06 and THR-03 already say).
- **Result:** about 80 rules and about 18,000 characters (about 4,500 tokens), roughly 3,900 tokens less per read. Getting to about 60 rules would mean folding the KB formatting rules (KB-04, KB-05) into a KB-thread brief. That is optional.
- **Biggest single saving outside the file: THR-02.** It says "every new thread first reads the newest KB, plans and decision log". The decision log is 775,583 bytes (about 190,000 tokens) and cannot be read whole. Replace it with:
  > "…reads the newest 20 rows of the decision log, the pending KB batch, the rows its plan or brief cites, and its plan file."

## Mechanical findings

`audit_rules.py` on the live file: **115 errors, 7 warnings, 117 info; exit 1.**

- **A03:** 105 rules without `applies_to`, and the 9 CMD entries with no `rule` text (they use `phrase` and `meaning`). Covered by S1 and S3. The schema difference is expected: control commands are not rules and move to the state file.
- **A06:** `active_now` lives in the ruleset. Covered by M1. There is also no `state_file` pointer (info).
- **A09:** "CI-01 apply reduced release-branch CI to every PR." **False positive.** CI-01 ("…on every PR. Pushes run CI only on main and release/**") does not reduce release CI, and CI-05 carries the critical exception. The pattern trips on "only … release/" plus "every PR". Reword so the linter stays quiet:
  > **CI-01**: "Every PR runs lint and the fast suite on Linux. Push events start CI for main and release/** branches; other branch pushes start none."

  The real release-CI defect is in `CLAUDE.md` (M3), which the script does not read.
- **A04 and A05 warnings:** no `execution_lanes`, `file_ownership_labels`, `model_routing` or `token_economy` blocks. The data exists in LANE-01, LANE-03, GH-03, MOD-01 and MOD-02 but not in the generator's shape. Covered by S8 and Token savings. The scratch copy adds them as `project_profile` and `execution_profile` with the profile "balanced", overridden to `max_concurrent_lanes: 1`.
- **A07:** LANE-02 and THR-05, covered by S3.
- **A08:** 115 rules (S3 and Token savings); LANE-03 is 468 characters (S8).
- **A03 info:** "unexpected key `source`" on every rule. Keep the key; it is how this project traces rules to decisions. Trim it as in Token savings.

After S1, M1 and the three rewordings (scratch copy, not the live file): **0 errors**. The 2 warnings left are the lane mapping note (S8) and 106 rules (Token savings).

Checked and clean, with no finding:
- The round-4 hard stop (REV-02 and AUTO-01's exception agree, with no bypass).
- Force-push (banned everywhere; MRG-03 uses update-branch, which merges).
- Owner approval (ROLE-03 and AUTO-02 use only Colin's own messages).
- The workflows deliver CI-02 and CI-05 (`ci.yml` matrix widens on `ci:full` for PRs into any base).
- The non-critical round cap of 2 is below the critical cap of 4.

## Suggested next step

There is no `governance-config.json`, and the 115 project-specific rules do not fit the generator's catalog, so regenerating would lose the D-number trail. **Apply the fixes by hand in one critical change set, coordinator-approved and logged as one D-number:**

1. **Now, while paused** (project files only, no repo touch):
   - Create `rules/project-state.yaml` as in M1 with `paused: true`.
   - In `project-rules.yaml` 1.4.0: remove `active_now`; add META-01 (S5) and META-02 (M1); replace `authority` (M5); replace REV-01 (M4), PR-05 and REV-03 (M6), LANE-02 and THR-05 (S3), THR-01 (S4), WD-01 (S6), LANE-03 (S8) and CI-01 (Mechanical findings); add the S1 scopes; delete CMD-07 to CMD-09; move CMD-01 to CMD-06 to the state file.
   - Regenerate the JSON twin.
   - Re-run `audit_rules.py` and expect 0 errors.
2. **Project instructions** (Colin pastes them, or the coordinator if it can): the source-of-truth line (M5), the KB critical wording (M4), and "at the next hand-off" in rule 1 (S4).
3. **After "continue"**: one `docs:` PR to sci2audio `CLAUDE.md` with M2, M3, the M4 wording and S10. This is critical (process document), reviewed on Opus high, and Linux CI is enough.
4. **Colin decides:** S7 (does "slow down" also move critical reviews to medium?) and whether META-01 should use the skill's stricter owner-approval default (S5).
5. **Later, optional:** the Token savings merges (version 1.5.0), S11 (ledger columns), S12 (KB file names).
