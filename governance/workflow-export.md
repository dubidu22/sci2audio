# Running a software project with Claude Projects: our workflow

This describes how we run one software project (an open-source desktop app, rewritten from scratch to a 1.0 release candidate in under a week) inside a Claude Project, with one human owner and many Claude threads. It is written so you can copy the setup. Names from our project appear only as examples; replace `<PROJECT>`, `<OWNER>`, `<CODE_REPO>` and `<KB_REPO>` with your own.

Reading time: about 12 minutes.

---

## 1. The idea in one paragraph

One human owns the goals. One Claude, the **coordinator**, runs the project chat: it starts threads, approves plans, decides, merges and keeps a decision log. All real work happens in **threads**, each with one job: build one issue, review one issue's PRs, or write the day's decision log. Every change goes **issue → plan → PR → review in a separate thread → squash merge**. Tests, golden files and byte-for-byte corpus comparisons are the safety net, so the owner can step back without losing control. Everything decided is written down, so a fresh thread (or the owner, a week later) can find out why anything is the way it is.

---

## 2. Roles

| Role | Who | Does | Never does |
|---|---|---|---|
| **Owner** | You (in our project: Colin) | Sets goals, milestones and release themes; approves process rules; does the hand steps a machine can't (listening tests, screen-reader pass, account setup, repo settings) | Has to read every diff (unless he wants to) |
| **Coordinator** | The Claude in the project chat | Splits work into issues and lanes; starts implementation, review and KB threads; approves plans; makes and logs decisions; tells review threads when to merge; reports to the owner one line per decision and per merge | Writes product code itself |
| **Implementation thread** | One Claude thread per issue | Reads the issue and KB, posts a plan, writes code and tests, opens the PR, answers review findings with an exact fix list | Merges its own PR; opens KB PRs; works outside its lane |
| **Review thread** | One Claude thread per issue (fresh, never the author) | Reviews every PR of that issue in rounds, runs the tests and corpus comparisons itself, writes round notes, squash-merges on the coordinator's go | Writes the feature; reviews a critical PR from another issue |
| **KB thread** | One Claude thread per day | Collects the day's decisions and merge records into one decision-log PR in the KB repo | Makes decisions itself |

**Concurrency:** at most **three implementation threads** at once, **one per lane** (a lane is a set of paths only one thread may change at a time; ours were extraction, layout, app/release, with text rules acting as its own lane in practice). Further work waits in the plan's lane order. Review threads and the KB thread don't count against the limit.

**Models:** coordinator on the strongest reasoning model; every new thread (implementation, review, KB) on a strong model at high effort. When the coordinator is unsure (a hard critical decision, conflicting plans, a tricky review) it may run that one thread on the strongest model instead. Critical work gets *more* effort, not less.

---

## 3. Project instructions (copy, then edit)

Paste this into the project's instructions and fill in the placeholders. It is our text, generalised.

```text
Claude acts as senior development manager for <PROJECT>. Save analyses as Docs in the <PROJECT>
folder. Source of truth: knowledge base in <KB_REPO> (docs/kb) and CLAUDE.md in <CODE_REPO>.

Models: the coordinator uses <STRONGEST_MODEL>. All new threads use <STRONG_MODEL> on high effort.
When the coordinator is uncertain about something (a critical decision, a hard review, a
conflicting plan), it may use <STRONGEST_MODEL> on medium or high for that thread instead.

Autonomy until <MILESTONE> (<OWNER>, <DATE>): Claude reviews and merges ALL PRs, including
critical ones, and makes all decisions itself until <MILESTONE> is reached, without waiting for
<OWNER>. <OWNER> is informed in the project chat about every decision on the way (one line per
decision, one line per merge). Testing and reviewing stay strict and the processes below stay in
force.

Critical means: any change to a layer contract, the core dataclasses, the KB, or a golden file,
regardless of label (risk:high also counts). Critical work still gets the full process (plan,
review in a new thread, exact fix lists, issues for anything deferred); the only change is that
Claude approves plans and merges instead of <OWNER>.

Plans: every implementation thread posts a plan before code or tests. For non-critical work, if
Claude has high confidence that the plan is superior to the alternatives, work starts right away;
otherwise, and for all critical work, the plan waits for the coordinator's explicit approval,
which the coordinator gives after weighing the alternatives.

Decisions and merges: every PR is reviewed in a review thread (<STRONG_MODEL>, high) before
merging. The review thread merges on the coordinator's instruction; the authoring thread never
merges. When addressing review feedback, list exactly what is fixed and why; never say "most";
anything deferred gets a GitHub issue. Every decision, including Claude's own, is recorded in the
KB decision log. <OWNER> is always informed in the project chat about every architectural
decision and every merge.

Workflow rules: (1) KB decision-log entries are collected into one KB PR per day, written by one
KB thread and reviewed and merged in one review thread; implementation threads do not open their
own KB PRs. (2) A test that fails twice without a code cause is quarantined the same day (skipped
with a linked GitHub issue); every quarantined test must be fixed before the next release.
(3) At most three implementation threads run at once, one per lane (<LANE_1>, <LANE_2>,
<LANE_3>); further work waits in the plan's lane order. (4) One review thread per issue, reused
for all of that issue's PRs; a critical PR from a different issue always gets a fresh review
thread.
```

If you don't want autonomy yet, delete the "Autonomy" paragraph and change "the coordinator's explicit approval" to "the owner's explicit approval" for critical plans and merges. That is how we started (section 9).

---

## 4. The flow of one change

```
issue (milestone, lane label, risk:high?)
  → implementation thread reads issue + KB + code
  → posts a PLAN (file in plans/, summary in thread)
      non-critical + clearly best → starts at once
      critical or real open choice → waits for approval (decision card, recommended option marked)
  → code + tests on a branch, one lane only
  → PR (title "<area>: <outcome> (#N)", body: what, tests, risk, what's out of scope)
  → coordinator starts / reuses the issue's REVIEW thread
  → review rounds: round notes file, must-fix / should-fix
  → author answers with an exact fix list, pushes fixes
  → review approves once CI is green
  → coordinator says "merge" → review thread squash-merges, pinned to the reviewed head SHA
  → coordinator: one chat line to the owner; decision + merge go into the day's KB batch
  → author and review threads resolved
```

### 4.1 Plans

The first thing an implementation thread posts is a plan, before any code or test (writing tests counts as implementation). Only reading the issue, the KB and existing code comes first. We added this rule after a thread wrote a whole PR without one.

A plan file lives in the shared project folder, `plans/issue<N>-<slug>-plan.md`, and has roughly:

1. **What is true today, measured.** Not "probably": numbers from running the code on the corpus. ("Only 3 of 30 footnote marks are found; the 27 missing are …")
2. **The change**, numbered, naming files and functions.
3. **Tests**: unit, property, corpus, golden changes expected.
4. **What stays the same**, measured where possible ("all English files byte-identical on a local prototype").
5. **PR split**, if any. Split only when the parts can be reviewed, tested and merged on their own; size alone is no reason.
6. **Choices for the decision log**: Q1, Q2 … each with options, the recommended one, and why. The approval ("approved as recommended") turns them into decision-log entries.

### 4.2 What counts as critical

A change is **critical** when it touches any of:

- a **layer contract** (which package may import which, enforced in CI; plugin interfaces),
- the **core data types** every stage shares,
- the **KB** (design docs and decision log),
- a **golden file** (hand-checked truth files, snapshots, regression cases),
- the **packaging / release workflow**,
- or carries the `risk:high` label.

This is decided by what the diff touches, not by the labels: the author sets labels, so a label alone must not decide whether a change gets the stricter path. Critical work always waits for plan approval and always gets a fresh review thread.

---

## 5. Review conventions

- **A separate thread reviews.** The thread that wrote the code never reviews or merges it. One review thread per issue is reused for all of that issue's PRs (it already knows the plan); a critical PR from another issue always gets a fresh one, because a long thread starts trusting its own earlier reading.
- **The reviewer runs things itself**: lint, the fast suite, the browser suite if UI changed, and the corpus comparison (5.1). It merges the main branch locally before judging, because many bugs only appear on the merge.
- **Round notes** go to `plans/review-pr<N>-round<K>.md`:
  - head SHA reviewed, verdict (changes requested / approved),
  - **What I verified** (commands, counts, what was read in full),
  - **Must fix** (M1, M2 …): a defect, with a measured failure case and the fix,
  - **Should fix (or defer with an issue)** (S1 …),
  - optional notes that need no action.
- **The author answers** in `plans/review-pr<N>-round<K>-answer.md` (or in the thread): every finding named as **fixed** (how, which test now fails on the old head), **deferred** (with the new issue link and milestone) or **declined** (with the reason). Never "fixed most of it".
- **Anything deferred becomes a GitHub issue** with a milestone, the same day.
- **Merging:** squash only (we turned off merge commits), pinned to the reviewed head SHA, only with CI green. If the branch is behind, the review thread merges main into it (no force-push), waits for CI, then merges. The author never merges or force-pushes after review starts.

### 5.1 The safety net: golden files and byte-identical corpus runs

This is what lets Claude merge without the owner reading diffs.

- **A test corpus** of real, openly licensed input files (ours: ~10 papers, an EPUB, Markdown and text samples), with a licence table.
- **Hand-checked truth files** per corpus file (headings in order, counts, sentences that must come out verbatim, text that must not appear). Written *before* the code, checked by the owner against the source.
- **Snapshot golden files** of the program's output. Accepted only when the truth tests pass; every later change shows up as a diff that the PR must explain. Changing a golden file makes a PR critical.
- **Byte-identical comparison.** For any change that could affect output, the reviewer runs every corpus file through the pipeline on main and on the branch and compares the bytes. A PR states which files are expected to change; every other file must be identical. ("All 11 English files identical; only the German paper and the German sample change.")
- **Property tests** (e.g. Hypothesis): never crashes on any input, every item ends up in exactly one place, running the text rules twice changes nothing.
- **Planted-failure checks** in review: plant a forbidden import and confirm the layer check breaks; mutate one line and confirm a test catches it.
- **Flaky tests** that fail twice without a code cause are quarantined the same day (a marker, skipped, linked issue); every one is fixed before the next release.

---

## 6. The decision log

Lives in the KB repo (`docs/kb/00-index/decision-log.md`), a table newest first.

**Entry types:** `F-n` = a fact or question the owner stated; `D-n` = a decision; `O-n` = an open question.

**Columns:** ID · date · title · decision (with the question, the alternative not chosen, and the reason) · status · links (issue, PR, plan, related entries).

**Status values:**

- **Decided**: the owner stated or approved it (even a coordinator proposal he said "yes" to). Quote his words with the time.
- **Decided (Claude)**: Claude decided alone under the autonomy rule. Binding until the owner revises it.
- **Proposed**, **Open**, **Superseded** (kept for history; the newer entry names it).

**Example status cells:**

```text
**Decided** (Colin, 13 Nov 14:53 UTC: "all 3 suggestions approved"; Colin informed in the project chat at 2026-11-13 14:53:28 UTC)

Decided (Claude) (coordinator, 14 Nov 01:21 UTC, under D-80; plan approved as recommended; Colin informed in the project chat at 2026-11-14 06:35:31 UTC)
```

**Rules that saved us trouble:**

- **The coordinator assigns every D-number**, so two threads never use the same one.
- **"Owner informed" time = the created-at timestamp of the chat post**, read from the chat itself, not from someone's note. If several decisions were reported in one batched post (the owner was away), they all get that post's time.
- When a decision revises an older one, add a status note on the older row too ("; **partly revised by D-80** (12 Nov): …").
- **One KB PR per day.** Decisions are collected through the day in a pending batch file in the project folder (`kb/kb-batch-<date>-pending.md`), each with its full text, status line and the notes to add on older rows. One KB thread turns the batch into one PR; one review thread checks each row against the owner's actual words and merges it. Before this rule, parallel KB PRs conflicted at the top of the table and had to merge in a chain.
- **KB PR bodies never write "fixes"/"closes" next to a code PR or issue link** ("records decisions of PR #N" instead): GitHub's closing keywords once closed an open code PR that way.
- Each table row has exactly the right number of cells and no raw `|` inside a cell.

---

## 7. Milestones and releases

- The owner sets **themed releases** and their order (ours: weekly, e.g. v1.1 "German reading", v1.2 "better listening", v1.3 "installers", plus "Later"). Each is a GitHub milestone; every issue has one.
- **Release branch strategy:** when the release PRs (version, changelog) are merged, cut `release/X.Y` from that merge commit. New feature work keeps landing on `main` only, and `main` moves to the next dev version (`X.(Y+1).0.dev0`). The tag goes on the release branch. The release-day PR (final changelog date, hand-test results) targets the release branch and is then merged forward into `main` by a PR. Protect `release/*` with the same ruleset as `main`. This way a release waiting for the owner's hand steps never blocks the next milestone.
- **Release gates** a machine can't do stay with the owner and are given to him as one checklist: listening test, screen-reader pass, speed run on real hardware, PyPI trusted-publisher setup, a protected publishing environment with himself as required reviewer, repo rulesets. The tag waits for these.
- **Patch milestone** (v1.0.1) collects bugs found on main during later reviews that are out of scope for the PR at hand.

---

## 8. Pacing and the owner's controls

The coordinator can't see token usage, so the owner steers with three words in the project chat:

| Owner says | Coordinator does |
|---|---|
| **"slow down"** | At most 2 implementation threads; reviews on a lighter setting (strong model medium for critical, a smaller model high for the rest) |
| **"pause all threads"** | Messages every running thread to stop and confirms each one stopped |
| **"continue"** | Back to normal pace |

Threads stop overnight; a nudge from the coordinator restarts them. When the owner comes back after hours away, the coordinator gives **one batched post** listing every decision and merge since he left (that post's timestamp becomes their "informed" time), plus anything waiting on him.

---

## 9. How the owner delegates: the autonomy ladder

We got here in steps, each written into the decision log, and you can stop at any step:

1. **Start:** plans wait for the owner; the owner merges everything. A fresh thread reviews every PR.
2. **Non-critical autonomy:** for non-critical work Claude may decide and merge after review in a separate thread; one chat line per merge so the owner can audit after the fact. Critical work still waits for him. Non-critical plans the coordinator is highly confident in start without waiting.
3. **Decision-log transcripts:** KB entries that only record what the owner already said in chat are merged by Claude after a review thread checks them against his words.
4. **Full autonomy until a milestone:** in our case: *"From now on you will review and merge all PRs and work totally by yourself until v1.0 is reached. Just inform me about all decisions on the way. Be strict with testing, reviewing and keep the current processes."* Later extended to v1.1 with *"keep working until you finished v1.1"*. The definition of critical stays; only who approves changes. Every decision still gets logged as "Decided (Claude)" and reported in one line.

Practical detail: the session's safety checks may block a merge that only another Claude asked for. Our coordinator attaches the owner's original autonomy message to every review thread as standing approval, which clears this.

**What stays the owner's even under full autonomy:** goals, milestones and release themes; anything outside the repo (accounts, repo settings, publishing); hand tests; and the right to revise any "Decided (Claude)" entry at any time.

---

## 10. Setting this up in a new project: checklist

**Repos**

- [ ] A **code repo** with `CLAUDE.md` at the root: hard rules, the layer contract (which package may import which), the "critical" list, PR title format, test rules per area (`.claude/rules/tests.md`), and a lane map (`.github/lanes.yml`).
- [ ] A separate **KB repo** (`docs/kb/`): `00-index/README.md` (start here), `00-index/decision-log.md` (legend from section 6, empty tables), playbooks for the plan and the dev process.
- [ ] Add both repos to the Claude Project (Project settings → repositories) so every thread gets them.
- [ ] GitHub: `main` ruleset (squash only, linear history, a required "CI passed" check with up-to-date branches, no force-push or deletion); later the same for `release/*`.
- [ ] CI: lint, formatter, import-layer check, dependency check, fast tests on 3 OS, browser tests if there is a UI; nightly slow suite.
- [ ] Labels: `lane:<name>`, `risk:high`, `bug`/`feature`/`chore`; milestones for each release.

**Project folder** (shared by every thread)

- [ ] `plans/`: one plan file per issue, review round notes `review-pr<N>-round<K>.md` and answers.
- [ ] `kb/`: the day's pending decision batch.
- [ ] `release/`: release check results.

**First KB PR**

- [ ] The decision log with the legend and your first entries: the roles, the definition of critical, "plan before code", "review in a separate thread", "every decision is logged", the workflow rules (one KB PR a day, quarantine, three lanes, one review thread per issue). Mark them **Decided** with your own words and the date.

**Project memory conventions**

- [ ] One memory file per subject (the project scope, the owner's preferences, each issue's thread status, review checklists that found real bugs), not one per fact.
- [ ] The memory index holds the live state: what's in flight, which thread owns which lane, the next free D-number, what's waiting on the owner.
- [ ] Save anything a fresh thread would otherwise have to ask the owner again, in the turn it's learned. Never store secrets.
- [ ] Keep a "review checks" memory per area: concrete checks that caught real bugs before ("merge main locally before judging", "run every corpus file, not only the two with goldens"). Each new review starts from it.

**First week**

- [ ] Write the corpus and its truth files before the first stage's code.
- [ ] Start with autonomy step 1 (section 9); move up a step when the reviews have earned it.
- [ ] Tell the coordinator your pacing words (section 8).

---

## 11. Lessons that became rules

- A thread that skipped the plan wrote a PR nobody had agreed to → **plan before code or tests**.
- A reply said "fixed most of the points" → **name every fix; defer only with an issue**.
- Seven KB PRs waited in a merge chain → **one KB PR per day**.
- Five flaky tests cost every lane re-runs → **quarantine after two unexplained failures, fix before release**.
- A fixed 400-line PR limit forced pointless splits → **split only when the parts stand alone**.
- A release waiting for hand steps would have stalled the next milestone → **release branch; main moves on**.
- Reused review threads drifted → **one review thread per issue; fresh for a critical PR from another issue**.

---

## 12. Changes on day 6: spend fewer tokens (D-626, D-627)

On the sixth day, close to the weekly usage limit, the owner approved a cheaper way of working. It applies from the next issue started.

**Threads and lanes (D-626)**

- PRs are batched by lane: extraction/voices, layout, textprep, app/release. At most three lane threads run at once.
- A lane thread lives for one batch, meaning its plan and its PRs. The coordinator replaces it when the PRs are merged or when its conversation gets long.
- Every new thread first reads the newest changes in the KB, the plans and the decision log.
- Implementation stays on the strongest model at high effort, because that is where quality is made.

**Reviews (D-626)**

- One review thread per issue batch handles all its PRs and rounds.
- A thread's effort is fixed when it starts. Non-critical reviews run at medium effort, critical ones at high.
- Heavy checks (mutation testing, extra nightly seeds, three-system CI) run only for critical PRs, on the final round. Where possible they move into GitHub workflows started by a label.
- At most two review rounds. Leftovers become issues. Critical PRs may go up to round four, then wait for the owner.

**Decision log and reporting (D-626)**

- KB PRs are no longer reviewed. One long-lived KB thread writes and merges one KB PR per day. The log is the coordinator's own record, and a mistake there is cheap to fix in the next batch.
- The coordinator reports only when the owner asks about progress or when a decision is critical. It no longer sends a chat line for every decision.

**Measuring thread reuse (D-627)**

- Two ledgers in project files, `ledger/implementation.md` and `ledger/review.md`, with one line per PR.
- A fitness check runs before a thread gets a new issue.
- A light audit of a lane's merged diff runs when the lane thread finishes.
- Outsourcing work to another vendor's model was considered and rejected.

**New lessons**

- Usage ran close to the weekly limit → **batch by lane, cap review rounds, and keep heavy checks for critical PRs on the final round**.
- The decision log needed its own review thread every day → **the KB thread merges its own PRs**.
