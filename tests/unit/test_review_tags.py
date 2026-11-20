"""No comment or docstring names a review round or a finding (#695, PR-05): such a tag says who
asked, not why the code is as it is, and the reason belongs in the text itself. An issue or PR
number may stay, since it points to the reason.

What is read: `#` comments and the docstrings of modules, classes and functions in `.py` files,
`//` and `/* */` comments in `.js` and `.css` files, `#` comments in `.toml` files and `{# #}` and
`<!-- -->` comments in `.html` templates, under `src/` and `tests/`. Python string literals and
TOML values are data and are not read. The regression cases, the corpus and the snapshots are
golden files and are skipped."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKIPPED = {"regression", "corpus", "__snapshots__", "__pycache__"}

REVIEW_TAG = re.compile(
    # "(#667 review S1)", "(#481 review)", "(#350, review N1)", "(#569 round 1, R3)"
    r"#\d+,?\s+(?i:review\b|round\s+\d+)"
    # "review round 2 of #83", "Review round 1 of #692, S1:"
    r"|\b(?i:review\s+round)\s+\d+"
    # "(review of PR #228)", "(review of #530, F1)"
    r"|\b(?i:review)\s+of\s+(?:PR\s+)?#\d+"
    # "(review M1)", "(review R1-2, R2-1)"; the finding letters are capitals
    r"|\b(?i:review)\s+[A-Z]{1,2}\d+"
    # "(round 2, N1)", "(round 1 S1a)", "round 2 of #450"
    r"|\b(?i:round)\s+\d+,?\s+(?:of\s+(?:PR\s+)?#\d+|[A-Z]{1,2}\d+)"
    # "(round 1)"
    r"|\((?i:round)\s+\d+\)"
)

JS_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
HTML_COMMENT = re.compile(r"\{#.*?#\}|<!--.*?-->", re.S)


def python_texts(source: str) -> Iterator[tuple[int, str]]:
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            yield token.start[0], token.string
    for node in ast.walk(ast.parse(source)):
        kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        if isinstance(node, kinds) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                yield first.lineno, ast.get_source_segment(source, first) or ""


def toml_texts(source: str) -> Iterator[tuple[int, str]]:
    """The `#` comment of each line; the files hold no multi-line strings."""
    for number, line in enumerate(source.splitlines(), 1):
        quote = ""
        for at, char in enumerate(line):
            if quote:
                if char == quote and not (quote == '"' and line[at - 1] == "\\"):
                    quote = ""
            elif char in "\"'":
                quote = char
            elif char == "#":
                yield number, line[at:]
                break


def matched_texts(pattern: re.Pattern[str], source: str) -> Iterator[tuple[int, str]]:
    for match in pattern.finditer(source):
        yield source.count("\n", 0, match.start()) + 1, match.group(0)


def texts(path: Path, source: str) -> Iterator[tuple[int, str]]:
    if path.suffix == ".py":
        return python_texts(source)
    if path.suffix == ".toml":
        return toml_texts(source)
    if path.suffix in {".js", ".css"}:
        return matched_texts(JS_COMMENT, source)
    if path.suffix == ".html":
        return matched_texts(HTML_COMMENT, source)
    return iter(())


def tags(path: Path, source: str) -> list[tuple[int, str]]:
    """(line, tag) for every review tag in the comments and docstrings of `source`."""
    found = []
    for line, text in texts(path, source):
        for match in REVIEW_TAG.finditer(text):
            found.append((line + text.count("\n", 0, match.start()), match.group(0)))
    return sorted(found)


def test_no_comment_or_docstring_carries_a_review_tag() -> None:
    hits = []
    for top in ("src", "tests"):
        for path in sorted((ROOT / top).rglob("*")):
            if not path.is_file() or SKIPPED & set(path.relative_to(ROOT).parts):
                continue
            if path == Path(__file__).resolve():  # its comments show the forms
                continue
            if path.suffix not in {".py", ".toml", ".js", ".css", ".html"}:
                continue
            for line, tag in tags(path, path.read_text(encoding="utf-8")):
                hits.append(f"{path.relative_to(ROOT)}:{line}: {' '.join(tag.split())}")
    assert hits == [], "review tags say who asked, not why:\n" + "\n".join(hits)


@pytest.mark.parametrize(
    "text",
    [
        "(#689 review S1)",
        "Review round 1 of #692, S1:",
        "review round 2 of #83",
        "the stamp goes back with each save (review M1)",
        "(#481 review)",
        "(#350, review N1)",
        "(review R1-2, R2-1)",
        "(review of PR #228)",
        "(review of #530, F1)",
        "(PR #547 review B1)",
        "(#569 round 1, R3)",
        "(round 2, N1)",
        "Step 2 (round 1 S1a): text put before all three",
        "round 2 of #450",
        "(#264 round 1)",
        "(round 1)",
    ],
)
def test_the_pattern_catches_every_known_form(text: str) -> None:
    assert REVIEW_TAG.search(text), text


@pytest.mark.parametrize(
    "text",
    [
        "for a review, see",
        "the preview plays the newest file",
        "thanks to #3 reviewers",
        "round 2 decimals",
        "a review of the literature",
        "a held key toggles once (#394)",
        "Software\nReview\nRepository",
    ],
)
def test_the_pattern_leaves_plain_words_alone(text: str) -> None:
    assert not REVIEW_TAG.search(text), text


def test_only_comments_and_docstrings_are_read() -> None:
    python = (
        '"""Module (review M1)."""\n'
        'TEXT = "a string (review M1)"\n'
        "x = 1  # a comment (#12 review S1)\n"
        "def f():\n"
        '    """A docstring\n    over lines (round 2, N1)."""\n'
    )
    assert tags(Path("a.py"), python) == [(1, "review M1"), (3, "#12 review"), (6, "round 2, N1")]
    toml = 'goal = "a value (review M1) # not a comment"\nkey = 1  # a comment (review B1)\n'
    assert tags(Path("a.toml"), toml) == [(2, "review B1")]
    js = 'const s = "review M1";\n// a comment (review S2)\n/* a block\n (round 1) */\n'
    assert tags(Path("a.js"), js) == [(2, "review S2"), (4, "(round 1)")]
    html = '<p title="review M1">{# a note (review N1) #}</p>\n<!-- (#9 review) -->\n'
    assert tags(Path("a.html"), html) == [(1, "review N1"), (2, "#9 review")]
