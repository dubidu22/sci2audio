# Review of KB PR #33 (D-192 to D-209, sci2audio #76), round 1

Reviewed head a8ce19b against main a6b26a2, the plan `plans/issue76-server-plan.md` §12, the coordinator's decision post (2026-11-13T02:14:57Z) and sci2audio PR #107 at ffbaef8.

## Passes

- Eighteen rows, D-192 to D-209, question N of §12 is D-(191+N) in every row; each row's §12 reference matches.
- All "Decided (Claude)", 13 Nov 02:15 UTC under D-80, "Colin informed ... 2026-11-13T02:14:57Z" in every row.
- Log order: 209 down to 192, then 166; no duplicates, no order breaks (D-167–175 come with KB PR #31).
- D-136 "refined by D-199" and D-101 "extended by D-195 and D-206" are in the status cells only; nothing else in those rows changed.
- D-208 records what happened: #71 (PR #99, 3ef8ac5) merged first, so the audio jobs are in the one server PR.
- D-205 matches the import-linter contract in PR #107 (core, five stages, app, testing; cli left out for `sci2audio ui`).
- D-206 versions match `uv.lock` in PR #107 (FastAPI 0.162.5, Starlette 1.10.0, uvicorn 0.54.0, Jinja2 3.1.6, python-multipart 0.0.33, pydantic 2.14.3, Schemathesis 4.33.4, httpx 0.28.1).
- D-207's test exists (`tests/unit/test_web_launch.py`), D-198's 411 exists (`web/limits.py`), D-199's default folder (`web/config.py`).
- PR body refers to PR #107 with a plain link; no "closes/fixes/resolves" anywhere.

## Must fix

1. **D-195 does not name the FastAPI version range.** It says "the current FastAPI (0.162.x)"; the code pins `fastapi>=0.162.5,<1` and the telemetry test is what guards that upper range. Add the range to D-195 (for example "`fastapi>=0.162.5,<1`, the test fails if a later release changes the switch; see D-206").
2. **D-194 lists fewer response headers than the code sends.** `web/security.py` also sends `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Resource-Policy: same-origin`, and the CSP is the full policy of plan §2.5, not only `default-src 'self'` with `frame-ancestors 'none'`. The PR body says details are recorded as built where they go beyond the plan, so add the two headers and say the CSP is the full one (or quote it).

No should-fix items.

## Round 2 (result)

Both fixed in f2ac084 (checked by word diff): D-195 now names `fastapi>=0.162.5,<1` and the guarding test; D-194 quotes the full CSP and adds COOP and CORP. Main (87e5aa8, KB PR #32) merged in as 0b13a34: IDs read 226…192 then 166, no duplicates or order breaks; the diff against main is the 18 rows plus the two status-cell notes. Squash-merged as 4bfe53d on 13 Nov 2026.
