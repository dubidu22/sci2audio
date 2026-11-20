# Review PR #676, round 1 (batch B-P1, #216 and #203)

Thread: review-plugins-b-p1 (Opus 5.5). Head reviewed: 6f25cd4. Date: 2026-11-20.
**Critical: yes** (CRIT-01: the text-step interface, a layer contract; `risk:high` set). Plan `plans/plugins-b-p1-plan.md`, approved as D-836.

**Verdict: changes requested** (1 must-fix, 2 should-fix, 4 notes).

## Verified

- (a) Contract: `textprep/api.py` holds re-exports only; `__all__` is plan §1 plus `LoadedPlugins` (N1). Nothing private leaks: `run_steps`, `StepRun`, `StepError`, the registry and the built-in steps stay out of `api`. `_declares_version` (plugins.py:195-205) walks `type(step).__mro__` and stops at `TextStep`, so the inherited default does not count; a value set on an intermediate plugin base or on the instance counts, which is "declared by the plugin". A wrong value is caught by `step_problems` ("api_version must be 1, got 2").
- (b) Guard: one `copy.deepcopy` per plugin call, run in a daemon thread with `join(timeout)`; timeout, `SystemExit` and a changed copy become `StepError`; `==` on the frozen core dataclasses is the right comparison, and since each plugin gets its own copy the original can never change. `StepContext` is frozen with a frozenset, so it needs no copy. `KeyboardInterrupt` raised in the plugin is re-raised in the job's thread. No module state; nothing loaded at import time (subprocess test with `entry_points = None`).
- (c) Discovery: every rejection case of plan §2 has a parametrised test (import error, not a TextStep, an instance instead of a class or factory, factory raises, factory `sys.exit`, inherited and wrong `api_version`, bad id, name not equal to id, built-in clash keeps the built-in, two plugins with one id both rejected, an entry point listed twice loaded once). Order is built-in then plugins by id per stage, and `check_registry` holds (it runs inside `run_steps`).
- (d) Layers: `api.py` and `plugins.py` import only core, textprep and the standard library. No file under `src/sci2audio/web/` changed. lint-imports 3 kept, deptry clean, ruff clean (local).
- (e) App: `run_script_job`, `run_audio_job` and `prepare_script` keep `BUILT_IN_STEPS`; only `JobRunner` loads `installed_steps()`; no golden file moves. Report JSON/Markdown list plugins only when present; load problems reach `report.problems`; the CLI prints "Text-step plugins: …" and the existing warning line.
- (f) Conformance: every built-in step behind `guarded` passes `check_text_step(allow_ask=False)`; the example and the loaded example pass; the Hypothesis property shows the guard changes no edit; the docs test runs the page's four Python blocks and their tests; the import-hygiene subprocess test exists.
- (g) `docs/plugins.md` matches the code except the "never stop a job" sentence (M1, S1). CONTRIBUTING line (same backtick style as the file's other doc references), CHANGELOG line and `docs/baseline.md` row exist.
- (h) The tests fail without the change, by reading: the mutation test asserts the original document and the next plugin's view; the duplicate test fails without `seen`; the timeout test bounds wall time.
- (i) No licence item; the fake plugins are our own code. No unrelated change.
- (j) #666, #667, #668, #669 exist, open, milestone v1.4, lane and risk labels set; #666 is the web read-along follow-up.
- CI: three-system `ci:full` green at 6f25cd4 (`tests` on ubuntu, macos, windows pass; `CI passed` pass).
- Local run (macOS M4, worktree at 6f25cd4): fast suite (`-k "not espeak"`) 8418 passed, 6 skipped, 6 xfailed; lint-imports 3 kept, deptry clean, ruff check and format clean. Probes for M1, S1 and S2 run against the same worktree.

## Findings

### M1 (must-fix): a plugin whose attributes raise stops sci2audio from starting
`src/sci2audio/textprep/plugins.py:179-192` and `:226-230`. Only `point.load()` and `made()` are inside a `try`. The checks after them (`isinstance`, `_declares_version`, `step_problems`, `point.name != step.id`, `step.id in taken`) and `_GuardedStep.__init__` read the plugin's attributes unguarded, and `step_problems` uses `getattr(..., None)`, which swallows only `AttributeError`. A plugin with, for example, `@property def languages(self): raise RuntimeError` makes `load_plugin_steps` raise. Probe at 6f25cd4: `installed_steps(entry_points=[EntryPoint("bad-prop", "probe_mod:BadProp", ...)])` raised `RuntimeError: boom` instead of returning a `PluginProblem`. Because `JobRunner.__init__` calls `installed_steps()` (`app/runner.py:30`) and both `CliEnv.runner` (`cli.py:141`, `default_factory=JobRunner`) and the server (`web/server.py:80`) build one, one broken installed plugin makes every CLI command and the server fail at start-up. That breaks #216 criterion 2, plan §2 ("each of these becomes a PluginProblem, and the rest still load"), and the sentence in `docs/plugins.md:132`.
Fix at the root: treat the whole inspection of the made step as plugin code. Wrap everything from `made()` to building the guard in one `try ... except (Exception, SystemExit)` that becomes `_Rejected`, and read `id`, `languages`, `category`, `stage` and `api_version` once into the guard so later reads never touch plugin code. Test: add a raising-property plugin to the parametrised rejection test, plus one test that `JobRunner(installed_steps(entry_points=[...]))` (or the CLI) still starts with it installed.

### S1 (should-fix): a plugin raising a `BaseException` subclass still crashes the job
`plugins.py:171`, `:177` catch `(Exception, SystemExit)`; `plugins.py:250-251` re-raise everything but `SystemExit`, and `run_steps` catches only `Exception` (`textprep/runner.py`, the `except Exception` in the step loop). A plugin that raises `GeneratorExit` or its own `class Boom(BaseException)` at import, in its factory or in `find` therefore ends the job (load) or the run (find). Probe at 6f25cd4: both escaped. D-836's wording (Exception and SystemExit) is met, but #216 criterion 2 ("a broken plugin cannot crash a job") is not. Fix: in the loader and in the guard, catch `BaseException` and let only `KeyboardInterrupt` through (in the guard, turn the rest into `StepError`). Test: a `BaseException`-subclass plugin at load and at run time.

### S2 (should-fix): distribution metadata read outside the guard and through a deprecated lookup
`plugins.py:160-164` `_distribution` runs before the `try` and uses `dist.metadata["Name"]`. For a `*.dist-info` without a `METADATA` file, Python 3.12 returns `None` with `DeprecationWarning: Implicit None on return values is deprecated and will raise KeyErrors` (probe at 6f25cd4); once `importlib.metadata` raises, the same start-up crash as M1 follows from a damaged install of any package that declares the entry point. Fix: use `dist.name` / `dist.metadata.get("Name")` and keep the lookup inside the rejection path, so a failure gives `("", "")` or a `PluginProblem`. Test: the probe case (dist-info without METADATA) under `-W error::DeprecationWarning`.

### N1 (note): `LoadedPlugins` joins the stability promise
`api.py:55`. Plan §1 named `PLUGIN_GROUP`, `load_plugin_steps`, `PluginInfo` and `PluginProblem`; `LoadedPlugins` is the return type of `load_plugin_steps`, so exporting it is consistent, and the public `load_plugin_steps` also has a keyword `reserved`. Both are now under `TEXT_STEP_API = 1`. No change asked; the coordinator may record it with the next point.

### N2 (note): one deep copy per plugin call instead of one per run
The PR's stated deviation from plan §3. It is simpler and safer (an abandoned thread never holds a copy another plugin reads) and its cost is measured (23.9 ms on the largest paper). It needs no new decision before merge; record it in the decision log as a Claude decision.

### N3 (note): the web jobs run plugins before the read-along does
`web/server.py:80` makes a `JobRunner()`, so web jobs now run installed plugins while `web/player.py` still builds the read-along with `BUILT_IN_STEPS`; with a plugin installed, highlight and audio can drift until #666 lands. Accepted by D-836; #666 should land before the release that ships this.

### N4 (note): ordinary plugin exceptions are re-raised, not wrapped
`plugins.py:250-251` re-raises the plugin's own exception instead of a `StepError` (plan §3 said `StepError`). The runner records it with its own type and message, which the report reads better; fine as is.

## Answer expected in round 2
M1 fixed with the two tests; S1 and S2 fixed with tests or deferred to an issue each (REV-01). One fix commit, branch frozen otherwise (D-698); the critical final round needs a fresh three-system run.

Handoff (THR-07): goal: review PR #676 to merge. Done: round 1, changes requested. Next: round 2 on the author's fix commit.
