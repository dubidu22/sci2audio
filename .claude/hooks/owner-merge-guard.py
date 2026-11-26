#!/usr/bin/env python3
"""Claude Code PreToolUse hook: stops a merge call on a pull request that only the owner merges.

It recognises `gh pr merge`, `gh api .../pulls/N/merge`, a `gh api graphql` merge mutation and the GitHub
MCP merge and auto-merge tools. It reads the PR's changed files with `gh`, or, where `gh` is missing or
signed out (cloud sessions), with `git fetch origin pull/N/head`. It blocks the call (exit 2) when a file
is the owner's to merge, or when the files cannot be read; the session then hands the PR to the owner.
It stops accidents, not intent: a session that edits this file on its own branch runs the edited copy,
and a merge inside `bash -c` or a script is not seen.
"""
import json
import os
import re
import shlex
import subprocess
import sys

OWNER_ONLY = [".claude/**", "CLAUDE.md"]
DEFAULT_BRANCH = "main"
OPERATORS = "();<>|&\n"  # a newline ends a command, as in the shell
# words that can stand before the program of a simple command
PREFIXES = {"env", "time", "timeout", "command", "exec", "nohup", "if", "then", "else", "elif", "do", "while", "until",
            "!", "{"}
# gh flags that take a value, so the value is not mistaken for the PR
VALUE_FLAGS = {"-R", "--repo", "-b", "--body", "-F", "--body-file", "-t", "--subject", "-A", "--author-email",
               "--match-head-commit", "-X", "--method", "-f", "--raw-field", "--field", "-H", "--header", "-q", "--jq"}
HAND_OVER = "Do not merge it another way: tell the owner the PR is ready, with its number."


def matches(glob, path):
    rx = re.escape(glob).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.fullmatch(rx, path) is not None


def simple_commands(command):
    """The shell command split into simple commands, each a list of words; None if it cannot be parsed."""
    try:
        lexer = shlex.shlex(command.replace("\\\n", " "), posix=True, punctuation_chars=OPERATORS)
        lexer.whitespace = " \t\r"  # not the newline: it separates commands
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return None
    out, cur = [], []
    for w in words:
        if w and set(w) <= set(OPERATORS):  # an operator (&&, ;, a newline, a redirection) ends the command
            out.append(cur)
            cur = []
        else:
            cur.append(w)
    return [c for c in out + [cur] if c]


def gh_merge(words):
    """For one simple command: None if it is no merge, else (pr or "", "owner/repo" or "", reason if unreadable)."""
    env_repo = ""
    while words and (words[0] in PREFIXES or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0])
                     or (words[0].startswith("-") and words[0] != "-")  # env -i, time -p
                     or re.fullmatch(r"\d+(\.\d+)?[smhd]?", words[0])):  # timeout 60
        if words[0].startswith("GH_REPO="):
            env_repo = words[0].split("=", 1)[1]
        words = words[1:]
    if not words or os.path.basename(words[0]) != "gh":
        return None
    repo, positional, i = env_repo, [], 1
    while i < len(words):
        w = words[i]
        if w in ("-R", "--repo") and i + 1 < len(words):
            repo, i = words[i + 1], i + 2
            continue
        if w.startswith("--repo="):
            repo = w.split("=", 1)[1]
        elif w in VALUE_FLAGS:
            i += 1
        elif not w.startswith("-"):
            positional.append(w)
        i += 1
    if positional[:2] == ["pr", "merge"]:
        return (positional[2] if len(positional) > 2 else ""), repo, ""
    if positional[:1] == ["api"] and len(positional) > 1:
        m = re.search(r"repos/([^/]+/[^/]+)/pulls/(\d+)/merge\b", positional[1])
        if m:
            return m.group(2), m.group(1), ""
        if positional[1] == "graphql" and re.search(r"mergePullRequest|enablePullRequestAutoMerge", " ".join(words)):
            return "", repo, "a GraphQL merge names the PR by its node id, which this guard cannot check"
    return None


def merge_target(tool, args):
    """(pr, repo, reason) for a merge call, or None."""
    if tool.startswith("mcp__"):
        name = tool.lower()
        if "github" not in name or "merge" not in name or "disable" in name:  # turning auto-merge off merges nothing
            return None
        pr = args.get("pullNumber") or args.get("pull_number") or args.get("number") or ""
        repo = f"{args['owner']}/{args['repo']}" if args.get("owner") and args.get("repo") else ""
        return str(pr), repo, "" if pr else "the call names no pull request number"
    command = args.get("command", "")
    parts = simple_commands(command)
    if parts is None:
        return ("", "", "the command could not be parsed") if re.search(r"\bgh\b.*\bmerge", command) else None
    for words in parts:
        found = gh_merge(words)
        if found:
            return found
    return None


def run(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout if res.returncode == 0 else None


def origin_is(repo):
    url = (run(["git", "remote", "get-url", "origin"]) or "").strip().lower()
    return not repo or re.search(r"[/:]" + re.escape(repo.lower()) + r"(\.git)?/?$", url) is not None


def pr_files(pr, repo):
    """The PR's changed files, or None when they cannot be read."""
    out = run(["gh", "pr", "view", *([pr] if pr else []), *(["-R", repo] if repo else []),
               "--json", "files", "--jq", ".files[].path"])
    if out is not None:
        return out.splitlines()
    if not pr.isdigit() or not origin_is(repo):
        return None
    if run(["git", "fetch", "-q", "origin", f"pull/{pr}/head", DEFAULT_BRANCH]) is None:
        return None
    # FETCH_HEAD is the PR, fetched first; --no-renames lists a moved file under its old path too
    out = run(["git", "diff", "--name-only", "--no-renames", f"origin/{DEFAULT_BRANCH}...FETCH_HEAD"])
    return out.splitlines() if out is not None else None


def main():
    data = json.load(sys.stdin)
    target = merge_target(data.get("tool_name", ""), data.get("tool_input") or {})
    if target is None:
        return 0
    pr, repo, reason = target
    files = None if reason else pr_files(pr, repo)
    if files is None:
        why = reason or "its files could not be read (no signed-in gh, and no git fetch of the PR)"
        print(f"Merge stopped: {why}. {HAND_OVER}", file=sys.stderr)
        return 2
    hits = [p for p in files if any(matches(g, p) for g in OWNER_ONLY)]
    if hits:
        more = " and more" if len(hits) > 5 else ""
        print("Merge stopped: this PR changes " + ", ".join(hits[:5]) + more
              + ", which only the owner merges (CLAUDE.md, rule 9). " + HAND_OVER, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
