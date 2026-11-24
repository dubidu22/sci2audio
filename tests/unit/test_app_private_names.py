"""No module of `src/sci2audio` outside `sci2audio.app` reaches into a private name (leading
underscore) of `sci2audio.app.audio` (#783, #980): what another layer needs is exported by the
package.

Scanned: every `.py` file under `src/sci2audio` except `sci2audio/app/`; the tests are not scanned.
A private name starts with one underscore or two without a closing pair; dunders (`__all__`,
`__name__`) are not private and never flagged.
Flagged forms: `from sci2audio.app.audio import _x` (absolute or relative, any `as` alias),
`from sci2audio.app.audio import *`, `import sci2audio.app.audio._x`, and attribute access
`_x` on the module reached through any import (`import sci2audio.app.audio as a`,
`from sci2audio.app import audio`, `from .. import app; app.audio._x`, `import sci2audio`,
relative forms of these).
Names are bound by imports only, in one table per file where the last import of a name wins
(two functions importing different things under the same name can give a missed or a false hit;
no module does this). Flagged: a later assignment, parameter or loop variable that reuses the
imported name (`audio = other(); audio._x`, `def f(audio): return audio._x`) still counts as the
module. Not flagged: a copy of the module under another name (`b = audio; b._x`),
`from sci2audio.app import *; audio._x`, `getattr(module, "_x")` and `importlib.import_module`;
the scan reads imports by syntax only."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "sci2audio"
PRIVATE_MODULE = "sci2audio.app.audio"


def _is_private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _absolute(node: ast.ImportFrom, package: str) -> str | None:
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    if node.level - 1 >= len(parts):
        return None
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module else [])])


def _resolve(node: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _resolve(node.value, aliases)
        return None if base is None else f"{base}.{node.attr}"
    return None


def private_names(source: str, package: str) -> list[str]:
    """Private names of `PRIVATE_MODULE` that `source` (a module in `package`) reaches."""
    tree = ast.parse(source)
    found: list[str] = []
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = _absolute(node, package)
            if module is None:
                continue
            for a in node.names:
                if module == PRIVATE_MODULE and (_is_private(a.name) or a.name == "*"):
                    found.append(a.name)
                aliases[a.asname or a.name] = f"{module}.{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                prefix = f"{PRIVATE_MODULE}."
                if a.name.startswith(prefix) and _is_private(a.name[len(prefix) :].split(".")[0]):
                    found.append(a.name)
                if a.asname:
                    aliases[a.asname] = a.name
                else:
                    top = a.name.split(".")[0]
                    aliases[top] = top
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and _is_private(node.attr)
            and _resolve(node.value, aliases) == PRIVATE_MODULE
        ):
            found.append(f"{PRIVATE_MODULE}.{node.attr}")
    return found


def _package_of(path: Path) -> str:
    return ".".join(path.relative_to(SRC.parent).parent.parts)


def test_no_module_outside_app_reaches_a_private_name_of_app_audio() -> None:
    outside = [p for p in sorted(SRC.rglob("*.py")) if "app" not in p.relative_to(SRC).parts[:1]]
    assert outside
    offenders = {
        str(p.relative_to(SRC)): names
        for p in outside
        if (names := private_names(p.read_text(encoding="utf-8"), _package_of(p)))
    }
    assert not offenders


_ATTR = ["sci2audio.app.audio._kept"]


@pytest.mark.parametrize(
    ("source", "package", "expected"),
    [
        ("from sci2audio.app.audio import _kept, kept_settings\n", "sci2audio.web", ["_kept"]),
        ("import sci2audio.app.audio._kept\n", "sci2audio.web", _ATTR),
        ("import sci2audio.app.audio as a\nx = a._kept\n", "sci2audio.web", _ATTR),
        ("from sci2audio.app import audio\naudio._kept()\n", "sci2audio.web", _ATTR),
        ("from sci2audio.app import audio as a\na._kept()\n", "sci2audio.web", _ATTR),
        ("import sci2audio.app.audio\nsci2audio.app.audio._kept()\n", "sci2audio.web", _ATTR),
        ("import sci2audio\nsci2audio.app.audio._kept()\n", "sci2audio.web", _ATTR),
        ("from sci2audio import app\napp.audio._kept()\n", "sci2audio.web", _ATTR),
        ("from ..app.audio import _kept\n", "sci2audio.web", ["_kept"]),
        ("from .app.audio import _kept as k\n", "sci2audio", ["_kept"]),
        ("from ..app import audio\naudio._kept()\n", "sci2audio.web", _ATTR),
        ("from .. import app\napp.audio._kept()\n", "sci2audio.web", _ATTR),
        ("from sci2audio import app\naudio = other()\napp.audio._kept()\n", "sci2audio.web", _ATTR),
        (
            "from sci2audio.app import audio\naudio = other()\naudio._kept()\n",
            "sci2audio.web",
            _ATTR,
        ),
        (
            "from sci2audio.app import audio\ndef f(audio):\n    return audio._kept\n",
            "sci2audio.web",
            _ATTR,
        ),
        ("from sci2audio.app.audio import *\n", "sci2audio.web", ["*"]),
        ("from ..app.audio import *\n", "sci2audio.web", ["*"]),
    ],
    ids=[
        "from-import",
        "dotted-import",
        "import-as-alias",
        "from-package-import-module",
        "from-package-import-module-as",
        "full-dotted-attribute",
        "top-package-attribute-chain",
        "app-package-attribute-chain",
        "relative-from-import",
        "relative-from-import-as",
        "relative-module-alias",
        "relative-package-import-chain",
        "assignment-does-not-unbind-the-package-chain",
        "assignment-does-not-unbind-the-alias",
        "parameter-does-not-unbind-the-alias",
        "star-import",
        "relative-star-import",
    ],
)
def test_the_scan_sees_each_form(source: str, package: str, expected: list[str]) -> None:
    assert private_names(source, package) == expected


@pytest.mark.parametrize(
    ("source", "package"),
    [
        ("from sci2audio.app.audio import kept_settings\n", "sci2audio.web"),
        ("import sci2audio.app.audio as a\na.kept_settings()\n", "sci2audio.web"),
        ("import sci2audio.app.audio as a\nb = other._kept\n", "sci2audio.web"),
        ("from sci2audio.app import settings\nsettings._x\n", "sci2audio.web"),
        ("from ..core import _x\n", "sci2audio.web"),
        ("from ...app.audio import _kept\n", "sci2audio"),
        ("from sci2audio.app.audio import __all__\n", "sci2audio.web"),
        ("from sci2audio.app.audio import __all__ as names\n", "sci2audio.web"),
        ("import sci2audio.app.audio as a\nx = a.__name__\n", "sci2audio.web"),
        ("from sci2audio.app import audio\naudio.__doc__\n", "sci2audio.web"),
        ("import sci2audio.app.audio.__init__\n", "sci2audio.web"),
        ("from sci2audio.app import audio\nb = audio\nb._kept()\n", "sci2audio.web"),
        ("from sci2audio.app import *\naudio._kept()\n", "sci2audio.web"),
    ],
    ids=[
        "public-from-import",
        "public-attribute",
        "unrelated-object",
        "other-module",
        "other-private-name",
        "relative-beyond-the-package",
        "dunder-from-import",
        "dunder-from-import-as",
        "dunder-attribute-through-alias",
        "dunder-attribute-through-module",
        "dunder-dotted-import",
        "copy-of-the-module-is-not-followed",
        "star-import-of-the-package-is-not-followed",
    ],
)
def test_the_scan_ignores_public_dunder_and_unfollowed_names(source: str, package: str) -> None:
    assert private_names(source, package) == []
