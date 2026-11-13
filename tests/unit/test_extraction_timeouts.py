"""Every extraction test has a timeout, so a file that makes extraction hang fails the test
instead of the whole run (Issue #5, D-403). Checked for each `test_extraction_*` module, this
one included, so a new module can't leave it out."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.timeout(60)

MODULES = sorted(Path(__file__).parent.glob("test_extraction_*.py"))


def module_timeout(path: Path) -> float | None:
    """The seconds of a module-wide `pytestmark = pytest.mark.timeout(N)`, or None."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
        ):
            continue
        marks = node.value.elts if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
        for mark in marks:
            if (
                isinstance(mark, ast.Call)
                and ast.unparse(mark.func) == "pytest.mark.timeout"
                and mark.args
                and isinstance(mark.args[0], ast.Constant)
            ):
                return float(mark.args[0].value)
    return None


def test_the_extraction_modules_are_found() -> None:
    names = {path.name for path in MODULES}
    assert {"test_extraction_pdf.py", "test_extraction_pdf_broken.py"} <= names
    assert Path(__file__).name in names


@pytest.mark.parametrize("module", MODULES, ids=[path.stem for path in MODULES])
def test_every_extraction_module_has_a_timeout(module: Path) -> None:
    seconds = module_timeout(module)
    assert seconds is not None, f"{module.name} sets no pytestmark = pytest.mark.timeout(...)"
    assert 0 < seconds <= 120


def test_a_module_without_a_timeout_is_found(tmp_path: Path) -> None:
    bare = tmp_path / "test_extraction_bare.py"
    bare.write_text("import pytest\npytestmark = pytest.mark.slow\n", encoding="utf-8")
    assert module_timeout(bare) is None
    both = tmp_path / "test_extraction_both.py"
    both.write_text(
        "import pytest\npytestmark = [pytest.mark.slow, pytest.mark.timeout(30)]\n",
        encoding="utf-8",
    )
    assert module_timeout(both) == 30
