# github-setup/

Files for the owner to apply to the repository. Nothing here takes effect by being in this folder, and no
thread applies it: repository settings are the owner's (`ROLE-14`).

Every file here that has a live twin in `.github/` is a byte-equal copy of it, and `tests/unit/test_lanes.py` fails when one differs: change the live file, then copy it here.

- `create-labels.sh`: creates the lane and risk labels. Run `bash create-labels.sh` (GitHub CLI, signed in).
- `pr_checks.py`, `pr-checks.json`, `pr-checks-workflow.yml`: the pull-request checks a machine can do (title format, no closing keywords in commits, a lane label, file ownership by path, `risk:high` on critical paths, no new markdown file outside `doc_paths`, and a warning for added comments that narrate the change, `PR-05`). Copy the first two to `.github/governance/` and the workflow to `.github/workflows/governance-pr-checks.yml`. Try it locally first: `python3 pr_checks.py --config pr-checks.json --title "cli: add import (#12)" --labels lane:cli --files changed.txt --commits commits.txt`. `pr-check-exemptions.json` goes to `.github/governance/` too: a file that has to break a path check is listed there as `sanctioned` (permanent, with a reason) or `debt` (with a reason and the issue that removes it); nothing else lets a PR past a check (`PR-04`). The format is in the header of `pr_checks.py`. Known gaps, on purpose: the checks stop accidents, not intent. They are only as strong as the branch protection that requires them and the owner review of `.github/governance/`.
- `CODEOWNERS`: add its lines to `.github/CODEOWNERS` and require code-owner review on `main`. This is what makes contract approval and ruleset changes the owner's own review.
- `labeler.yml` and `labeler-workflow.yml`: copy to `.github/labeler.yml` and `.github/workflows/labeler.yml`. CI then sets `risk:high` on PRs that touch `critical_paths`.

## Branch protection on `main`

These rules have no script, because only the repository's settings can enforce them. Set them once; they
replace rule prose that a thread would otherwise have to remember:

- Require a pull request before merging (no direct pushes): `ROLE-06`.
- Block force pushes: `PR-03`, `MRG-01`.
- Require status checks to pass: your CI and `governance pr checks`: `PR-02`, `CI-01`.
- Require review from Code Owners: contract approval and ruleset changes.
