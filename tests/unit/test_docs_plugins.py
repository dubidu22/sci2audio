"""The code on docs/plugins.md runs and passes the conformance suite (#203)."""

import re
import sys
import types
from pathlib import Path

import pytest

DOCS = Path(__file__).parents[2] / "docs" / "plugins.md"
NEEDS_INSTALLING = {"test_the_entry_point_loads"}  # needs the example package installed


def blocks() -> dict[str, str]:
    """Each Python block of the page by the file name on its first line."""
    found = re.findall(r"```python\n# (\S+)\n(.*?)```", DOCS.read_text(encoding="utf-8"), re.S)
    return dict(found)


def module(name: str, code: str) -> types.ModuleType:
    made = types.ModuleType(name)
    exec(compile(code, f"docs/plugins.md:{name}", "exec"), made.__dict__)  # noqa: S102
    return made


def test_the_page_has_its_four_files() -> None:
    assert sorted(blocks()) == [
        "my_plugin.py",
        "my_voice.py",
        "tests/test_my_plugin.py",
        "tests/test_my_voice.py",
    ]


@pytest.mark.parametrize(
    ("source", "test"),
    [("my_plugin.py", "tests/test_my_plugin.py"), ("my_voice.py", "tests/test_my_voice.py")],
)
def test_the_page_s_tests_pass_on_the_page_s_code(
    source: str, test: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = blocks()
    name = source.removesuffix(".py")
    monkeypatch.setitem(sys.modules, name, module(name, code[source]))
    tests = module("page_tests", code[test])
    ran = [
        value()
        for key, value in vars(tests).items()
        if key.startswith("test_") and key not in NEEDS_INSTALLING
    ]
    assert ran


def test_the_entry_point_on_the_page_names_the_step_by_its_id() -> None:
    text = DOCS.read_text(encoding="utf-8")
    assert 'ampersand-and = "my_plugin:AmpersandStep"' in text
    assert 'id = "ampersand-and"' in blocks()["my_plugin.py"]
