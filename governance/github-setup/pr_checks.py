#!/usr/bin/env python3
"""
Deterministic checks for a pull request, so the rules that a machine can check are not left to prose.

    python3 pr_checks.py --config pr-checks.json --title "<PR title>" --labels "lane:cli,risk:low" \
        --files changed.txt --commits commits.txt [--diff diff.txt] [--exemptions pr-check-exemptions.json] [--open-issues "12,15"] [--json]

    changed.txt   output of `git diff --name-status <base>...<head>` (plain paths, one per line, also work)
    commits.txt   output of `git log --format=%B <base>..<head>`
    diff.txt      output of `git diff <base>...<head>` (optional; needed only for the comment check)

What it checks (rule ids of the generated ruleset):
    title        PR-01   '<area>: <outcome> (#N)'
    commits      PR-01   no closing keyword (Closes #N, Fixes #N, ...) in a commit message
    lane label   LANE-03 the PR carries at least one file-ownership label
    ownership    LANE-03 every changed file that a label owns is owned by one of the PR's labels
                         (a docs label is open to every lane; core files need the lock label)
    critical     CRIT-01 a PR that touches a critical path carries risk:high
    tests        TST-02  deleted test files are listed as a warning for the reviewer
    new docs     PR-05   a markdown file the PR adds lies under one of `doc_paths` (config). Summary, notes
                         and report files nobody asked for fail. Needs `git diff --name-status` input:
                         only files with status A count as new. Not checked when the config has no `doc_paths`
    comments     PR-05   with --diff: an added comment line that tells the history of the change or the
                         conversation (HISTORY_RE: "previously", "now uses", "as requested", "in this PR",
                         ...) fails; one that only matches the broad word list (NARRATION_RE: "no longer",
                         "moved to", ...) or carries a TODO without an issue number is a warning for the
                         reviewer. HISTORY_RE is strict enough that the tree has no false match
                         (tests/unit/test_narrating_comments.py scans it with the same list)

Exemptions. A file that may break one of the path checks (ownership, unowned, lock, critical, tests, docs) is
listed in pr-check-exemptions.json next to the config, never in a private allowlist and never by weakening
a glob. Each entry says what it is:

    [{"check": "ownership", "paths": ["src/core/legacy/**"], "kind": "debt", "issue": 31,
      "reason": "CLI still imports the legacy loader; issue 31 moves it"},
     {"check": "unowned", "paths": ["LICENSE"], "kind": "sanctioned",
      "reason": "Licence text belongs to no lane and changes only with the owner"}]

    sanctioned   a permanent, legitimate case
    debt         a violation that is tracked for removal; it names the issue that removes it

Every exemption that was used is printed, so it stays visible. With --open-issues (the numbers of the
open issues), a debt exemption whose issue is no longer open fails: the issue is closed, so the
exemption goes. A malformed exemptions file is a config error (exit 2), not a silent pass.

Known gaps, on purpose. These checks stop accidents, not intent. They read the labels and file list
they are given, so they are only as good as the workflow that passes them; a thread with write access to
the workflow, the config or the exemptions file can change what is checked, which is why those files need
the owner's review (CODEOWNERS) and the check must be required in branch protection. Ownership is by path
only: a file moved into another lane's folder is owned by that lane from then on. The comment check is a
word list over added lines that start with a comment marker: it misses trailing comments, docstrings (the
test above scans those) and narration in other words, above all a comment that says what the code does
instead of why; that stays the reviewer's. A sanctioned case goes in the exemptions file (check "comments").
The new-docs check sees markdown only; a notes file with another extension is the reviewer's to catch.

A pull request that only changes governance files (the workspace folder) is exempt from the title, label
and ownership checks: decision-log and contract pull requests follow other rules.

Exit code: 0 no failure, 1 at least one failure, 2 bad arguments or config. Reads only; standard library only.
The config is written by scaffold_workspace.py --github from governance-config.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TITLE_RE = re.compile(r"^[^\s:][^:]*: \S.* \(#\d+\)$")
CLOSING_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+(?:[\w.-]+/[\w.-]+)?#\d+", re.IGNORECASE)
EXEMPTABLE = ("ownership", "unowned", "lock", "critical", "tests", "docs", "comments")
DOC_FILE_RE = re.compile(r"\.(md|markdown|mdx)$", re.IGNORECASE)
PROSE_FILE_RE = re.compile(r"\.(md|markdown|mdx|rst|txt|adoc)$", re.IGNORECASE)
COMMENT_RE = re.compile(r"^\s*(?:#(?!!)|//|/\*|\*(?!/)|--\s|<!--|;;)\s*(.*)$")
# phrases that describe the change or the conversation instead of the code
NARRATION_RE = re.compile(
    r"\b(?:previously|used to\b|no longer|as requested|as discussed|per (?:the )?(?:review|feedback|request)|"
    r"changed (?:from|to)\b|was changed|now uses?\b|now we\b|we now\b|refactored|rewritten|"
    r"(?:added|removed|updated|fixed|moved|renamed) (?:this|the|to|in|by|for)\b|new implementation|old implementation|"
    r"review round|reviewer (?:asked|wanted|said))", re.IGNORECASE)
# the history of the change or of the conversation: precise enough to fail on (D-891, one step up META-03)
HISTORY_RE = re.compile(
    r"\b(?:previously|as (?:requested|discussed|agreed)|per (?:the )?(?:review|feedback|request)\b(?! rounds?\b)|"
    r"was changed|changed (?:from|to)\b|now uses?\b|now we\b|we now\b|"
    r"(?:the )?(?:old|new) (?:implementation|code|approach|behaviou?r)\b|"
    r"in this (?:PR|commit|change)\b|(?:before|after) this (?:PR|commit|change)\b|"
    r"this (?:PR|commit) (?:adds|removes|changes|fixes|moves|replaces)\b|"
    r"reviewer (?:asked|wanted|said|found)\b|"
    r"(?:ended|went away|was dropped|were dropped) (?:with|in) the move\b|"
    r"(?:was|were) (?:added|removed|renamed|moved|replaced|rewritten) (?:in|by|for|when) (?:#\d|PR|the review|D-\d)|"
    r"used to (?:be|call|use|read|write|return|live|sit|run)\b)", re.IGNORECASE)
TODO_RE = re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b")
ISSUE_REF_RE = re.compile(r"#\d+|/issues/\d+")
MAX_LISTED = 12
MIN_REASON = 20

TEST_FILE_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|[._-](test|spec)\.[A-Za-z]+$|_test\.[A-Za-z]+$")


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Path glob from the repository root: `**` crosses folders, `*` and `?` stay inside one path segment."""
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, globs: list[str]) -> bool:
    return any(glob_to_regex(g).match(path) for g in globs)


def read_changes(text: str) -> list[tuple[str, str]]:
    """(status, path) per changed file. Renames count as the new path; plain path lines get status 'M'."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and re.fullmatch(r"[ACDMRTUXB]\d*", parts[0]):
            out.append((parts[0][0], parts[-1].strip()))
        else:
            out.append(("M", line.strip()))
    return out


def exemption_errors(entries: object) -> list[str]:
    """What is wrong with an exemptions list; empty when it is usable."""
    if not isinstance(entries, list):
        return ["the exemptions file must hold a JSON list"]
    out: list[str] = []
    for i, e in enumerate(entries, 1):
        where = f"exemption {i}"
        if not isinstance(e, dict):
            out.append(f"{where}: must be an object")
            continue
        unknown = sorted(set(e) - {"check", "paths", "kind", "reason", "issue"})
        if unknown:
            out.append(f"{where}: unknown key(s) {', '.join(unknown)}")
        if e.get("check") not in EXEMPTABLE:
            out.append(f"{where}: `check` must be one of {', '.join(EXEMPTABLE)}")
        paths = e.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(g, str) and g.strip() for g in paths):
            out.append(f"{where}: `paths` must be a non-empty list of path globs")
        elif any(g.strip() in ("*", "**", "**/*") or g.startswith("/") or ".." in g.split("/") for g in paths):
            out.append(f"{where}: `paths` must name files or folders from the repository root, not everything")
        if e.get("kind") not in ("sanctioned", "debt"):
            out.append(f"{where}: `kind` must be sanctioned or debt")
        reason = e.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON:
            out.append(f"{where}: `reason` must say why in at least {MIN_REASON} characters")
        issue = e.get("issue")
        if e.get("kind") == "debt" and (isinstance(issue, bool) or not isinstance(issue, int) or issue < 1):
            out.append(f"{where}: a debt exemption names the `issue` (a number) that removes it")
        if e.get("kind") == "sanctioned" and "issue" in e:
            out.append(f"{where}: a sanctioned exemption is permanent and names no `issue`; use kind debt")
    return out


def comment_notes(diff: str, skip: list[str]) -> list[tuple[str, bool]]:
    """(`path:line: text`, tells history) for added comment lines that narrate the change or hold a TODO
    without an issue; the flag is true for a HISTORY_RE match, which fails the check.

    Reads a unified diff. Prose files and paths matching `skip` are left out. Only lines that start with a
    comment marker are seen; a trailing comment after code is not.
    """
    out: list[tuple[str, bool]] = []
    path, line = "", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            name = raw[4:].strip()
            path = "" if name == "/dev/null" else (name[2:] if name.startswith("b/") else name)
            continue
        if raw.startswith("--- "):
            continue
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
        if m:
            line = int(m.group(1))
            continue
        if not path or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            c = COMMENT_RE.match(raw[1:])
            if c and not PROSE_FILE_RE.search(path) and not matches(path, skip):
                text = c.group(1).strip()
                if HISTORY_RE.search(text):
                    out.append((f"{path}:{line}: {text[:90]}", True))
                elif NARRATION_RE.search(text):
                    out.append((f"{path}:{line}: {text[:90]}", False))
                elif TODO_RE.search(text) and not ISSUE_REF_RE.search(text):
                    out.append((f"{path}:{line}: {text[:90]} (no issue number)", False))
            line += 1
        elif not raw.startswith("-"):
            line += 1
    return out


def run_checks(cfg: dict, title: str, labels: list[str], changes: list[tuple[str, str]], commits: str,
               exemptions: list[dict] | None = None, open_issues: set[int] | None = None, diff: str | None = None) -> list[dict]:
    results: list[dict] = []
    used: list[tuple[dict, str]] = []

    def exempt(check: str, path: str) -> bool:
        for e in exemptions or []:
            if e["check"] == check and matches(path, e["paths"]):
                used.append((e, path))
                return True
        return False

    def add(check: str, status: str, message: str) -> None:
        results.append({"check": check, "status": status, "message": message})

    paths = [p for _, p in changes]
    governance = cfg.get("governance_paths") or []
    governance_only = bool(paths) and bool(governance) and all(matches(p, governance) for p in paths)
    ownership = cfg.get("ownership_labels") or []
    label_paths: dict[str, list[str]] = cfg.get("label_paths") or {}
    mine = [l for l in labels if l in ownership]

    # commits: never exempt, a closing keyword closes an issue whatever the pull request is about
    hits = sorted({m.group(0) for m in CLOSING_RE.finditer(commits)})
    if hits:
        add("commits", "FAIL", f"closing keyword in a commit message ({', '.join(hits)}); closing keywords belong in the PR body only (PR-01)")
    else:
        add("commits", "ok", "no closing keyword in commit messages")

    if governance_only:
        add("scope", "ok", "only governance files changed: title, lane label and ownership checks do not apply")
    else:
        if TITLE_RE.match(title.strip()):
            add("title", "ok", "title has the form '<area>: <outcome> (#N)'")
        else:
            add("title", "FAIL", f"title '{title.strip()}' does not have the form '<area>: <outcome> (#N)' (PR-01)")

        if ownership:
            if mine:
                add("lane label", "ok", f"file-ownership label(s): {', '.join(mine)}")
            else:
                add("lane label", "FAIL", f"the PR carries none of the file-ownership labels ({', '.join(ownership)}) (LANE-03)")

        if label_paths:
            open_labels = [l for l in cfg.get("open_labels") or [] if l in label_paths]
            lock, locked = cfg.get("lock_label") or "", cfg.get("locked_label") or ""
            foreign, unowned, unlocked = [], [], []
            for path in paths:
                if governance and matches(path, governance):
                    continue
                owners = [l for l, globs in label_paths.items() if matches(path, globs)]
                if not owners:
                    if not exempt("unowned", path):
                        unowned.append(path)
                    continue
                if lock and locked and locked in owners and lock in ownership and lock not in labels and not exempt("lock", path):
                    unlocked.append(path)
                if not (set(owners) & set(mine)) and not (set(owners) & set(open_labels)) and not exempt("ownership", path):
                    foreign.append(f"{path} ({', '.join(owners)})")
            if foreign:
                add("ownership", "FAIL", f"files outside the PR's labels ({', '.join(mine) or 'none'}): {'; '.join(foreign)} (LANE-03)")
            else:
                add("ownership", "ok", "every owned file belongs to one of the PR's labels")
            if unlocked:
                add("lock", "FAIL", f"files owned by {locked} changed without the {lock} label: {', '.join(unlocked)} (LANE-03)")
            if unowned:
                add("unowned", "WARN", f"files no label owns (one PR at a time, with plan approval): {', '.join(unowned)}")

    critical = [p for p in paths if matches(p, cfg.get("critical_paths") or [])]
    if critical and "risk:high" not in labels:
        critical = [p for p in critical if not exempt("critical", p)]
    if critical:
        if "risk:high" in labels:
            add("critical", "ok", f"critical paths touched and risk:high is set: {', '.join(critical)}")
        else:
            add("critical", "FAIL", f"critical paths touched without the risk:high label: {', '.join(critical)} (CRIT-01)")

    deleted = [p for status, p in changes if status == "D" and TEST_FILE_RE.search(p) and not exempt("tests", p)]
    if deleted:
        add("tests", "WARN", f"test files deleted: {', '.join(deleted)}. The reviewer confirms none was removed to turn CI green (TST-02)")

    if isinstance(cfg.get("doc_paths"), list):
        stray = [p for status, p in changes if status == "A" and DOC_FILE_RE.search(p)
                 and not matches(p, cfg["doc_paths"]) and not (governance and matches(p, governance)) and not exempt("docs", p)]
        if stray:
            add("new docs", "FAIL", f"new markdown file(s) outside the documentation paths ({', '.join(cfg['doc_paths']) or 'none set'}): "
                f"{', '.join(stray)}. Reports and notes go in the PR body or the ledger; a document the plan names goes "
                "under a documentation path (PR-05)")
        else:
            add("new docs", "ok", "no new markdown file outside the documentation paths")

    if diff is not None:
        notes = [(n, history) for n, history in comment_notes(diff, governance) if not exempt("comments", n.split(":", 1)[0])]
        history = [n for n, h in notes if h]
        broad = [n for n, h in notes if not h]

        def listed(items: list[str]) -> str:
            more = f" (and {len(items) - MAX_LISTED} more)" if len(items) > MAX_LISTED else ""
            return "; ".join(items[:MAX_LISTED]) + more
        if history:
            add("comments", "FAIL", "added comments tell the history of the change or the conversation, not why the code is "
                f"as it is: {listed(history)}. Say why, or drop the comment (PR-05)")
        if broad:
            add("comments", "WARN", "added comments that may narrate the change instead of saying why the code is as it is: "
                + listed(broad) + ". The reviewer decides (PR-05)")
        if not notes:
            add("comments", "ok", "no added comment matches the narration word lists")

    seen: set[tuple[int, str]] = set()
    for e, path in used:
        if (id(e), path) in seen:
            continue
        seen.add((id(e), path))
        if e["kind"] == "debt":
            add("exemption", "WARN", f"{path} is exempt from the {e['check']} check as debt, to be removed by #{e['issue']}: {e['reason'].strip()}")
        else:
            add("exemption", "ok", f"{path} is exempt from the {e['check']} check (sanctioned): {e['reason'].strip()}")
    if open_issues is not None:
        stale = sorted({e["issue"] for e in exemptions or [] if e["kind"] == "debt" and e["issue"] not in open_issues})
        if stale:
            add("exemption debt", "FAIL", "debt exemption(s) whose issue is not open: "
                + ", ".join(f"#{n}" for n in stale) + ". The issue is closed, so remove the exemption (or reopen the issue)")
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic pull-request checks for a governed repository")
    ap.add_argument("--config", type=Path, required=True, help="pr-checks.json written by scaffold_workspace.py --github")
    ap.add_argument("--title", required=True)
    ap.add_argument("--labels", default="", help="comma-separated labels on the pull request")
    ap.add_argument("--files", type=Path, required=True, help="file with `git diff --name-status` output")
    ap.add_argument("--commits", type=Path, required=True, help="file with the commit messages of the pull request")
    ap.add_argument("--diff", type=Path, help="file with `git diff <base>...<head>` output; turns on the comment check")
    ap.add_argument("--exemptions", type=Path, help="exemptions file (default: pr-check-exemptions.json next to the config, if it exists)")
    ap.add_argument("--open-issues", help="comma-separated numbers of the open issues; a debt exemption whose issue is not among them fails")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    exemptions: list[dict] = []
    open_issues: set[int] | None = None
    try:
        if args.open_issues is not None:
            open_issues = {int(n.strip().lstrip("#")) for n in args.open_issues.split(",") if n.strip()}
        ex_path = args.exemptions or args.config.with_name("pr-check-exemptions.json")
        if args.exemptions or ex_path.exists():
            exemptions = json.loads(ex_path.read_text(encoding="utf-8"))
            wrong = exemption_errors(exemptions)
            if wrong:
                print(f"error: {ex_path}:\n  " + "\n  ".join(wrong), file=sys.stderr)
                return 2
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        changes = read_changes(args.files.read_text(encoding="utf-8"))
        commits = args.commits.read_text(encoding="utf-8")
        diff = args.diff.read_text(encoding="utf-8", errors="replace") if args.diff else None
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(cfg, dict):
        print("error: the config must be a JSON object", file=sys.stderr)
        return 2
    labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    results = run_checks(cfg, args.title, labels, changes, commits, exemptions, open_issues, diff)
    failed = [r for r in results if r["status"] == "FAIL"]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['status']:<4} {r['check']}: {r['message']}")
        print(f"\n{len(failed)} failure(s)." if failed else "\nAll checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
