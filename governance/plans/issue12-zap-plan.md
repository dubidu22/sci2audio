# Issue #12: OWASP ZAP baseline scan (AQ-03) — plan

Thread: "Add OWASP ZAP baseline scan". Base: main 47c86fb (after #76–#79). Lane: infra. Item 27 of the v1.0 plan.

Issue #12 asks for one ZAP baseline scan of the running local server before v1.0, with no high or medium findings, and the findings recorded in the release Issue. `docs/release-checklist.md` lists it as a manual step marked *(not yet possible)*.

## 1. What a trial run already shows

I ran the stock `zap-baseline.py` (image `ghcr.io/zaproxy/zaproxy:stable`, digest `sha256:9624669d…f328af`) with `--network host` against main 47c86fb. The server had the fake voice, one uploaded PDF, a finished script job and a finished audio job, and the start cookie was sent as a header. The spider found 26 URLs. 59 passive rules passed, and none failed.

| Rule | ZAP risk | Where | What it is |
|---|---|---|---|
| 10027 Suspicious comments | Informational | `static/app.js`, `static/player.js` | The word "address" or "where" in a code comment. Nothing is leaked. |
| 10029 Cookie poisoning | Informational | `GET /language?language=en&back=…` | The parameter decides the cookie's value. `known_language()` only ever writes `en` or `de`, never the request's text (D-288). |
| 10031 User-controllable attribute | Informational | `/documents/{id}?category=…` | The query value is echoed into an attribute. Jinja2 autoescape covers it, and CSP `script-src 'self'` covers it too. |

The spider also tried `back=https://zap.example.com`. `local_path()` turned it into `/`, so the redirect stayed on this server (rule 10028 passed).

So the server is clean today. The work is to make the scan repeatable, to make it cover the states a spider can't reach by itself, and to decide how its result gates work.

## 2. Proposed design

**Driver.** A new script, `scripts/zap_scan.py` (`uv run python scripts/zap_scan.py`), does five things:

1. It starts the real server in-process on 127.0.0.1, the way `tests/browser/conftest.py` does. It uses a temp work folder, the fake voice, a fake voice download and the small download plan, so it needs no models and makes no network calls.
2. It starts ZAP in Docker as a daemon proxy (`zap.sh -daemon`, `--network host`). Host networking is needed because the server only answers `Host: 127.0.0.1:<port>` (D-194).
3. It drives the main flow with Playwright Chromium through that proxy (`--proxy-bypass-list=<-loopback>`), like a person would. ZAP then passively scans every real request and answer, including the upload POST, the job POSTs, the SSE streams, the MP3 range requests and the language switch.
4. It runs ZAP's spider from `/` with the session cookie, and waits for the passive scan to finish.
5. It pulls the alerts over ZAP's local JSON API using `httpx`, which is already a dependency, so it adds no new Python dependency. It writes `zap-report.json`, `zap-report.html` and a short `zap-summary.md`, and exits non-zero on failure.

The judging logic (alerts against the accepted list) is plain Python. It gets unit tests in the fast suite, `tests/unit/test_zap_scan.py`, built on recorded alert JSON. The scan itself never runs inside pytest, because it needs Docker.

**Accepted findings.** `scripts/zap/accepted.toml` holds one entry per accepted alert: the rule id, a URL regex (kept narrow), the risk, the reason and the decision number.

**Workflow.** A new `.github/workflows/zap.yml` runs on Linux only. It pins the image by digest, uploads the reports as an artifact, uses `permissions: contents: read` and pins actions by SHA (zizmor clean).

**Docs.** The release-checklist line becomes "the ZAP workflow's last run on main is green; paste its `zap-summary.md` into the release Issue". `THIRD_PARTY_LICENSES.md` gets a row for ZAP (Apache-2.0, CI tool only, never shipped). The README or CONTRIBUTING gets a short "run it yourself" note.

## 3. Questions and recommendations

**Q1. Where does the scan run?**
- A. Its own workflow, run on PRs that touch `src/sci2audio/web/**`, `src/sci2audio/app/**`, `scripts/zap_scan.py`, `scripts/zap/**`, `pyproject.toml`, `uv.lock` or the workflow itself, plus nightly (after the 02:17 run) and on manual dispatch.
- B. Nightly and manual dispatch only.
- C. Every PR.
- D. By hand before the release only, as the issue wrote it.

**Recommend A.** A header or template change is caught in the PR that makes it, and other PRs don't pay for the 1.2 GB image pull and the roughly 5 minute scan. The issue's own note ("if a hosted web version ever comes, move this into CI") anticipated this; CI is cheap now that it can run.

**Q2. How is the server driven?**
- A. ZAP as a proxy, with Playwright driving the real flow through it.
- B. Stock `zap-baseline.py` with the spider only.
- C. The Automation Framework with a fixed list of GET URLs.

**Recommend A.** B and C never see the answers to the upload or job POSTs, and the spider's own POSTs are refused with 403. That refusal is correct behaviour, since the spider sends the cookie without an `Origin` header, but it means the upload flow goes unscanned. A is the only option that covers the upload flow the way a person uses it. It costs about 150 more lines than B.

**Q3. Which pages and states are covered?**

Everything below is visited in English and again in German, after the language switch's GET form (D-321):
- `/start` with its 303 answer and `Set-Cookie`, to check the cookie flags.
- `/` while empty, and again with documents.
- Opening a file through the upload form (a generated PDF), and opening pasted text.
- The document page while the analysis runs and after it has finished, including the `category`, `chapter` and `text` parameters.
- The voice page before the voice is installed, the fake download, and the page after it.
- The script job page and the audio job page, including their event streams.
- The Listen page with an audiobook, its MP3 range requests and `audiobook.json`.
- The Listen page with nothing to play.
- `/privacy`.
- `/openapi.json`.
- Every GET API endpoint.
- A request without a cookie (the 401 page, in both languages through `Accept-Language`).
- A request with a wrong `Host` (421).

After the flow, the spider runs from `/`.

**Recommend this list.** It is every page template (`base`, `index`, `document`, `job`, `listen`, `missing`, `privacy`, `voice`) in both languages, and every answer the middleware writes itself.

**Q4. What fails the scan?**
- A. Any alert of risk High or Medium fails, as the issue asks. Any Low alert also fails unless `accepted.toml` names it with a reason. Informational alerts are listed in the summary but never fail. An accepted entry that matched nothing is reported as stale but doesn't fail, so a ZAP update can't turn the check red by itself.
- B. Only High and Medium fail.

**Recommend A.** A Low alert is cheap to look at now, and the list then documents why each one is fine. The three informational alerts above are explained in the summary. They are not added to the list, because they never fail.

**Q5. Does a failure block merges?**

**Recommend this:** the ZAP workflow is not added to the required `CI passed` job, because it is path-filtered and a skipped required job blocks merging. A red ZAP check on a PR is a must-fix in its review. The review threads already require green checks, and I'll add a line to the review checks memory. A red nightly run gets an issue with milestone v1.0 (or the next milestone after v1.0). At release, the checklist requires the last run on main to be green.

**Q6. How are findings handled?**

**Recommend this:**
- A real Medium or High finding is fixed in this PR if small (a header, an escape), otherwise it gets an issue with milestone v1.0 and the scan stays red until it is fixed. It is never accepted away.
- A Low finding is fixed, or accepted in `accepted.toml` with a reason and a decision number.
- The scan results go into a comment on #12 when the PR is ready, and into the release Issue at v1.0.
- Hardening that ZAP doesn't flag (for example `Permissions-Policy`, or COEP for the Spectre rule, if the pinned ZAP doesn't raise them) stays out of this PR. If a rule raises it, it is fixed here.

**Q7. How is the image pinned and updated?**

**Recommend this:** pin `ghcr.io/zaproxy/zaproxy` by digest in the workflow, with the version as a comment, and pass it to the script through `--image`. The script's default is the same digest. Bump it by hand: a release-checklist line says "ZAP image updated in the last 3 months". ZAP rule 10116 ("ZAP is out of date") reminds us too. Dependabot can't follow a digest inside a workflow's `docker run` line, so I'd rather not pretend it can.

**Q8. Running it locally.**

**Recommend this:** it is supported on Linux with Docker. It also works on macOS with Docker Desktop 4.34 or later once host networking is turned on. The script checks for Docker and prints a clear message if Docker is missing or the proxy port can't be reached. CI on Linux remains the place of record.

**Q9. Is this critical?**

**Recommend this:** not critical. It changes no layer contract, core dataclasses, golden files or app code, unless a finding needs a fix. Labels: `testing`, `lane:infra`, not `risk:high`. It adds no Python dependency. The Docker image pull is a CI download like `playwright install`, and the app and the tests stay offline. The decisions still go into the KB log.

## 4. Tests and checks

- Unit tests (fast suite) for the judging logic:
  - High or Medium always fails.
  - Low fails unless accepted.
  - An accepted entry matches only its rule and URL regex.
  - A stale entry is reported.
  - A malformed `accepted.toml` is refused with a clear message.
  - The summary is written.
- The `zap.yml` run on the PR itself is the end-to-end test.
- Before the PR: `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`, the fast suite, `pytest -m browser`, `zizmor --offline .github/workflows`, and one local scan whose report is attached to the PR.

## 5. Size and order

About 450 lines: the script, the workflow, about 120 lines of tests and the docs. There is one code PR, `ci: OWASP ZAP baseline scan of the local server (#12)` with `Closes #12`. After it, a KB PR records the decisions with the numbers the coordinator assigns (D-364 onward; Q1–Q9 would be D-364–D-372 in order). Because KB PRs #38–#45 are queued ahead, it will merge main and keep the numeric order.
