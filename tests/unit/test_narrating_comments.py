"""No comment or docstring tells the history of the code (PR-05, D-891). The review-tag test (#695)
sees one form of it only, so a strict phrase list in `pr_checks.py` fails a pull request, and this
scan of the tree uses the same list, so the author meets it in the fast suite before review.

A phrase list cannot tell a comment that says what the code does from one that says why it is so;
that stays the reviewer's finding. The broad list in `pr_checks.py` keeps warning about it."""

from __future__ import annotations

import ast
import importlib.util
import io
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("src", "tests", "scripts", ".github", "governance/tools")
# they quote the phrases to define or test them
QUOTING = {
    ROOT / ".github" / "governance" / "pr_checks.py",
    ROOT / "governance" / "github-setup" / "pr_checks.py",
    Path(__file__).resolve(),
}


def load_pr_checks():
    path = ROOT / ".github" / "governance" / "pr_checks.py"
    spec = importlib.util.spec_from_file_location("sci2audio_pr_checks_comments", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PR_CHECKS = load_pr_checks()
HISTORY_RE = PR_CHECKS.HISTORY_RE


def comments_and_docstrings(source: str) -> list[tuple[int, str]]:
    found = [
        (token.start[0], token.string)
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            docstring = ast.get_docstring(node, clean=False)
            if docstring is not None:
                found.append((node.body[0].lineno, docstring))
    return found


def test_no_comment_or_docstring_narrates_the_change() -> None:
    hits = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            if path.resolve() in QUOTING or ".venv" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for line, text in comments_and_docstrings(source):
                for match in HISTORY_RE.finditer(text):
                    where = line + text.count("\n", 0, match.start())
                    hits.append(f"{path.relative_to(ROOT)}:{where}: {match.group(0)!r}")
    assert hits == [], (
        "comments and docstrings say why the code is as it is, not how it came to be (PR-05):\n"
        + "\n".join(hits)
    )


@pytest.mark.parametrize(
    "text",
    [
        # the change history the review-tag test let through (D-891)
        "Its THR-10 and THR-05 texts (subagent hosting, D-881) ended with the move to the "
        "claude.ai Project (D-888, ruleset 1.14.0); the D888 pins below replace them.",
        "previously this read the whole file",
        "as requested, the limit is 214",
        "per the review, the lock is taken first",
        "the parser now uses the spaCy tokens",
        "The old implementation joined the pages first.",
        "In this PR the cache moves to the job folder.",
        "this commit removes the retry",
        "The timeout was changed from 5 to 10 seconds.",
        "the helper was renamed in #612",
        "it used to call ffmpeg twice",
        "the reviewer asked for a second check",
    ],
)
def test_the_history_list_catches_change_history(text: str) -> None:
    assert HISTORY_RE.search(text), text


@pytest.mark.parametrize(
    "text",
    [
        "an old position no longer fits and is dropped",
        "The limits in force in this process hold in the child too",
        "this run already replaced cannot be restored: the old versions are gone",
        "a footnote moved to its mark is read after it",
        "stderr is a terminal: progress is rewritten in one line",
        "Each file put in place is added to `committed` with its inode.",
        "a second run no longer sees that link",
        "Used to check that running the steps a second time changes nothing.",
    ],
)
def test_the_history_list_leaves_why_comments_alone(text: str) -> None:
    assert not HISTORY_RE.search(text), text


def diff_adding(path: str, *lines: str) -> str:
    added = "".join(f"+{line}\n" for line in lines)
    return (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -1,0 +1,{len(lines)} @@\n{added}"
    )


def comment_results(diff: str, exemptions: list[dict] | None = None) -> list[dict]:
    results = PR_CHECKS.run_checks(
        {}, "x: y (#1)", [], [("M", "src/a.py")], "", exemptions, None, diff
    )
    return [r for r in results if r["check"] == "comments"]


def test_an_added_change_history_comment_fails_the_pr_check() -> None:
    for path, line in (
        ("src/a.py", "# previously this read the whole file"),
        (".github/workflows/ci.yml", "  # the job now uses the cached wheel"),
        ("src/sci2audio/web/static/app.js", "// as requested, the button stays"),
    ):
        results = comment_results(diff_adding(path, line))
        assert [r["status"] for r in results] == ["FAIL"], (path, results)
        assert f"{path}:1" in results[0]["message"]


def test_a_broad_list_match_only_warns() -> None:
    results = comment_results(diff_adding("src/a.py", "# an old position no longer fits"))
    assert [r["status"] for r in results] == ["WARN"]


def test_a_sanctioned_exemption_lets_a_comment_through() -> None:
    exemption = {
        "check": "comments",
        "paths": ["tests/fixtures/**"],
        "kind": "sanctioned",
        "reason": "fixture files quote narrating comments as test input",
    }
    assert PR_CHECKS.exemption_errors([exemption]) == []
    diff = diff_adding("tests/fixtures/sample.py", "# previously this read the whole file")
    results = comment_results(diff, [exemption])
    assert [r["status"] for r in results] == ["ok"]
