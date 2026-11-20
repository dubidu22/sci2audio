"""The ruleset, its role extracts and its config agree (#683, D-848, D-849). The skill's generator
writes all three, but it knows neither the D-849 wording of PLAN-01 nor `governance_paths`, so a
re-run undoes both silently; these tests make that undo fail (META-03)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE = ROOT / "governance"
RULESET = (GOVERNANCE / "claude-project-rules.yaml").read_text(encoding="utf-8")
CONFIG = json.loads((GOVERNANCE / "governance-config.json").read_text(encoding="utf-8"))
EXTRACTS = sorted((GOVERNANCE / "rules").glob("*.yaml"))

PLAN_01 = (
    "Every implementation thread writes a numbered plan in ./governance/plans/ before writing "
    "tests or code. The plan names every test it promises as a pytest node ID, and the PR body "
    "repeats that list under the heading '## Tests promised in the plan'; the governance check "
    "fails the PR when a listed test does not collect. Deviating from an approved plan requires "
    "a new coordinator D-number."
)


def profile(text: str) -> dict[str, str]:
    """The `project_profile:` block as key -> raw value. A line parser, because PyYAML is only a
    transitive dev dependency; the flow lists in it are JSON."""
    out: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        if line == "project_profile:":
            inside = True
            continue
        if inside:
            if not line.startswith("  "):
                break
            key, _, value = line.strip().partition(": ")
            out[key] = value
    assert out, "no project_profile block"
    return out


def rules(text: str) -> dict[str, str]:
    """Each `  - id:` block by its id, as the raw lines up to the next block or section."""
    out: dict[str, str] = {}
    current = ""
    for line in text.splitlines():
        found = re.fullmatch(r"  - id: (\S+)", line)
        if found:
            current = found.group(1)
            out[current] = line + "\n"
        elif current and line.startswith("    "):
            out[current] += line + "\n"
        else:
            current = ""
    return out


def rule_text(block: str) -> str:
    found = re.search(r'^    rule: (".*")$', block, re.MULTILINE)
    assert found, block
    return json.loads(found.group(1))


def test_plan_01_carries_the_promised_tests_wording() -> None:
    assert rule_text(rules(RULESET)["PLAN-01"]) == PLAN_01
    implementation = (GOVERNANCE / "rules" / "implementation.yaml").read_text(encoding="utf-8")
    assert rule_text(rules(implementation)["PLAN-01"]) == PLAN_01


@pytest.mark.parametrize("extract", EXTRACTS, ids=lambda p: p.stem)
def test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset(extract: Path) -> None:
    text = extract.read_text(encoding="utf-8")
    full = rules(RULESET)
    own = rules(text)
    assert own, f"{extract.name} holds no rule"
    for rule_id, block in own.items():
        assert block == full.get(rule_id), f"{extract.name}: {rule_id} differs from the ruleset"
    assert profile(text) == profile(RULESET)


@pytest.mark.parametrize("key", ["critical_paths", "label_paths", "doc_paths", "governance_paths"])
def test_the_profile_holds_the_paths_of_the_config(key: str) -> None:
    assert json.loads(profile(RULESET)[key]) == CONFIG[key]
