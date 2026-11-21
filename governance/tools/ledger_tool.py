#!/usr/bin/env python3
"""
Read the ledger: one small file per PR and per review round (ledger/README.md).

    python3 ledger_tool.py table [--ledger DIR]   # PRs and rounds as markdown tables
    python3 ledger_tool.py stats [--ledger DIR]   # rounds per PR, compactions per PR, PRs per thread
    python3 ledger_tool.py check [--ledger DIR]   # entries with missing or malformed fields (exit 1 if any)
    python3 ledger_tool.py gate <PR number> [--head SHA]
                                                  # may this PR be merged? exit 0 only if the entries say yes (MRG-01),
                                                  # or the owner's one-off override for exactly this head is recorded
    python3 ledger_tool.py status                 # what is open now, a few lines, PRs by number (ROLE-17)
    python3 ledger_tool.py triage                 # what was left behind and has no decision yet; exit 1 while anything is
                                                  # open. Run before a new batch is composed (THR-16)
    python3 ledger_tool.py flags                  # one line per thing an audit should judge, from the entries alone (ROLE-15)

The ledger directory defaults to `../ledger` next to this script's folder (the
scaffolded `tools/`), or `./ledger`. This tool only reads. Entries are flat
`key: value` files, so it needs nothing beyond the standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PR_KEYS = ("pr", "opened", "thread", "lane", "labels", "critical", "compactions")
ROUND_KEYS = ("pr", "round", "date", "thread", "head", "verdict", "must_fix", "should_fix", "report")
REVERT_KEYS = ("pr", "date", "by", "reason")
OVERRIDE_KEYS = ("pr", "date", "by", "head", "reason")
DEFERRED_KEYS = ("pr", "date", "what", "decision")
DECISIONS = ("open", "planned", "postponed", "dropped")
# first word of a worker thread's report (THR-15); the ones in OPEN_HANDBACKS stop a merge until cleared
HANDBACKS = ("done", "question", "blocked", "review", "handoff")
OPEN_HANDBACKS = ("question", "blocked", "review")
MIN_REASON = 20
INT_KEYS = {"pr", "round", "compactions", "must_fix", "should_fix"}


def read_entry(path: Path) -> dict[str, str]:
    """Flat `key: value` lines; a '#' outside quotes starts a comment."""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line, quote = [], ""
        for i, ch in enumerate(raw):
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
                break
            line.append(ch)
        text = "".join(line).strip()
        m = re.match(r"([A-Za-z_][\w-]*):\s*(.*)$", text)
        if m:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[m.group(1)] = v
    return out


def load(ledger: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    prs = [dict(read_entry(p), _file=p.name) for p in sorted((ledger / "prs").glob("*.yaml"))]
    rounds = [dict(read_entry(p), _file=p.name) for p in sorted((ledger / "rounds").glob("*.yaml"))]
    return prs, rounds


def load_reverts(ledger: Path) -> list[dict[str, str]]:
    folder = ledger / "reverts"
    return [dict(read_entry(p), _file=p.name) for p in sorted(folder.glob("*.yaml"))] if folder.is_dir() else []


def load_overrides(ledger: Path) -> list[dict[str, str]]:
    folder = ledger / "overrides"
    return [dict(read_entry(p), _file=p.name) for p in sorted(folder.glob("*.yaml"))] if folder.is_dir() else []


def load_deferred(ledger: Path) -> tuple[list[dict[str, str]], str]:
    """(entries of deferred/, the date from deferred/since.txt or '')."""
    folder = ledger / "deferred"
    if not folder.is_dir():
        return [], ""
    since = ""
    marker = folder / "since.txt"
    if marker.is_file():
        m = re.search(r"^\d{4}-\d{2}-\d{2}$", marker.read_text(encoding="utf-8"), re.MULTILINE)
        since = m.group(0) if m else ""
    return [dict(read_entry(p), _file=p.name) for p in sorted(folder.glob("*.yaml"))], since


def deferred_problems(e: dict[str, str]) -> list[str]:
    out = [f"`{k}` is missing" for k in DEFERRED_KEYS if not e.get(k)]
    if e.get("pr") and not re.fullmatch(r"\d+", e["pr"]):
        out.append(f"`pr` must be a whole number, got '{e['pr']}'")
    decision = e.get("decision", "")
    if decision and decision not in DECISIONS:
        out.append(f"`decision` must be one of {', '.join(DECISIONS)}, got '{decision}'")
    if decision == "planned" and not re.fullmatch(r"#?\d+", e.get("issue", "")):
        out.append("a planned item names the `issue` (a number) that carries it")
    if decision in ("postponed", "dropped") and len(e.get("reason", "").strip()) < MIN_REASON:
        out.append(f"a {decision} item says why in `reason` (at least {MIN_REASON} characters)")
    if decision == "postponed" and not e.get("until"):
        out.append("a postponed item says `until` when (a milestone, a date or an event)")
    if decision == "dropped" and "owner" not in e.get("by", "").lower():
        out.append("dropping an item is the owner's call: `by` names the owner and where they said it")
    return out


def handback_problems(e: dict[str, str]) -> list[str]:
    hb = e.get("handback", "")
    if not hb:
        return []
    if hb not in HANDBACKS:
        return [f"`handback` must be one of {', '.join(HANDBACKS)}, got '{hb}'"]
    if hb in ("question", "blocked") and len(e.get("recommended", "").strip()) < 10:
        return [f"a `{hb}` hand-back carries `recommended`: the one next action the thread proposes"]
    return []


def triage(rounds: list[dict[str, str]], deferred: list[dict[str, str]], since: str) -> tuple[list[str], list[str]]:
    """(lines that still need a decision, lines that are settled)."""
    todo: list[str] = []
    settled: list[str] = []
    per_pr: dict[str, int] = {}
    for e in deferred:
        wrong = deferred_problems(e)
        per_pr[e.get("pr", "")] = per_pr.get(e.get("pr", ""), 0) + 1
        label = f"deferred/{e['_file']} (PR #{e.get('pr', '?')}): {e.get('what', '').strip() or '(no text)'}"
        if wrong:
            todo.append(f"{label}: " + "; ".join(wrong))
        elif e["decision"] == "open":
            todo.append(f"{label}: no decision yet. Plan it (issue), postpone it (reason, until) or ask the owner to drop it")
        else:
            how = {"planned": f"planned in #{e.get('issue', '').lstrip('#')}", "postponed": f"postponed until {e.get('until', '')}",
                   "dropped": f"dropped by {e.get('by', '')}"}[e["decision"]]
            settled.append(f"{label}: {how}")
    for r in sorted((r for r in rounds if r.get("merged")), key=lambda r: num(r.get("pr"))):
        left = num(r.get("should_fix"))
        if left and (not since or r.get("date", "") >= since) and per_pr.get(r.get("pr", ""), 0) < left:
            have = per_pr.get(r.get("pr", ""), 0)
            todo.append(f"PR #{r.get('pr')} was merged with {left} should-fix finding(s) open, {have} recorded in deferred/: "
                        f"write one entry per finding from {r.get('report') or 'the round report'}")
    return todo, settled


def flags(prs: list[dict[str, str]], rounds: list[dict[str, str]], reverts: list[dict[str, str]],
          overrides: list[dict[str, str]], deferred: list[dict[str, str]], since: str) -> list[str]:
    """One line per thing an audit should judge. Derived from the entries; nobody writes a flag by hand."""
    out: list[str] = []
    per_pr = {e.get("pr", ""): len([r for r in rounds if r.get("pr") == e.get("pr")]) for e in prs}
    out += [f"flag: rounds | PR #{p} took {n} review rounds" for p, n in sorted(per_pr.items(), key=lambda kv: num(kv[0])) if n >= 3]
    out += [f"flag: compactions | PR #{e.get('pr')} was compacted {e.get('compactions')} times while in work"
            for e in prs if num(e.get("compactions")) >= 2]
    seen: dict[str, list[str]] = {}
    for r in sorted(rounds, key=lambda r: (num(r.get("pr")), num(r.get("round")))):
        for k in kinds_of(r):
            if r.get("pr", "?") not in seen.setdefault(k, []):
                seen[k].append(r.get("pr", "?"))
    out += [f"flag: repeated-kind | {k} in {', '.join('#' + p for p in v)}" for k, v in sorted(seen.items()) if len(v) > 1]
    out += [f"flag: regressed | {kind} claimed fixed by #{pr}, back in {', '.join('#' + p for p in back)}"
            for kind, pr, standing, back in fix_claims(prs, rounds) if standing == "regressed"]
    merged = {r.get("pr") for r in rounds if r.get("merged")}
    out += [f"flag: revert | PR #{e.get('pr')} was reverted: {e.get('reason', '').strip()}"
            for e in sorted(reverts, key=lambda e: num(e.get("pr"))) if e.get("pr") in merged]
    out += [f"flag: override | PR #{o.get('pr')} was merged on an owner override: {o.get('reason', '').strip()}"
            for o in sorted(overrides, key=lambda o: num(o.get("pr")))]
    out += [f"flag: handback | PR #{e.get('pr')} handed back `{e['handback']}`: {e.get('recommended', '').strip() or '(no recommendation)'}"
            for e in sorted(prs, key=lambda e: num(e.get("pr"))) if e.get("handback") in OPEN_HANDBACKS]
    todo, _ = triage(rounds, deferred, since)
    out += [f"flag: untriaged | {line}" for line in todo]
    return out


def seam_status(ledger: Path, rounds: list[dict[str, str]]) -> tuple[bool, str] | None:
    """(due, one line) for the seam audit, or None when the project has no seam groups.

    Reads `seam_groups` and `seam_audit_every_prs` from governance-config.json next to the ledger. Counts
    merge rounds dated after the newest ledger/audits/seam-<date>.md; nobody keeps the count by hand.
    """
    try:
        cfg = json.loads((ledger.parent / "governance-config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(cfg, dict) or not cfg.get("seam_groups"):
        return None
    every = cfg.get("seam_audit_every_prs")
    every = every if isinstance(every, int) and not isinstance(every, bool) and every > 0 else 15
    dates = sorted(m.group(1) for p in (ledger / "audits").glob("seam-*.md")
                   if (m := re.fullmatch(r"seam-(\d{4}-\d{2}-\d{2})(-\d+)?\.md", p.name))) if (ledger / "audits").is_dir() else []
    last = dates[-1] if dates else ""
    merged = len({r.get("pr") for r in rounds if r.get("merged") and r.get("date", "") > last})
    since = f"since the seam audit of {last}" if last else "and no seam audit has run yet"
    if merged >= every:
        return True, (f"{merged} PRs merged {since} (due every {every}): start a fresh read-only session with the output of "
                      "tools/seam_audit.py brief (ROLE-16)")
    return False, f"{merged} of {every} PRs merged {since}"


def kinds_of(entry: dict[str, str], key: str = "kinds") -> list[str]:
    """Finding kinds named in an entry: `kinds: timer-workaround, missing-test` (rounds), `fixes_kinds: ...` (PRs)."""
    return [k.strip().lower() for k in entry.get(key, "").split(",") if k.strip()]


def same_head(a: str, b: str) -> bool:
    """Two commit SHAs name the same commit: equal, or one is a prefix of the other (7 characters or more)."""
    a, b = a.strip().lower(), b.strip().lower()
    return bool(a) and bool(b) and min(len(a), len(b)) >= 7 and (a.startswith(b) or b.startswith(a))


def override_problems(e: dict[str, str]) -> list[str]:
    out = [f"`{k}` is missing" for k in OVERRIDE_KEYS if not e.get(k)]
    if e.get("pr") and not re.fullmatch(r"\d+", e["pr"]):
        out.append(f"`pr` must be a whole number, got '{e['pr']}'")
    if e.get("head") and not re.fullmatch(r"[0-9a-fA-F]{7,40}", e["head"]):
        out.append("`head` must be the commit SHA the override is for (7 to 40 hex characters)")
    if e.get("reason") and len(e["reason"].strip()) < MIN_REASON:
        out.append(f"`reason` must say why in at least {MIN_REASON} characters")
    return out


def fix_claims(prs: list[dict[str, str]], rounds: list[dict[str, str]]) -> list[tuple[str, str, str, list[str]]]:
    """(kind, claiming PR, standing, PRs where it came back) for every `fixes_kinds` claim.

    standing: pending (the claiming PR is not merged), holding (merged, the kind has not come up since) or
    regressed (a round of another PR, dated after the claiming PR's merge round, names the kind again;
    on the same date the higher PR number counts as later). The standing is derived, never written by hand.
    """
    out = []
    for e in sorted(prs, key=lambda e: num(e.get("pr"))):
        pr = e.get("pr", "")
        merge_round = next((r for r in rounds if r.get("pr") == pr and r.get("merged")), None)
        for kind in kinds_of(e, "fixes_kinds"):
            if merge_round is None:
                out.append((kind, pr, "pending", []))
                continue
            when = (merge_round.get("date", ""), num(pr))
            back = sorted({r.get("pr", "") for r in rounds if r.get("pr") != pr and kind in kinds_of(r)
                           and (r.get("date", ""), num(r.get("pr"))) > when}, key=num)
            out.append((kind, pr, "regressed" if back else "holding", back))
    return out


def gate(pr: str, prs: list[dict[str, str]], rounds: list[dict[str, str]],
         overrides: list[dict[str, str]] | None = None, head: str = "") -> tuple[bool, list[str]]:
    """Whether the ledger entries allow PR `pr` to be merged, and why or why not.

    An owner override (overrides/pr-N.yaml) lets a PR through that the entries would stop, once: it holds
    for exactly the head it names. That head must be the head of the latest recorded round or, when no
    round is recorded, the head given with --head. A PR that is already merged is never let through.
    """
    ok, reasons = _gate(pr, prs, rounds)
    if ok:
        return ok, reasons
    mine = [o for o in overrides or [] if o.get("pr") == pr]
    if not mine:
        return ok, reasons
    if any(r.startswith("already merged") for r in reasons):
        return False, reasons + ["an owner override is recorded, but the PR is already merged; an override is used once"]
    o = mine[-1]
    wrong = override_problems(o)
    if wrong:
        return False, reasons + [f"overrides/{o['_file']} does not count: " + "; ".join(wrong)]
    last = sorted((r for r in rounds if r.get("pr") == pr), key=lambda r: num(r.get("round")))
    current = last[-1].get("head", "") if last else head
    if not current:
        return False, reasons + [f"overrides/{o['_file']} names head {o['head']}, but no round is recorded to compare it with: "
                                 "pass the PR's current head with --head"]
    if not same_head(o["head"], current):
        return False, reasons + [f"overrides/{o['_file']} is for head {o['head']}, the PR is now at {current}: "
                                 "the override does not carry over to a changed PR, the owner decides again"]
    return True, [f"OWNER OVERRIDE by {o['by']} on {o['date']} for head {o['head']}: {o['reason'].strip()}",
                  "The entries alone would stop this merge:", *[f"  {r}" for r in reasons],
                  "Merge go comes from the owner only, for this head only; required CI must still be green. "
                  "The override is counted in `stats`."]


def _gate(pr: str, prs: list[dict[str, str]], rounds: list[dict[str, str]]) -> tuple[bool, list[str]]:
    mine = sorted((r for r in rounds if r.get("pr") == pr), key=lambda r: num(r.get("round")))
    reasons: list[str] = []
    if not any(e.get("pr") == pr for e in prs):
        reasons.append(f"no prs/pr-{pr}.yaml: the implementation thread has not written the PR's ledger entry")
    if not mine:
        reasons.append("no review round is recorded")
        return False, reasons
    first = next((r for r in mine if r.get("round") == "1"), None)
    if first is None or first.get("critical") not in ("yes", "no"):
        reasons.append("round 1 does not record the reviewer's `critical: yes|no` (CRIT-03)")
    last = mine[-1]
    mine_entry = next((e for e in prs if e.get("pr") == pr), {})
    if mine_entry.get("handback") in OPEN_HANDBACKS:
        reasons.append(f"the implementation thread handed back `{mine_entry['handback']}` (THR-15): "
                       f"{mine_entry.get('recommended', '').strip() or 'no recommendation recorded'}. Settle it, then the thread "
                       "sets `handback: done`")
    if last.get("merged"):
        reasons.append(f"already merged ({last['merged']})")
    if not re.fullmatch(r"\d+", last.get("must_fix", "")):
        reasons.append(f"round {last.get('round')} does not say how many must-fix findings are open")
    elif int(last["must_fix"]) != 0:
        reasons.append(f"round {last.get('round')} has {last['must_fix']} open must-fix finding(s)")
    if last.get("verdict") != "approved":
        reasons.append(f"round {last.get('round')} verdict is '{last.get('verdict', '')}', not approved")
    if reasons:
        return False, reasons
    critical = first.get("critical") == "yes"  # type: ignore[union-attr]
    who = "the coordinator (the PR is critical)" if critical else "the dispatcher, where there is one, or the coordinator (confirmed non-critical)"
    return True, [f"round {last.get('round')}: approved, 0 must-fix, head {last.get('head', '?')}. Merge go comes from {who}; "
                  "CI must be green on that head"]


def num(v: str | None, default: int = 0) -> int:
    return int(v) if v is not None and re.fullmatch(r"\d+", v) else default


def problems(prs: list[dict[str, str]], rounds: list[dict[str, str]], reverts: list[dict[str, str]] | None = None,
             overrides: list[dict[str, str]] | None = None) -> list[str]:
    out: list[str] = []
    merged = {r.get("pr") for r in rounds if r.get("merged")}
    for e in overrides or []:
        out += [f"overrides/{e['_file']}: {w}" for w in override_problems(e)]
    recorded = {k for r in rounds for k in kinds_of(r)}
    for e in prs:
        out += [f"prs/{e['_file']}: {w}" for w in handback_problems(e)]
        for kind in kinds_of(e, "fixes_kinds"):
            if kind not in recorded:
                out.append(f"prs/{e['_file']}: `fixes_kinds` names '{kind}', a finding kind no review round has recorded")
    for e in reverts or []:
        where = f"reverts/{e['_file']}"
        for k in REVERT_KEYS:
            if not e.get(k):
                out.append(f"{where}: `{k}` is missing")
        if e.get("pr") and not re.fullmatch(r"\d+", e["pr"]):
            out.append(f"{where}: `pr` must be a whole number, got '{e['pr']}'")
        elif e.get("pr") and e["pr"] not in merged:
            out.append(f"{where}: PR #{e['pr']} has no round entry that records a merge")
    for kind, entries, keys in (("prs", prs, PR_KEYS), ("rounds", rounds, ROUND_KEYS)):
        seen: set[tuple[str, str]] = set()
        for e in entries:
            where = f"{kind}/{e['_file']}"
            for k in keys:
                if k not in e or e[k] == "":
                    out.append(f"{where}: `{k}` is missing")
                elif k in INT_KEYS and not re.fullmatch(r"\d+", e[k]):
                    out.append(f"{where}: `{k}` must be a whole number, got '{e[k]}'")
            ident = (e.get("pr", ""), e.get("round", ""))
            if ident in seen:
                out.append(f"{where}: a second entry for the same PR{' and round' if kind == 'rounds' else ''}")
            seen.add(ident)
            if e.get("critical", "no") not in ("yes", "no") and (kind == "prs" or e.get("round") == "1"):
                out.append(f"{where}: `critical` must be yes or no")
            if kind == "rounds" and e.get("verdict") not in (None, "", "approved", "changes_requested"):
                out.append(f"{where}: `verdict` must be approved or changes_requested")
    by_pr = {e.get("pr") for e in prs}
    for e in rounds:
        if e.get("pr") not in by_pr:
            out.append(f"rounds/{e['_file']}: no prs/pr-{e.get('pr')}.yaml for this PR")
        if e.get("round") == "1" and "critical" not in e:
            out.append(f"rounds/{e['_file']}: round 1 must record the reviewer's `critical: yes|no` (CRIT-03)")
        if e.get("merged") and num(e.get("must_fix"), -1) != 0:
            out.append(f"rounds/{e['_file']}: merged with open must-fix findings (MRG-01)")
    return out


def status_of(pr: str, rounds: list[dict[str, str]]) -> tuple[str, int, str]:
    mine = sorted((r for r in rounds if r.get("pr") == pr), key=lambda r: num(r.get("round")))
    if not mine:
        return "open, not reviewed", 0, "-"
    last = mine[-1]
    confirmed = next((r.get("critical", "-") for r in mine if r.get("round") == "1"), "-")
    if last.get("merged"):
        return f"merged {last['merged'][:9]}", len(mine), confirmed
    return f"round {last.get('round')}: {last.get('verdict', '?')}, {num(last.get('must_fix'))} must-fix", len(mine), confirmed


def status(prs: list[dict[str, str]], rounds: list[dict[str, str]], deferred: list[dict[str, str]], since: str) -> str:
    """What is open now, in a few lines: the answer to "what is pending" without a list kept in a chat."""
    merged = {r.get("pr") for r in rounds if r.get("merged")}
    lines: list[str] = []
    for e in sorted((e for e in prs if e.get("pr") not in merged), key=lambda e: num(e.get("pr"))):
        pr = e.get("pr", "?")
        mine = sorted((r for r in rounds if r.get("pr") == pr), key=lambda r: num(r.get("round")))
        if e.get("handback") in OPEN_HANDBACKS:
            what = f"{e['handback']}: {e.get('recommended', '').strip() or 'no recommendation'}"
            who = "coordinator"
        elif not mine:
            what, who = "in work, no review round yet", e.get("thread", "implementation")
        else:
            last = mine[-1]
            must = num(last.get("must_fix"))
            ok, _ = _gate(pr, prs, rounds)
            if ok:
                what, who = f"round {last.get('round')} {last.get('verdict')}, gate passes", "merge"
            elif must:
                what, who = f"round {last.get('round')} {last.get('verdict')}, {must} must-fix", e.get("thread", "implementation")
            else:
                what, who = f"round {last.get('round')} {last.get('verdict')}, gate stops", "coordinator"
        lines.append(f"  #{pr}  {what}  [next: {who}]")
    todo, _ = triage(rounds, deferred, since)
    out = [f"Open PRs: {len(lines)}" + (":" if lines else "."), *lines]
    out.append(f"Leftovers without a decision: {len(todo)}" + (" (ledger_tool.py triage)." if todo else "."))
    return "\n".join(out) + "\n"


def table(prs: list[dict[str, str]], rounds: list[dict[str, str]], reverts: list[dict[str, str]] | None = None) -> str:
    undone = {e.get("pr"): e.get("by", "?") for e in reverts or []}
    lines = ["## PRs", "", "| PR | Opened | Thread | Lane | Labels | Package | Critical (author / reviewer) | Compactions | Rounds | Status |",
             "|----|--------|--------|------|--------|---------|------------------------------|-------------|--------|--------|"]
    for e in sorted(prs, key=lambda e: num(e.get("pr"))):
        status, n, confirmed = status_of(e.get("pr", ""), rounds)
        if e.get("pr") in undone:
            status += f", reverted by {undone[e.get('pr')]}"
        lines.append(f"| #{e.get('pr', '?')} | {e.get('opened', '')} | {e.get('thread', '')} | {e.get('lane', '')} | {e.get('labels', '')} | "
                     f"{e.get('package', '-') or '-'} | {e.get('critical', '-')} / {confirmed} | {e.get('compactions', '0')} | {n} | {status} |")
    lines += ["", "## Review rounds", "", "| PR | Round | Date | Thread | Head | Verdict | Must-fix | Should-fix | Report |",
              "|----|-------|------|--------|------|---------|----------|------------|--------|"]
    for e in sorted(rounds, key=lambda e: (num(e.get("pr")), num(e.get("round")))):
        lines.append(f"| #{e.get('pr', '?')} | {e.get('round', '')} | {e.get('date', '')} | {e.get('thread', '')} | {e.get('head', '')} | "
                     f"{e.get('verdict', '')} | {e.get('must_fix', '')} | {e.get('should_fix', '')} | {e.get('report', '')} |")
    return "\n".join(lines) + "\n"


def stats(prs: list[dict[str, str]], rounds: list[dict[str, str]], reverts: list[dict[str, str]] | None = None,
          overrides: list[dict[str, str]] | None = None) -> str:
    if not prs:
        return "No PR entries yet.\n"
    per_pr = {e.get("pr", ""): len([r for r in rounds if r.get("pr") == e.get("pr")]) for e in prs}
    reviewed = [n for n in per_pr.values() if n]
    comp = [num(e.get("compactions")) for e in prs]
    lines = [
        f"PRs: {len(prs)}; reviewed: {len(reviewed)}; merged: {sum(1 for r in rounds if r.get('merged'))}.",
        f"Review rounds per reviewed PR: {sum(reviewed) / len(reviewed):.1f} on average, {max(reviewed)} at most." if reviewed else "No review rounds yet.",
        f"PRs with three or more rounds: {', '.join('#' + p for p, n in per_pr.items() if n >= 3) or 'none'}.",
        f"Compactions per PR: {sum(comp) / len(comp):.1f} on average; PRs with one or more: {', '.join('#' + e.get('pr', '?') for e in prs if num(e.get('compactions'))) or 'none'}.",
        "PRs per thread (compare with replace_after_prs, THR-02):",
    ]
    threads: dict[str, int] = {}
    for e in prs:
        threads[e.get("thread") or "(no thread name)"] = threads.get(e.get("thread") or "(no thread name)", 0) + 1
    for e in rounds:
        key = (e.get("thread") or "(no thread name)") + " [review]"
        threads.setdefault(key, 0)
    for name in list(threads):
        if name.endswith(" [review]"):
            threads[name] = len({r.get("pr") for r in rounds if (r.get("thread") or "(no thread name)") + " [review]" == name})
    lines += [f"  {name}: {n}" for name, n in sorted(threads.items())]
    merged = {r.get("pr") for r in rounds if r.get("merged")}
    undone = sorted({e.get("pr", "") for e in reverts or [] if e.get("pr") in merged}, key=num)
    share = f" ({100 * len(undone) / len(merged):.1f}%)" if merged else ""
    lines.append(f"Reverted: {len(undone)} of {len(merged)} merged PRs{share}{': ' + ', '.join('#' + p for p in undone) if undone else ''}. "
                 "This is the number a cheaper model or a leaner profile must not raise.")
    seen: dict[str, list[str]] = {}
    for r in sorted(rounds, key=lambda r: (num(r.get("pr")), num(r.get("round")))):
        for k in kinds_of(r):
            if r.get("pr", "?") not in seen.setdefault(k, []):
                seen[k].append(r.get("pr", "?"))
    repeated = {k: v for k, v in seen.items() if len(v) > 1}
    if repeated:
        lines.append("Finding kinds seen in more than one PR (each needs a check or a design change, REV-05, META-03):")
        lines += [f"  {k}: {', '.join('#' + p for p in v)}" for k, v in sorted(repeated.items())]
    else:
        lines.append("Finding kinds seen in more than one PR: none.")
    claims = fix_claims(prs, rounds)
    if claims:
        lines.append("Fixes claimed for a finding kind (`fixes_kinds`), and whether they held:")
        for kind, pr, standing, back in claims:
            tail = {"pending": "pending, the PR is not merged", "holding": "holding, not seen since",
                    "regressed": "REGRESSED, seen again in " + ", ".join("#" + p for p in back)
                                 + ". The fix did not remove the cause: go one step up the ladder (META-03)"}[standing]
            lines.append(f"  {kind}: #{pr}, {tail}")
    used = sorted(overrides or [], key=lambda o: num(o.get("pr")))
    waiting = [e for e in prs if e.get("handback") in OPEN_HANDBACKS]
    if waiting:
        lines.append("Hand-backs waiting (THR-15): " + ", ".join(f"#{e.get('pr', '?')} {e['handback']}" for e in waiting) + ".")
    lines.append(f"Owner overrides of the merge gate: {len(used)}"
                 + (": " + ", ".join(f"#{o.get('pr', '?')} ({o.get('date', '?')})" for o in used)
                    + ". Each is a one-off; several for the same reason mean the rule is wrong, change the rule (META-01)." if used else "."))
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Read the per-PR and per-round ledger entries")
    ap.add_argument("cmd", choices=["table", "stats", "check", "gate", "triage", "flags", "status"])
    ap.add_argument("pr", nargs="?", help="PR number (gate only)")
    ap.add_argument("--ledger", type=Path, help="ledger directory (default: ../ledger next to this script, or ./ledger)")
    ap.add_argument("--head", default="", help="gate only: the PR's current head SHA, needed for an owner override when no round is recorded")
    args = ap.parse_args()
    here = Path(__file__).resolve().parent.parent / "ledger"
    ledger = args.ledger or (here if here.is_dir() else Path("ledger"))
    if not ledger.is_dir():
        print(f"error: no ledger directory at {ledger}", file=sys.stderr)
        return 2
    prs, rounds = load(ledger)
    reverts = load_reverts(ledger)
    overrides = load_overrides(ledger)
    if args.cmd == "gate":
        number = (args.pr or "").lstrip("#")
        if not re.fullmatch(r"\d+", number):
            print("error: gate needs a PR number, e.g. `ledger_tool.py gate 12`", file=sys.stderr)
            return 2
        ok, reasons = gate(number, prs, rounds, overrides, args.head)
        by_override = ok and reasons[0].startswith("OWNER OVERRIDE")
        print(f"PR #{number}: {'may be merged by owner override' if by_override else 'may be merged' if ok else 'must not be merged'}")
        print("\n".join(f"  - {r}" for r in reasons))
        return 0 if ok else 1
    deferred, since = load_deferred(ledger)
    if args.cmd == "status":
        print(status(prs, rounds, deferred, since), end="")
        return 0
    if args.cmd == "triage":
        todo, settled = triage(rounds, deferred, since)
        if settled:
            print(f"Settled ({len(settled)}):\n" + "\n".join(f"  {line}" for line in settled))
        if todo:
            print(f"Needs a decision before the next batch ({len(todo)}):\n" + "\n".join(f"  {line}" for line in todo))
            return 1
        print("Nothing is waiting for a decision." + (f" (Merges before {since} are not counted.)" if since else ""))
        return 0
    seam = seam_status(ledger, rounds)
    if args.cmd == "flags":
        found = flags(prs, rounds, reverts, overrides, deferred, since)
        if seam and seam[0]:
            found.append(f"flag: seam-audit-due | {seam[1]}")
        print("\n".join(found) if found else "No flags.")
        return 0
    if args.cmd == "table":
        print(table(prs, rounds, reverts), end="")
        return 0
    if args.cmd == "stats":
        print(stats(prs, rounds, reverts, overrides), end="")
        if seam:
            print(f"Seam audit: {'DUE, ' if seam[0] else 'not due, '}{seam[1]}.")
        return 0
    found = problems(prs, rounds, reverts, overrides) + [f"deferred/{e['_file']}: {w}" for e in deferred for w in deferred_problems(e)]
    print("\n".join(found) if found else f"{len(prs)} PR entries and {len(rounds)} round entries, no problems.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
