"""The ruleset, its role extracts and its config agree (#683, D-848, D-849). The skill's generator
writes all three. It keeps `governance_paths` since ruleset 1.10.0 (D-877), but its PLAN-01 says
"by its test ID" and "does not exist", while the check reads backticked pytest node IDs, so the
D-849 wording is restored by exact replace after each re-run; these tests make a missed restore
or a dropped path list fail (META-03)."""

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
            if not line.strip() or line.lstrip().startswith("#"):
                continue
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


def applies_to(block: str) -> list[str]:
    found = re.search(r"^    applies_to: (\S+)$", block, re.MULTILINE)
    assert found, block
    return found.group(1).split(",")


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
    role = re.search(r"^extract_for: (\S+)$", text, re.MULTILINE)
    assert role, f"{extract.name} names no role"
    scoped = {i for i, b in full.items() if {role.group(1), "all"} & set(applies_to(b))}
    assert set(own) == scoped, f"{extract.name}: rules missing or extra: {set(own) ^ scoped}"
    for rule_id, block in own.items():
        assert block == full.get(rule_id), f"{extract.name}: {rule_id} differs from the ruleset"
    assert profile(text) == profile(RULESET)


@pytest.mark.parametrize("key", ["critical_paths", "label_paths", "doc_paths", "governance_paths"])
def test_the_profile_holds_the_paths_of_the_config(key: str) -> None:
    assert json.loads(profile(RULESET)[key]) == CONFIG[key]


# D-882 (ruleset 1.13.0): the dispatcher changes of the audit of 22 Nov 2026. The generator has
# no setting for them, so they are exact replaces too, and a regeneration that drops one fails here.
D882 = {
    "THR-10": (
        "the dispatcher starts implementation and review threads as background subagents of its "
        "own session (Agent tool, with the slot's model and effort from "
        "execution_profile.model_routing, and `isolation: worktree` when the thread writes files); "
        "it writes a starter block only if it has no such tool.",
    ),
    "MRG-01": (
        "for critical ones the coordinator, whose go is the file "
        "./governance/ledger/gos/pr-<N>.yaml with the head SHA, the coordinator and the time, "
        "written by the coordinator and required by ledger_tool.py gate <N>",
        "For a risk:high PR, re-run `governance pr checks` on that head after the approving round "
        "entry is pushed.",
        "record the new SHA as `updated_head` in the latest round entry",
    ),
    "ROLE-11": (
        "It also watches CI and merges for PRs outside the batch that the coordinator names, and "
        "records them in the batch file.",
    ),
    "THR-05": ("and never while one of its subagents is running.",),
    "ROLE-17": (
        "A dispatcher event reaches you as one line starting with `COORDINATOR:`; its content is "
        "in ./governance/plans/batch-<NNN>.md, read it there.",
    ),
    "THR-04": (
        "The dispatcher sends the coordinator one line per event, starting with `COORDINATOR:`; "
        "the content goes in the batch file.",
    ),
}


@pytest.mark.parametrize("rule_id", sorted(D882))
def test_a_d882_rule_keeps_its_wording(rule_id: str) -> None:
    """Each extract repeats the ruleset's block byte for byte (the test above), so the ruleset
    is enough here."""
    text = rule_text(rules(RULESET)[rule_id])
    for fragment in D882[rule_id]:
        assert text.count(fragment) == 1, f"{rule_id} lost: {fragment}"


def test_the_dispatcher_instructions_carry_the_d882_changes() -> None:
    text = " ".join((GOVERNANCE / "dispatcher_instructions.md").read_text(encoding="utf-8").split())
    for fragment in (
        "Start implementation and review threads as background subagents of your own session: "
        "the Agent tool, with the slot's model and effort from `execution_profile.model_routing`, "
        "and `isolation: worktree` when the thread writes files. Write a starter block only if "
        "you have no such tool.",
        "never while one of your subagents is running (`THR-05`)",
        "every event reaches the Coordinator as one line starting with `COORDINATOR:`, and its "
        "content goes in the batch file",
        "You also watch CI and merges for PRs outside the batch that the Coordinator names",
    ):
        assert fragment in text, fragment
