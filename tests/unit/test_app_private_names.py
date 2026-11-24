"""Nothing outside `sci2audio.app` reaches into a private name (leading underscore) of
`sci2audio.app.audio` (#783): what another layer needs is exported by the package."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "sci2audio"
PRIVATE_MODULE = "sci2audio.app.audio"


def private_imports(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == PRIVATE_MODULE:
            found += [a.name for a in node.names if a.name.startswith("_")]
        elif isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.startswith(f"{PRIVATE_MODULE}._")]
    return found


def test_no_module_outside_app_imports_a_private_name_from_app_audio() -> None:
    outside = [p for p in sorted(SRC.rglob("*.py")) if "app" not in p.relative_to(SRC).parts[:1]]
    assert outside
    offenders = {str(p.relative_to(SRC)): names for p in outside if (names := private_imports(p))}
    assert not offenders


def test_the_scan_sees_a_private_import(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from sci2audio.app.audio import _kept, kept_settings\nimport sci2audio.app.audio._kept\n",
        encoding="utf-8",
    )
    assert private_imports(probe) == ["_kept", "sci2audio.app.audio._kept"]
