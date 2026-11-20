# Review of KB PR #24 (D-121 to D-127), round 1

Reviewed 12 Nov 2026 against the coordinator's decision post (2026-11-12T22:52:31Z), plan `plans/issue18-kokoro-plan.md` ("Decisions in this plan", 1 to 7) and sci2audio PR #88 (head 623e70f).

## Checks that passed
- Numbering: main ended at D-120 (deabf4f); the PR adds D-121 to D-127 with no gap, newest first, branch based on deabf4f. One file changed, table rows keep six columns.
- Each row matches its plan decision: D-121 = 1, D-122 = 2, D-123 = 3, D-124 = 4, D-125 = 5, D-126 = 6, D-127 = 7. All seven say "Decided (Claude)" under D-80.
- Facts checked in PR #88: Kokoro revision f3ff3571 (`voices/download.py`), 28 English voice packs, total about 355 MB (327.2 MB weights + 12.8 MB spaCy wheel + 28 voices); `.part` then rename; spaCy wheel unpacked into a temporary folder that is renamed; `prepare_environment()`, `HF_HUB_OFFLINE=1` (`voices/runtime.py`); `spacy.util.is_package` guard raising `ModelNotFoundError`; `[tool.uv.sources]` CPU index on Linux and `--torch-backend cpu` in README; `requires-python = ">=3.12"`, `torch>=2.6`, pipx note; sci2audio Issue #87 exists (v1.0 milestone); `espeakng-loader` in `--ignore-packages` with a comment; `PCM_FLOAT32`, `VoiceInfo`, `api_version`, `listVoices()`, BCP 47 tag, `sci2audio.testing.voices`; README says Apple chips only.

## Findings and fixes (pushed by the review thread, commit 9f6bb1e)
1. D-125 had no chat line: the 22:52:31Z post lists six decisions and leaves out the contract shape. Fixed: the coordinator posted the line; D-125's "Colin informed" time is now 2026-11-12T23:15:37Z (decision time stays 22:52 UTC).
2. Missing forward pointers. Fixed: D-104 "refined by D-121 and D-122"; D-52 "refined by D-125"; D-48 "refined by D-123 and D-127"; D-47 "refined by D-123 and D-124", in the status column as earlier entries do (e.g. D-103 → D-114).

Nothing deferred. Verdict: merge.
