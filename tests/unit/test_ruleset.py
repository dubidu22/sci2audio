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
        "every event reaches the Coordinator as one line starting with `COORDINATOR:`, and its "
        "content goes in the batch file",
        "You also watch CI and merges for PRs outside the batch that the Coordinator names",
    ):
        assert fragment in text, fragment


# D-888 (ruleset 1.14.0): the threads are chats in the claude.ai Project, and the working files
# stay on branch governance. The generator words the starter block for a Claude Code session,
# so the two instruction files get the Project wording by exact replace; these pins catch a
# regeneration that brings the old text back.
PROJECT_CHAT_START = (
    "ask the owner to open a new chat in the sci2audio claude.ai Project on that model and paste "
    "it. The Project's instructions (`governance/project_chat_instructions.md`) tell that chat how "
    "to clone the repository and add the governance worktree."
)


@pytest.mark.parametrize("name", ["project_instructions.md", "dispatcher_instructions.md"])
def test_an_instruction_file_starts_threads_as_project_chats(name: str) -> None:
    text = " ".join((GOVERNANCE / name).read_text(encoding="utf-8").split())
    assert PROJECT_CHAT_START in text
    assert "claude --model" not in text
    assert "subagent" not in text.replace("starts a session or subagent", "")


def test_no_rule_hosts_threads_as_subagents_or_hands_out_compact() -> None:
    """A claude.ai chat has neither the Agent tool of D-881 nor /compact (THR-11)."""
    assert "subagents" not in RULESET
    assert "/compact" not in RULESET
    assert "THR-11" not in rules(RULESET)
    assert CONFIG["coordinator_compact_every_batches"] == 0


def test_the_project_chat_instructions_set_up_the_clone_and_the_governance_worktree() -> None:
    text = (GOVERNANCE / "project_chat_instructions.md").read_text(encoding="utf-8")
    for line in (
        "git clone https://github.com/dubidu22/sci2audio.git",
        "git worktree add ../sci2audio-governance governance",
        "governance/rules/<role>.yaml",
    ):
        assert line in text, line
    assert "governance/project_chat_instructions.md" in CONFIG["critical_paths"]


# D-889: the coordinator asks the Project's channel session for each worker thread, so a
# pasted line saying no chat can open another would send Colin click steps PREF-01 avoids.
PROJECT_CHANNEL_START = "ask the Project's channel session for"


def test_the_project_chat_instructions_start_threads_through_the_channel_session() -> None:
    text = " ".join(
        (GOVERNANCE / "project_chat_instructions.md").read_text(encoding="utf-8").split()
    )
    assert PROJECT_CHANNEL_START + " each worker thread" in text
    assert "(D-889)" in text
    assert "No chat here can open another chat" not in text
    assert "Never ask for a token or accept one." in text


@pytest.mark.parametrize("name", ["project_instructions.md", "dispatcher_instructions.md"])
def test_an_instruction_file_starts_threads_through_the_channel_session(name: str) -> None:
    text = " ".join((GOVERNANCE / name).read_text(encoding="utf-8").split())
    assert PROJECT_CHANNEL_START + " the thread" in text
    assert "(D-889)" in text
