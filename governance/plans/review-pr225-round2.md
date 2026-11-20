# Review: PR #225, round 2

14 Nov 2026 ~01:30 UTC on head ad383cb (main 2819458 merged in, so #222 and #224 are included).

- F1 fixed: lines for #109 #110 #145 #151 #159 #160 (text rules), #104 and #118 (script-job line), one Development line (#17, #39, #47, #129, D-374, #138 #147 #157 #161 #166, #195, #199, D-68 to D-72, D-80), and (#1), (#2) on the setup lines. My own check over all 71 merged PRs (#1 to #222): each PR's number or one of its title's issue/D numbers appears in CHANGELOG.md; none missing.
- F2 fixed: a line for #222 (#96, #221).
- F3 fixed: build job step "The changelog dates this version" (version from TAG via env, dots escaped). Checked here: today's CHANGELOG fails for v1.0.0; a copy dated 2026-11-20 passes for v1.0.0 and fails for v1.0.1; a heading "1x0x0" does not match (escaping works). Release checklist's first Release item names the dated heading.
- zizmor 1.32.0 (no findings), actionlint 1.7.7 (clean), test_readme passes. Only src change is the version string; no golden file changes.
- **Verdict: approved.** Squash-merge pinned to ad383cb once "CI passed" is green; then create release/1.0 from the merge commit (D-490).

**Merged** 14 Nov 2026 ~01:27 UTC by squash, pinned to ad383cb (all CI checks green): b25f192. Nothing deferred.
Branch `release/1.0` pushed at b25f192 (D-490).
Ruleset for `release/*` (D-491): the session proxy refuses writes to the rulesets API (HTTP 403), so it needs Colin: Settings → Rules → Rulesets → New branch ruleset "release branches", target `release/*`, enforcement Active, rules as the "main" ruleset: restrict deletions, block force pushes, require linear history, require a pull request (0 approvals, squash only), require status check "CI passed" (GitHub Actions) with "branches up to date".
