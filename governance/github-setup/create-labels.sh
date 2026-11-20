#!/usr/bin/env bash
# sci2audio: creates the GitHub labels the ruleset refers to. Safe to run again (--force updates).
# Needs the GitHub CLI, signed in with access to the repository. Run it yourself: threads do not change
# repository settings (ROLE-14).
set -eu
REPO=${1:-'dubidu22/sci2audio'}

gh label create 'lane:core' --repo "$REPO" --color B60205 --description 'Shared core files: critical, requires lane:infra, single-thread lock' --force
gh label create 'lane:extraction' --repo "$REPO" --color 5319E7 --description 'File ownership for the extraction area' --force
gh label create 'lane:layout' --repo "$REPO" --color 5319E7 --description 'File ownership for the layout area' --force
gh label create 'lane:textprep' --repo "$REPO" --color 5319E7 --description 'File ownership for the textprep area' --force
gh label create 'lane:voices' --repo "$REPO" --color 5319E7 --description 'File ownership for the voices area' --force
gh label create 'lane:output' --repo "$REPO" --color 5319E7 --description 'File ownership for the output area' --force
gh label create 'lane:app' --repo "$REPO" --color 5319E7 --description 'File ownership for the app area' --force
gh label create 'lane:web' --repo "$REPO" --color 5319E7 --description 'File ownership for the web area' --force
gh label create 'lane:cli' --repo "$REPO" --color 5319E7 --description 'File ownership for the cli area' --force
gh label create 'lane:infra' --repo "$REPO" --color D93F0B --description 'Cross-cutting/infra changes; the lock for touching core' --force
gh label create 'lane:docs' --repo "$REPO" --color 0E8A16 --description 'Documentation; any lane may edit' --force
gh label create 'risk:high' --repo "$REPO" --color B60205 --description 'Critical change: plan approval, strong-model review, full CI matrix' --force
gh label create 'risk:low' --repo "$REPO" --color C2E0C6 --description 'Routine change within lane ownership' --force
gh label create 'full-ci' --repo "$REPO" --color 1D76DB --description 'Dispatch the full target_platforms matrix on this PR' --force
gh label create 'deferred' --repo "$REPO" --color FBCA04 --description 'Review finding deferred from a PR round' --force
gh label create 'backlog' --repo "$REPO" --color D4C5F9 --description 'Idea cut from an acceptance contract; run specify before building it' --force
gh label create 'flaky-test' --repo "$REPO" --color E99695 --description 'Quarantined test; fix before release' --force

# Execution lanes (one concurrent implementation thread each): extraction/voices, layout, textprep, app/release, web, docs
# Execution lanes are who works; lane:* labels (.github/lanes.yml) are which files a PR may touch. extraction/voices -> lane:extraction, lane:voices, lane:output. layout -> lane:layout. textprep -> lane:textprep (incl. src/sci2audio/testing). app/release -> lane:app, lane:cli (and lane:web when a PR spans both). web -> lane:web (src/sci2audio/web, static, templates, browser tests). docs -> lane:docs (docs/, CLAUDE.md, KB process text). app and web share files often, so LANE-02 keeps them apart unless their PRs touch disjoint files (D-761 B7/B8). lane:core and lane:infra are shared and critical; lane:infra is the lock. (D-765)
