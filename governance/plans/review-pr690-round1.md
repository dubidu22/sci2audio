# Review PR #690, round 1 (batch B-P2, #684)

Thread: review-plugins-b-p2 (Opus 5.5). Head reviewed: f7d8898 (base caecf7a, up to date with main). Date: 2026-11-20.
**Critical: yes** (CRIT-01: a safety mechanism of the text-step plugin interface; `risk:high` set). Plan `plans/plugins-b-p2-plan.md`, approved as D-845.

**Verdict: changes requested** (1 must-fix, 0 should-fix, 4 notes).

## Verified

- (1) Scope: only `src/sci2audio/textprep/plugins.py`, `tests/unit/{broken_text_plugins,hanging_on_import,test_textprep_plugins,test_app_plugins}.py`, `docs/plugins.md` and `CHANGELOG.md` change. `PLUGIN_LOAD_TIMEOUT = 30.0` is a module constant; loading is sequential with one limit per entry point; `installed_steps` gains `load_timeout: float | None = None`, read at call time; `load_plugin_steps` reads the constant at call time through the private `_load`. `sci2audio.textprep.api` is untouched. Labels `risk:high`, `lane:textprep`, `lane:docs`. No new dependency (licence: none).
- (2) Guard: `_made` (plugins.py:254) runs `point.load()`, the factory, `isinstance`, `_declares_version` and `_GuardedStep.__init__` (the attribute reads) inside `_in_worker` (plugins.py:188). A daemon thread; `join(timeout)`; `is_alive()` then decides. A worker that ends between `join` returning and `is_alive()` has already written `result` (the write comes before the thread stops), so it counts as a success, which is correct. A worker that finishes or raises after the caller gave up writes into a dict nobody reads; `work` catches `BaseException`, so no "Exception in thread" output. `KeyboardInterrupt` in `_made` passes its `except (_Rejected, KeyboardInterrupt): raise` and is re-raised in the caller (`_step` catches only `_TimedOut`). A real Ctrl+C hits the main thread in `join`. Same abandoned-thread semantics as `find`. The checks left in the caller's thread are M1.
- (3) `find` through `_in_worker`: the outcomes are the same as at caecf7a. Timeout gives `StepError` (same message); `KeyboardInterrupt` and `Exception` are re-raised as the same object; `SystemExit` and other `BaseException`s become `StepError`; the thread name is unchanged; the `type: ignore` is gone because `_in_worker` is generic. The #676 tests (rejection parametrisation, M1, S1, the find-guard and Ctrl+C tests) are unchanged in the diff (only additions) and pass.
- (4) T5 pins `str(inspect.signature(load_plugin_steps))` and `api.__all__`.
- (5) T1 to T7 exist under the node IDs named in the plan. T1 to T3, T6 and T7 fail on caecf7a: T1 to T3 through the unknown `load_timeout` keyword and the 5 s wait, T6 and T7 through the missing constant and the 5 s wait. T4 guards a behaviour that already held (the PR body says so). Timing: the limit is 0.2 s, the budget 3 s and the fake hang 5 s. The plugin that must still load (`example_text_plugin`) is imported at test-module import, so its load in the worker is a `sys.modules` lookup. `Event.wait` returns once it has been notified, even if the next test's fixture clears the event first, so an abandoned thread cannot carry over into the next test. I see no flake path. Three-system `ci:full` run 44791680229 is green on f7d8898 (`tests` on ubuntu, macos and windows).
- (6) `docs/plugins.md` (the new paragraph at :99 and the "Not loaded" bullet) and the CHANGELOG Fixed line describe the load limit as coded. The `docs/plugins.md:99` claim that the attributes run in the worker is only true once M1 is fixed.
- (7) Local, macOS M4, worktree at f7d8898: ruff check clean, ruff format --check clean (385 files), lint-imports 3 kept, deptry clean, fast suite `-k "not espeak"`: 8592 passed, 6 skipped, 6 xfailed.
- Comments: no narrating comment or review tag. The `(#684)` and `(D-845)` references give the reason, in the module's existing style.

## Findings

### M1 (must-fix): the checks left in the caller's thread still run plugin code, unguarded and with no time limit (kind unguarded-plugin-code, second time)
`src/sci2audio/textprep/plugins.py:245-250`, with `src/sci2audio/textprep/steps.py:150-169`. The plan said that `step_problems`, the name check and the `taken` check "run no plugin code". In fact they read the guard's copies. Those copies are the plugin's own objects, so the checks run the plugin's `__repr__` (`{step_id!r}`, `{version!r}`), `__ne__` (`version != TEXT_STEP_API`), `__eq__` and `__iter__` (languages), and `__hash__` and `__eq__` (`step.id in taken`, `point.name != step.id` for a str subclass). They run in the caller's thread, outside any `try` and outside the time limit. Probes at f7d8898, with `installed_steps(entry_points=[...], load_timeout=0.2)`:
- `id` is a lazy-translation-like object (not a str) whose `__repr__` raises. `RuntimeError` escapes `installed_steps` at once, so `JobRunner()` and with it every CLI command and the server fail at start-up. A plugin written with a lazy `gettext` proxy as its id hits this without any malice.
- `api_version` is an object whose `__ne__` blocks. `installed_steps` takes 5.0 s with a 0.2 s limit: the hang this PR exists to bound.

This is the kind of #676 M1 and the edge noted as N1 in #676 round 2. Under REV-05 it is now fixed at the root, together with a check that stops it from coming back.

Fix: run `step_problems`, the entry-point-name check and the `taken` check inside `_made`, inside its `try`, so that they run in the worker. `taken` is only read there; it is changed only in the caller after the worker returns. Any exception then becomes `_Rejected` and any hang meets `load_timeout`. The messages stay the same. This is a small move against the plan text but within D-845 ("attribute reads run in the same worker-thread guard"); please state it in the fix answer.

Tests (the check):
- add to the parametrised rejection test a plugin whose `id` is a non-str object with a raising `__repr__` (expect a `PluginProblem`);
- add to the T1 to T3 family a plugin whose `api_version.__ne__` blocks on `HANG` (expect "took longer than 0.2 s to load" in under 3 s).

### N1 (note): copied values still reach plugin code at run time
After validation, `id` may be a str subclass and `languages` a tuple subclass. `handles()` (`steps.py:141`), the thread name `f"text step {self.id}"`, the registry and `given != document` (when the plugin planted an object in its copy) then run plugin dunders in the job's thread, outside the time limit. This is not on the start-up path, so it is not #684. Closing it means storing exact built-in copies (`str`, `tuple` of `str`) once validation passes, and comparing the copy with a guard of its own. I suggest that the coordinator opens a follow-up Issue for it. No change asked in this PR.

### N2 (note): several entry points in one hanging module each wait the full limit
An abandoned loader thread keeps the module's import lock. A package that declares three steps in one module whose import hangs (for example, a model download at import with no network) therefore delays every command by 90 s, not 30 s. The same happens with a shared parent package. The PR body states this, and it meets plan §2 and #684. A cheap later improvement: reject at once any later entry point whose top-level package timed out. That is a candidate follow-up Issue for the coordinator, not a change here.

### N3 (note): a Fixed line for a feature that has not been released
The plugin interface is still under Unreleased (Added), so the bug in the Fixed line never shipped. The Added line's "takes longer than 60 s" now reads as if it covered loading too. The plan prescribed the line; at release time it may be folded into the Added line ("takes longer than 30 s to load or 60 s per document"). No change asked.

### N4 (note): Ctrl+C on Windows during a hanging load
On Windows, CPython may not wake a lock wait with a timeout on Ctrl+C, so Ctrl+C during a hanging plugin load can take effect only when the 30 s limit ends. Before this PR it took effect at once, as long as the hang was in interruptible Python code. `find` already behaves this way with its 60 s limit. No change asked; mention it if the docs ever describe Ctrl+C.

Handoff (THR-07): goal: PR #690 to merge. Done: round 1 found 1 must-fix (the caller-thread checks) and 4 notes. Next: the author pushes one fix commit with M1 and its two tests. Round 2 checks that diff and Linux CI; before merge a green three-system `ci:full` run on the final head is needed (CRIT-02, D-580).
