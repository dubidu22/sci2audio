# Plan: batch B-P1, public text-step plugin interface (#216, PE-10) and conformance-suite docs (#203, PE-10, PE-07)

Thread: plugins-b-p1, the textprep/core lane's implementation thread, running on Opus 5.5 high. Written 20 Nov 2026.
**Critical (CRIT-01):** it changes the text-step interface, a layer contract. It does not touch `sci2audio.core`, the lint-imports layers or any golden file. Label `risk:high`. No code is written before the coordinator approves this plan (PLAN-02).

Read first: `governance/rules/implementation.yaml`, `.claude/rules/tests.md`, #216, #203, `textprep/steps.py`, `registry.py` and `runner.py`, `testing/text_steps.py` and `voices.py`, and the decisions D-57, D-103, D-111, D-112, D-114, D-459 and D-595.

## 0. What exists today

- `TextStep` (an ABC) declares `id`, `languages`, `category`, `stage`, `api_version = TEXT_STEP_API` (1) and `find(document, context) -> list[Edit]`. `step_problems` checks the declared attributes, and `check_registry` checks the ids and the stage order.
- `run_steps` drops a step that raises or returns invalid edits and records a `StepProblem`; `strict=True` raises instead (D-111). It has no time limit, and it hands every step the same `Document` object.
- No entry point is read anywhere yet. `app` (`job.py`, `runner.py`, `script.py`, `audio.py`), `web/player.py` (`build_view` and `joined_hyphens`) and `cli.py` all default to `BUILT_IN_STEPS`.
- `sci2audio.testing` already exports `check_text_step`, `text_step_problems`, `check_voice_engine`, `no_network` and `make_document` as plain functions that never import pytest (D-103, D-114).
- `sci2audio.textprep.__all__` mixes the interface with internals (`BUILT_IN_STEPS`, the built-in step classes, `StepRun`, `overlap` and others), so nothing says what a plugin author may rely on.

## 1. Public surface (#216 criterion 3)

A new module, `sci2audio.textprep.api`, holds the whole public surface for plugin authors and contains only re-exports. Its `__all__` is the stability promise:

- Interface: `TextStep`, `StepContext`, `Category`, `Stage`, `ANY_LANGUAGE`, `TEXT_STEP_API`.
- Core types a step reads or builds: `Document`, `Block`, `BlockKind`, `FurnitureRole`, `Part`, `Section`, `Span`, `Edit` and `EditKind`, each re-exported from `sci2audio.core` (textprep may import core, so the layers are unchanged).
- Discovery: `PLUGIN_GROUP = "sci2audio.text_steps"`, `load_plugin_steps`, `PluginInfo` and `PluginProblem` (see §2).

The promise is written in the module docstring and on the docs page. Under `TEXT_STEP_API = 1`, these names keep their meaning. A change that would break a step written against them raises `TEXT_STEP_API`:

- a field removed or renamed;
- a new required argument;
- stricter validation in `Edit` or `Span`;
- a new abstract method.

Additive changes do not raise it: a field with a default (as D-595 did), a new `Category` member, or a new `EditKind` member that a step is never forced to use. Everything else stays private and may change in any release:

- `run_steps`, `StepRun`, `Outcome`, `Status` and `StepProblem`;
- `check_registry` and `BUILT_IN_STEPS`;
- every built-in step class;
- `cut_utterances`, `spoken_text` and the wordings.

`sci2audio.textprep.__init__` keeps its exports so nothing inside the program breaks, and its docstring points plugin authors to `api`. The public part of `sci2audio.testing` is its existing `__all__`, and the page names it.

**The version field** (criterion 3): a plugin must declare `api_version` in its own class. The loader looks it up along the class's MRO, stopping before `TextStep`, so the inherited default does not count. Without this rule, a plugin written for contract 1 would silently claim contract 2 after a break. A missing or different `api_version` rejects the plugin with "targets text-step contract N; this sci2audio provides 1". Built-in steps keep the inherited default, because they ship with the contract they target.

## 2. Discovery and order

New module `textprep/plugins.py` (it uses only the standard library: `importlib.metadata`, `copy`, `threading` and `time`).

- `load_plugin_steps(entry_points=None, *, timeout=PLUGIN_TIMEOUT) -> LoadedPlugins`, which returns `steps`, `plugins` (a `PluginInfo` per loaded step: step id, distribution name and version, entry-point value) and `problems` (a `PluginProblem` per rejected entry point: entry-point name, distribution, message). By default it reads `importlib.metadata.entry_points(group=PLUGIN_GROUP)`; tests pass `EntryPoint` objects instead. It has no module state, and nothing is loaded at import time: the app calls it once per `JobRunner`.
- **What an entry point names:** a `TextStep` subclass or a callable with no arguments that returns a `TextStep` instance. Both are called with no arguments, and one entry point gives one step. A distribution with several steps registers several entry points:
  ```toml
  [project.entry-points."sci2audio.text_steps"]
  greek-letters = "my_plugin:GreekLetterStep"
  ```
- **Rejected entry points.** Each of these becomes a `PluginProblem`, and the rest still load:
  - the import fails, or calling the entry point fails (`Exception` or `SystemExit`);
  - the result is not a `TextStep`;
  - `step_problems` reports something, or `api_version` is not declared or is wrong;
  - the entry-point name is not the step's `id`;
  - the id equals a built-in id: the built-in step stays;
  - the id equals another plugin's id: both plugins are rejected, so the result never depends on install order;
  - an entry point that is listed twice with the same name and value (the same distribution on `sys.path` twice) is loaded once.
- **Order:** `with_plugins(built_in, plugin_steps)` returns the built-in steps of each stage first, followed by that stage's plugins sorted by id. The result is block, then inline, then move steps, and `check_registry` still holds. The built-in steps come first, so a built-in edit wins when edits overlap (Q15, D-105): a plugin adds to the reading and cannot override a built-in rule. Plugins may use any stage, including `move`, under the same runner rules.
- **Switches** (criterion 1): a plugin declares one of the fixed `Category` members, so the existing per-category switches (`--on`/`--off`, the web toggles, `DEFAULT_SWITCHED_OFF`) apply to it unchanged. Its edits show in the report under its step id and category like any other step's.

## 3. A failing, slow or misbehaving plugin never stops a run (criterion 2)

`load_plugin_steps` wraps each plugin in `_GuardedStep`, a `TextStep` that keeps the plugin's id, languages, category and stage and has its own `find`. `run_steps` stays unchanged: a wrapped step that fails raises `StepError`, which goes through the existing D-111 path (the step's edits are dropped, a `StepProblem` is recorded, and a strict run raises). The guard does four things.

1. **Errors:** it catches `Exception` and `SystemExit` (so a plugin's `sys.exit` cannot end the job) and turns them into `StepError`. `KeyboardInterrupt` passes through, so cancel still works.
2. **Time:** it runs `find` in a daemon worker thread and waits for it with `join(timeout)`. A step that runs out of time becomes "took longer than 60 s; its edits are left out". The thread cannot be killed: it is abandoned and its result is thrown away. The job goes on, and the thread dies with the process. **Open choice Q5.**
3. **The document:** plugins get a `copy.deepcopy` of the document, never the object the runner and the other steps share. The copy is made once per run and shared by the plugins. After each plugin, the guard compares the copy with the original (`==` on the frozen dataclasses). If the copy differs, or the step ran out of time, the guard records the problem "changed the document it was given", drops the edits and makes a fresh copy for the next plugin. So no plugin can change the text except through edits that the runner checks.
4. **The runner's checks** already apply: a list of `Edit`, the step's own id, spans inside their blocks, no overlap, whole blocks for a block step, and moves only from a move step.

Problems from loading go into the job report together with the step problems (§5). The run never stops, because loading problems are only recorded.

Not enforced at run time: network access. `no_network()` patches the `socket` module and is not thread-safe, so it cannot guard a live job. The no-network rule for plugins is enforced by the conformance suite (`check_text_step` runs every step inside `no_network()`) and stated on the docs page. A real sandbox would be a follow-up, if it is ever wanted.

## 4. The conformance suite's public entry (#203, and criterion 4 of #216)

**Plain functions, as today:** `check_text_step(step, documents=SAMPLE_DOCUMENTS, *, allow_ask=True)` and `text_step_problems(...)`, plus `check_voice_engine(factory)`, `no_network()` and `make_document(...)`. Reasons:

- D-103 says nothing in `sci2audio.testing` imports pytest.
- The functions work with any test runner.
- They are already used for the built-in steps, so plugins and built-in steps pass the same suite.

Alternatives not chosen:

- A `pytest11` plugin, which would be loaded into every pytest session of anyone who installs sci2audio, including ours.
- A fixture, which needs pytest at import time and hides what is being checked.

The docs page shows a parametrised pytest test of five lines. A plugin author also checks the packaging with `load_plugin_steps()`: the test asserts that the plugin is in `plugins` and that `problems` is empty, which catches a wrong entry-point name or a missing `api_version`. `allow_ask` stays `True` by default for plugins, and only the built-in test passes `False` (v1.0 rule).

## 5. Wiring into the app (needs files outside the textprep lane; see Q1)

- `app/runner.py`: `JobRunner(steps=None)` loads `with_plugins(BUILT_IN_STEPS, load_plugin_steps().steps)` once at construction and keeps the `LoadedPlugins`. `run_script` and `run_audio` default to these steps instead of `BUILT_IN_STEPS`. The functions `run_script_job`, `run_audio_job` and `build_script` keep `BUILT_IN_STEPS` as their default, so tests and goldens see no plugins unless they ask for them.
- `app/report.py`: the report gets `plugins` (id, distribution, version, category) and adds the load problems to `problems` as `("plugin <name>", message)`. The JSON and Markdown reports list the plugins in a "Plugins" line. The web page's existing problems list then shows load problems without a template change.
- `cli.py`: `sci2audio script` and `sci2audio audio` print a line "Plugins: a (dist 1.0), b (...)" when plugins are installed. The CLI already prints the report's problems.
- `web/player.py`: `build_view` and `joined_hyphens` take the runner's steps, so the read-along matches the run. That is two call sites plus their callers in `web/`.
- Not in this PR (follow-up issues, milestone v1.4):
  - Listing the plugins on the web document page (a template and strings in both languages).
  - Recording in the audiobook record which plugins made it, so the player can tell when the plugins changed since.

## 6. Tests written first

Unit tests in `tests/unit/test_textprep_plugins.py`, with a fake plugin package in `tests/plugins/sci2audio_example_plugin.py` that the tests import through `monkeypatch.syspath_prepend`:

1. **Discovery with fake `EntryPoint` objects:** a class, a factory and the order (built-in steps per stage first, then plugins by id). The result passes `check_registry`.
2. **Real discovery:** a temporary `*.dist-info` with `entry_points.txt` and `METADATA` on `sys.path`. The default `load_plugin_steps()` finds it, and `PluginInfo` names the distribution and version.
3. **Broken plugins**, each with its problem text, while the other plugins still load:
   - an import error;
   - not a `TextStep`;
   - a factory that raises;
   - a factory that calls `sys.exit`;
   - `api_version` inherited, missing or 2;
   - an invalid id or language;
   - the entry-point name is not the id;
   - an id that clashes with a built-in step (the built-in stays);
   - two plugins with the same id (both rejected);
   - a duplicate entry point (loaded once).
4. **The guard at run time,** using `run_steps` with the built-in steps plus a plugin:
   - a plugin that raises, or calls `sys.exit`: a problem is recorded, and the script equals the built-in-only script;
   - a slow plugin, with `timeout=0.2` and a 2 s sleep: a problem is recorded, and the run returns well before 2 s;
   - a plugin that changes a block's text through `object.__setattr__`: a problem is recorded, the original document is unchanged, and the next plugin sees the clean text;
   - a strict run raises `StepError` in each case;
   - `KeyboardInterrupt` is not caught.
5. **Conformance (criterion 4):**
   - the example plugin passes `check_text_step`;
   - each built-in step, run through `_GuardedStep`, passes `check_text_step`, which shows the guard keeps the contract;
   - a Hypothesis property in the `ci` profile: on any document from the existing strategies, the guarded and the unguarded step give the same edits.
6. **App:** a `JobRunner` with a fake plugin does three things:
   - it applies the plugin's edit in the script job;
   - switching its category off marks the edit switched off;
   - the JSON and Markdown reports list the plugin, and a broken one appears under problems.
   The CLI prints the "Plugins:" line, and `build_view` uses the runner's steps.
7. **Docs stay true:** a test pulls the Python blocks out of `docs/plugins.md`, runs them in a temporary module, and runs `check_text_step` on the step they define and `check_voice_engine` on the engine they define.
8. **Import hygiene:** a subprocess test checks that importing `sci2audio.textprep.api` loads no entry point and imports neither pytest nor Hypothesis.
9. **Benchmark** (`@pytest.mark.benchmark`): the guard's cost (one deepcopy and the comparisons) on the largest corpus document, with a row in `docs/baseline.md`.

The existing conformance, runner, regression and golden tests must stay unchanged and green. They use `BUILT_IN_STEPS` explicitly or through the job functions' defaults, so no golden file moves.

## 7. Docs page for #203

`docs/plugins.md`, "Writing a text-step plugin", in English:

- What a text step is and the D-57 rule: it proposes marked edits with a reason and never rewrites or summarises the text.
- The public names (§1) and the stability promise, and how `api_version` is used.
- A minimal step of about 25 lines (for example, reading "&" as "and" in paragraphs).
- Its `pyproject.toml` entry point, and the rule that the entry-point name is the step's id.
- Where plugins run (after the built-in steps of their stage), the categories and switches, and what happens to a broken, slow or document-changing plugin.
- Running the suite with pytest: `check_text_step` on the step, the `load_plugin_steps()` packaging check, and `no_network()`.
- A table with every check in `testing.text_steps` and the rule it enforces (D-57, D-61, D-105, D-111, D-558, D-595, D-710).
- A minimal voice engine checked with `check_voice_engine`, and every check in `testing.voices` with its rule (D-52, D-125). Voices have no public entry point yet; the page says so.

The page is linked from `CONTRIBUTING.md` (#203 criterion 3) and has a line in the CHANGELOG under Unreleased. The `testing` docstrings get the same check-to-rule names.

## 8. lint-imports and deptry

- No new package and no layer change: `textprep/api.py` and `textprep/plugins.py` import only `sci2audio.core`, `sci2audio.textprep` and the standard library. The app imports them through `sci2audio.textprep`, which is allowed. Loading a plugin at run time is not an import that lint-imports checks, and the docs ask plugins to import only `sci2audio.textprep.api`.
- The `forbidden` contract of D-114 still holds: `web` and `cli` get steps from `app`, never from `testing`.
- No new dependency, so deptry and the licence gate are unaffected (licence note: none). The fake plugin under `tests/plugins/` is our own code.

## 9. Size and files

- `textprep/plugins.py`: about 250 lines. `textprep/api.py`: about 60.
- App wiring: about 120 lines across `runner.py`, `report.py`, `cli.py` and `web/player.py` with its callers.
- Tests: about 700 lines.
- `docs/plugins.md`: about 250 lines. `CONTRIBUTING.md`, the CHANGELOG and `docs/baseline.md`: one line each.
- In all, about 1,400 lines in one PR (one contract change, so not split, D-75).
- Labels: `lane:textprep`, `lane:docs` and `risk:high`, plus `lane:app`, `lane:cli` and `lane:web` if Q1 is answered (a). There is no core change, so no `lane:core`.

## 10. Open choices for the coordinator

- **Q1. Where does the app wiring go?** (a) In this PR, touching `app/runner.py`, `app/report.py`, `cli.py`, `web/player.py` and its callers in `web/`. (b) In a follow-up PR in the app/web lane after B-W1. **Recommended: (a).** #216 criterion 1 ("listed in the report and switchable") is not met without it, and a public interface the app never loads is useless. The condition: the files must be disjoint from B-W1's plan (#217, #172). If B-W1 touches `app/report.py`, `cli.py` or `web/player.py`, LANE-02 applies: (b), or wait.
- **Q2. Public module name.** `sci2audio.textprep.api` (recommended: no layer-contract change) or a top-level `sci2audio.text_steps`, which matches the entry-point group but needs a new place in the lint-imports layers beside `app`.
- **Q3. What an entry point names, and how it is named.** A class or a zero-argument factory, with the entry-point name equal to the step id (recommended). The alternative is to accept any name and list the id only after loading. The rule costs plugin authors nothing and makes report entries and problems traceable to the `pyproject.toml` line.
- **Q4. Order.** Plugins after the built-in steps of their stage, by id (recommended). The alternative is a `priority` field in the contract: more power for plugins, but a plugin could then block built-in rules, and the order would become part of the public contract.
- **Q5. Slow plugins.** (a) A worker thread with `join(timeout)`, abandoned on timeout (recommended: cheap, works in the frozen installer build; the cost is an abandoned thread that keeps a CPU busy until the process ends). (b) A subprocess per plugin, which can be killed but needs a pickled document, re-imports the plugin in the child, and needs `freeze_support` in the installers (#215). (c) Only measuring the time and warning. Also choose the limit: **60 s per plugin per document** is recommended. The `PLUGIN_TIMEOUT` constant is not a user setting.
- **Q6. The version field.** The plugin must declare `api_version` itself (recommended) or may inherit the default.
- **Q7. A switch to turn plugins off** (`--no-plugins`, a web setting). Recommended: not in this PR; uninstalling is the off switch for now, and a follow-up issue tracks it.
- **Q8. A `JobRunner` loads plugins at construction** (recommended: once per process for the CLI and the server, no module state) or once per job (picks up a newly installed plugin without a restart, at an entry-point scan per job).

## 11. Order of work after approval

1. Tests from §6 (they fail).
2. `textprep/plugins.py` and `textprep/api.py`.
3. App wiring (if Q1 is (a)).
4. `docs/plugins.md`, `CONTRIBUTING.md`, the CHANGELOG and `docs/baseline.md`.
5. The fast checks from `CLAUDE.md`, then `-m browser`, because `web/player.py` changes.
6. Open the PR, run a `ci:full` three-system run, remove the label, and write the ledger entry.

Handoff (THR-07): goal: #216 and #203 in one critical PR. Done: plan written. Next: the coordinator answers Q1 to Q8, then tests first.
