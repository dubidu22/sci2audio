"""No fast test asserts an upper bound on wall-clock time without saying why (#734, META-03): a
slow or loaded runner breaks such a bound with no code cause, which is how the bounds of #680 and
#715 failed review (finding kind brittle-test).

A clock value is a call to `time.monotonic`, `time.perf_counter` or `time.time` (or their `_ns`
forms, also imported bare), a name or attribute containing `elapsed`, or a name that a function
fills from one: assigned, stored under a key, passed to a method such as `append`, or looped over.
An upper bound is an `assert` whose comparison has a clock value on its small side (`elapsed <
1.6`, `time.monotonic() < deadline`, `deadline > time.monotonic()`). A lower bound passes, since a
slow runner only makes it safer.

A bound that has to stay carries `# clock-bound: <reason>` on one of its lines or on a comment line
just above it; the reason names what the bound guards against. Tests marked `slow` or `benchmark`
and the browser tests are outside the fast suite and are not read."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKIPPED = {"browser", "corpus", "__snapshots__", "__pycache__"}
CLOCKS = {"monotonic", "perf_counter", "time", "monotonic_ns", "perf_counter_ns", "time_ns"}
UNMARKED = {"slow", "benchmark"}
ALLOWANCE = re.compile(r"#\s*clock-bound\b:?(.*)")


def is_clock_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in CLOCKS and isinstance(func.value, ast.Name) and func.value.id == "time"
    return isinstance(func, ast.Name) and func.id in CLOCKS


def holds_clock(expr: ast.AST, filled: set[str]) -> bool:
    for node in ast.walk(expr):
        if is_clock_call(node):
            return True
        if isinstance(node, ast.Name) and (node.id in filled or "elapsed" in node.id):
            return True
        if isinstance(node, ast.Attribute) and "elapsed" in node.attr:
            return True
    return False


def root_names(target: ast.AST) -> Iterator[str]:
    """The names a target writes into: `took`, `ended` of `ended[k]`, both of `a, b`."""
    while isinstance(target, (ast.Subscript, ast.Attribute, ast.Starred)):
        target = target.value
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from root_names(item)


def filled_names(unit: ast.AST) -> set[str]:
    """The names `unit` (nested functions and lambdas included) fills from a clock value."""
    filled: set[str] = set()
    while True:
        before = len(filled)
        for node in ast.walk(unit):
            targets: list[ast.AST] = []
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
                if node.value is not None and holds_clock(node.value, filled):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                if holds_clock(node.iter, filled):
                    targets = [node.target]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                arguments = [*node.args, *(k.value for k in node.keywords)]
                if any(holds_clock(a, filled) for a in arguments):
                    targets = [node.func.value]
            for target in targets:
                filled.update(root_names(target))
        if len(filled) == before:
            return filled


def upper_bounds(test: ast.AST, filled: set[str]) -> bool:
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left, *node.comparators]
        for at, op in enumerate(node.ops):
            small, large = sides[at], sides[at + 1]
            if isinstance(op, (ast.Lt, ast.LtE)) and holds_clock(small, filled):
                return True
            if isinstance(op, (ast.Gt, ast.GtE)) and holds_clock(large, filled):
                return True
    return False


def is_mark(expr: ast.AST) -> bool:
    target = expr.func if isinstance(expr, ast.Call) else expr
    return (
        isinstance(target, ast.Attribute)
        and target.attr in UNMARKED
        and isinstance(target.value, ast.Attribute)
        and target.value.attr == "mark"
    )


def is_unmarked(expr: ast.AST) -> bool:
    """`expr` is `pytest.mark.slow` or `pytest.mark.benchmark`, called or not, or a list or tuple
    holding one. A mark nested deeper, as on one `pytest.param` of a parametrize, leaves the other
    values in the fast suite."""
    items = expr.elts if isinstance(expr, (ast.List, ast.Tuple)) else [expr]
    return any(is_mark(item) for item in items)


def units(body: list[ast.stmt]) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The functions of the fast suite: those not marked, in classes not marked."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if any(is_unmarked(d) for d in node.decorator_list):
                continue
            if isinstance(node, ast.ClassDef):
                yield from units(node.body)
            else:
                yield node


def module_unmarked(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
        and is_unmarked(node.value)
        for node in tree.body
    )


def allowances(source: str) -> dict[int, tuple[str, bool]]:
    """{line: (reason, alone on its line)} for each `# clock-bound` comment."""
    found = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and (match := ALLOWANCE.fullmatch(token.string)):
            found[token.start[0]] = (
                match.group(1).strip(),
                not token.line[: token.start[1]].strip(),
            )
    return found


def findings(source: str) -> list[str]:
    """'<line>: <what>' for each bound without an allowance and each allowance not kept."""
    tree = ast.parse(source)
    lines = source.splitlines()
    allowed = allowances(source)
    used: set[int] = set()
    out = []
    if not module_unmarked(tree):
        for unit in units(tree.body):
            filled = filled_names(unit)
            for node in ast.walk(unit):
                if not isinstance(node, ast.Assert) or not upper_bounds(node.test, filled):
                    continue
                end = node.end_lineno or node.lineno
                own = [n for n in range(node.lineno, end + 1) if n in allowed]
                above = node.lineno - 1
                if not own and above in allowed and allowed[above][1]:
                    own = [above]
                if own:
                    used.update(own)
                    continue
                out.append(f"{node.lineno}: clock bound: {lines[node.lineno - 1].strip()}")
    for line, (reason, _) in allowed.items():
        if line not in used:
            out.append(f"{line}: clock-bound allowance beside no clock bound")
        elif not reason:
            out.append(f"{line}: clock-bound allowance without a reason")
    return sorted(out, key=lambda item: int(item.split(":", 1)[0]))


def scanned() -> list[Path]:
    """The Python files of the fast suite and its helpers."""
    return [
        path
        for path in sorted((ROOT / "tests").rglob("*.py"))
        if not SKIPPED & set(path.relative_to(ROOT / "tests").parts)
    ]


def test_no_fast_test_asserts_an_upper_wall_clock_bound() -> None:
    hits = []
    for path in scanned():
        for found in findings(path.read_text(encoding="utf-8")):
            hits.append(f"{path.relative_to(ROOT)}:{found}")
    assert hits == [], (
        "a wall-clock upper bound fails on a slow runner; prove the behaviour without the clock, "
        "or say what the bound guards against in `# clock-bound: <reason>`:\n" + "\n".join(hits)
    )


def in_test(*body: str) -> str:
    return "import time\n\n\ndef test_x():\n" + "".join(f"    {line}\n" for line in body)


@pytest.mark.parametrize(
    "body",
    [
        ["started = time.monotonic()", "assert time.monotonic() - started < 3"],
        ["assert elapsed < 1.6"],
        ["start = time.perf_counter()", "assert time.perf_counter() - start < 1.0"],
        ["deadline = time.monotonic() + 10", "assert time.monotonic() < deadline, 'no start'"],
        ["deadline = time.monotonic() + 10", "assert deadline > time.monotonic()"],
        ["t0 = time.time()", "took = time.time() - t0", "assert 1.0 <= took < 1.5"],
        ["assert result.elapsed <= 2"],
        ["from time import monotonic_ns", "t0 = monotonic_ns()", "assert monotonic_ns() - t0 < 9"],
        ["began = time.monotonic()", "assert (", "    time.monotonic() - began", "    < 30", ")"],
        ["began = time.monotonic()", "assert ok and time.monotonic() - began < 5"],
        ["times = [time.monotonic()]", "assert all(t < 3 for t in times)"],
    ],
)
def test_every_known_form_of_a_clock_bound_is_caught(body: list[str]) -> None:
    found = findings(in_test(*body))
    assert len(found) == 1, found
    assert ": clock bound: assert" in found[0]


@pytest.mark.parametrize(
    "body",
    [
        ["took = time.monotonic()", "assert took >= 1.0"],
        ["took = time.monotonic()", "assert 1.0 <= took"],
        ["assert elapsed == 0"],
        ["assert len(items) < 3"],
        ["assert duration < 3"],
        ["assert time.monotonic()"],
        ["assert 'elapsed' in text"],
        ["started = time.monotonic()", "assert count < 3"],
    ],
)
def test_lower_bounds_and_other_comparisons_pass(body: list[str]) -> None:
    assert findings(in_test(*body)) == []


def test_a_clock_value_stored_in_a_nested_function_is_followed() -> None:
    source = in_test(
        "decided, started, ended = [], {}, {}",
        "def timed():",
        "    decided.append(time.monotonic())",
        "run(on_step=lambda step: started.setdefault(step, time.monotonic()))",
        "def read(name):",
        "    ended[name] = time.perf_counter()",
        "took = decided[0] - started['page']",
        "assert took < 1.5",
        "assert ended['a'] < ended['b']",
    )
    assert [item.split(":", 1)[0] for item in findings(source)] == ["12", "13"]


def test_slow_benchmark_and_browser_tests_are_not_read() -> None:
    bound = ["    started = time.monotonic()", "    assert time.monotonic() - started < 3"]
    marked = [
        ["@pytest.mark.slow", "def test_x():", *bound],
        ["@pytest.mark.benchmark(group='pdf')", "def test_x():", *bound],
        ["@pytest.mark.slow", "class TestX:", "  def test_x(self):", *bound],
        ["pytestmark = [pytest.mark.slow, pytest.mark.timeout(60)]", "def test_x():", *bound],
    ]
    for lines in marked:
        assert findings("import time\nimport pytest\n" + "\n".join(lines) + "\n") == [], lines
    unmarked = "import time\nimport pytest\n@pytest.mark.timeout(9)\ndef test_x():\n"
    assert len(findings(unmarked + "\n".join(bound) + "\n")) == 1
    one_value_slow = [
        "@pytest.mark.parametrize('n', [pytest.param(1, marks=pytest.mark.slow), 2])",
        "def test_x(n):",
        *bound,
    ]
    assert len(findings("import time\nimport pytest\n" + "\n".join(one_value_slow) + "\n")) == 1
    files = [path.relative_to(ROOT).as_posix() for path in scanned()]
    assert not [path for path in files if path.startswith("tests/browser/")]
    assert "tests/unit/web_helpers.py" in files
    assert "tests/conftest.py" in files


def test_an_allowance_with_a_reason_lets_the_bound_pass() -> None:
    start = "started = time.monotonic()"
    trailing = in_test(
        start, "assert time.monotonic() - started < 3  # clock-bound: a hang is 60 s"
    )
    inside = in_test(
        start, "assert (", "    time.monotonic() - started  # clock-bound: 60 s", "    < 3", ")"
    )
    above = in_test(
        start,
        "# clock-bound: the hang it guards against is 60 s",
        "assert time.monotonic() - started < 3",
    )
    for source in (trailing, inside, above):
        assert findings(source) == [], source


def test_an_allowance_without_a_reason_fails() -> None:
    start = "started = time.monotonic()"
    for allowance in ("# clock-bound", "# clock-bound:", "# clock-bound:   "):
        source = in_test(start, f"assert time.monotonic() - started < 3  {allowance}")
        assert findings(source) == ["6: clock-bound allowance without a reason"], allowance


def test_an_allowance_beside_no_clock_bound_fails() -> None:
    start = "started = time.monotonic()"
    stale = in_test(start, "assert count < 3  # clock-bound: a hang is 60 s")
    assert findings(stale) == ["6: clock-bound allowance beside no clock bound"]
    two_above = in_test(
        start, "# clock-bound: a hang is 60 s", "x = 1", "assert time.monotonic() - started < 3"
    )
    assert findings(two_above) == [
        "6: clock-bound allowance beside no clock bound",
        "8: clock bound: assert time.monotonic() - started < 3",
    ]
    trailing_above = in_test(
        start, "x = 1  # clock-bound: a hang is 60 s", "assert time.monotonic() - started < 3"
    )
    assert findings(trailing_above) == [
        "6: clock-bound allowance beside no clock bound",
        "7: clock bound: assert time.monotonic() - started < 3",
    ]
