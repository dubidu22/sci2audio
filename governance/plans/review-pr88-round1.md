# Review of sci2audio PR #88 (Kokoro English voice, #18), round 1

Reviewed head `623e70f` against the approved plan (`plans/issue18-kokoro-plan.md`) and decisions D-121 to D-127 (coordinator post 12 Nov 22:52:31Z).

## Verdict

Request changes: one blocker (merge conflict with main after #85), three should-fix items, four nits. The design matches the plan and the decisions; the code is careful.

## What I checked and ran

- `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`: clean.
- Fast suite with `HYPOTHESIS_PROFILE=nightly`: 604 passed.
- Real model, network blocked inside the tests (this container, Linux CPU): models fetched with the PR's own `prepare_models.py` / `download_voice_files` (all sha256 checks passed), then `pytest -m slow tests/integration`. Result: 4 passed in 93 s (two voices into WAV, conformance suite with all 28 voices, speech-recognition round trip **WER 0.012** over 249 words, the same as the author's number). No language-mismatch or download warnings from kokoro/misaki, only deprecation warnings inside torch and misaki.
- Pins in `uv.lock`: kokoro 0.9.4, misaki 0.9.4, torch 2.15.0 (CPU index on Linux), spaCy 3.8.18, espeakng-loader 0.2.4. `requires-python >=3.12`.
- Abogen MIT notice with revision `1807822f` at the top of `types.py`, `engine.py`, `errors.py`, `kokoro_engine.py`.
- kokoro 0.9.4 source: with `config` and `model` given as paths, `KModel` never calls `hf_hub_download`; `load_single_voice` skips it for `.pt` paths. misaki 0.9.4 `en.py:500` calls `spacy.cli.download` only when `is_package` is false, which the adapter checks first.
- `HF_HUB_OFFLINE=1` and `PYTORCH_ENABLE_MPS_FALLBACK=1` set by `prepare_environment`, called before torch/spaCy/kokoro import. WAV is 16-bit mono 24 kHz via `wave`. espeakng-loader ignore in the licence job with a comment.
- Layer plants: `import sci2audio.testing` in `app`, `voices/wav.py`, `core` → BROKEN (good); in `cli.py` and `web/__init__.py` → KEPT (finding 2).
- 27 hand mutations of `download.py`, `kokoro_engine.py`, `wav.py`, `runtime.py`, `testing/voices.py`: 22 killed, 5 survived (findings 3 and nit 4; `_pipelines.clear()` is an equivalent mutant).
- CI on `623e70f`: green on Linux, macOS and Windows.

## Blocker

1. **Conflicts with main.** #85 (output) merged as `7ce16dc`; PR #88 now conflicts in `THIRD_PARTY_LICENSES.md` and `docs/baseline.md`, and `pyproject.toml` / `uv.lock` both changed. Merge main into the branch (no force-push), re-lock with `uv lock`, and keep both sets of rows.

## Should fix

2. **D-114 is not enforced while this PR is the first to add `sci2audio.testing`.** The layer line lets `cli` and `web` import `sci2audio.testing` (planted imports in `cli.py` and `web/__init__.py` stay KEPT). D-114 says cli/web never import testing; #83 adds a `forbidden` contract for it, but the merge order is not fixed. Add the same contract here, word for word as in #83 (`name = "Nothing in the program imports the conformance suite (Q11)"`, `source_modules = ["sci2audio.cli", "sci2audio.web"]`, `forbidden_modules = ["sci2audio.testing"]`), so whichever merges second has a text-only conflict.
3. **Two repair paths of the download are untested** (mutants survived):
   - `_in_place` without the size check survives: no test shows that `missing_files` reports a voice file of the wrong size (for example a truncated `kokoro-v1_0.pth`), so `create_kokoro_engine` would load it.
   - Removing `if target.exists(): shutil.rmtree(target)` in `_unpack_wheel`, or replacing the `RECORD` check with `path.is_dir()`, both survive: no test has a spaCy folder that exists but is damaged (no `RECORD`). Without the `rmtree` the rename onto a non-empty folder fails on every rerun, so the download could never repair it. Add a test: damaged spaCy folder in place → the download replaces it; and a test for `missing_files` with a wrong-size file.
4. **The "never goes online" guarantee depends on misaki internals, but misaki is not bounded for users.** Our lock pins misaki 0.9.4, but `uv tool install sci2audio` resolves from published metadata, where kokoro only asks for `misaki[en]>=0.9.4`. A later misaki that loads a different spaCy model or downloads in another place would go online on first use. Add `misaki[en]>=0.9.4,<0.10` as a direct dependency (with a `deptry` DEP002 ignore and a comment saying why), or explain why this is not needed.

## Nits (fix or answer; anything deferred gets an issue)

5. **No cap on bytes per file.** `_fetch_with_requests` writes until the server stops; a wrong or hostile response fills the disk before the sha256 check. Stop with `DownloadError` once more than `file.size` bytes arrive (one line in `on_bytes` or the fetch).
6. **Hosts.** `https://huggingface.co/.../resolve/...` answers with a redirect to Hugging Face's CDN (seen here: `/api/resolve-cache/...`; large files go to an LFS/Xet CDN host). The plan test "only the two pinned hosts" is true for listed URLs only. Say in the `download.py` docstring (and later on the consent screen) that Hugging Face may redirect to its CDN.
7. **`sys.path.insert(0, …)`** puts a user-writable folder before the standard library. The folder only needs to be findable; `append` is enough and cannot shadow anything (the test asserting `sys.path[0]` changes with it).
8. **Unsafe-path test covers `..` only.** The mutant dropping the absolute-path check survives (zipfile also strips leading slashes, so it is defence in depth). Add an entry like `/abs.py` to the unsafe-wheel test.

## Not findings

- pip-audit skipping `torch 2.15.0+cpu` is acceptable (coordinator's note).
- Rebase with #83 (`testing/__init__.py` docstring, layer line, reuse of #83's `no_network`) is already listed in the PR body.
