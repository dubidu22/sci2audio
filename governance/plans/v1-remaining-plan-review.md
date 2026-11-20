# Second opinion on `v1-remaining-plan.md` (12 Nov 2026, thread "Weigh the v1.0 remaining-work plan", Fable 5.1)

Checked against: KB decision log through D-95 (esp. D-45, D-48, D-50, D-52, D-54, D-55, D-57, D-61, D-63, D-69, D-80), feature list, playbook, CLAUDE.md, `.claude/rules/tests.md`, the code on `main` (af78e0b), issues #63–#80, and PyPI metadata for misaki 0.9.4, kokoro 0.9.4, imageio-ffmpeg 0.8.1, espeakng-loader (fetched 12 Nov).

## Verdict: approve with listed changes

The plan is sound: the wave order and the critical path are right, all 41 Must features map to an issue, the 18 issues are well-formed and do not overlap, and no recommendation changes a decided contract. Nine of the fifteen recommendations I accept as written; six need a correction or an addition before they become decisions (Q2 wording, Q3, Q5, Q6, Q11, Q12, Q15). Two facts the plan did not know change the shape of Q5 and Q12: imageio-ffmpeg ships no ffprobe, and the spaCy model misaki needs is not on PyPI at all. My estimate is 30 % done, the same as the plan's, but its time figure is optimistic.

## 1. Q1 to Q15

| Q | Verdict | Reason / change |
|---|---|---|
| Q1 keep D-69, batch-approve #64–#68 | **Accept** | D-69 is Colin's rule; batching approvals is process, not a contract change. Each PR still gets its own review thread. |
| Q2 footnotes read in place, "Footnote 1.", marks removed, one switch | **Accept, fix the wording** | Consistent with D-61 (1) (edits never cross blocks) and avoids the footnote-mark links D-61 left for later. But `layout/footnotes.py` puts a footnote block "in the place of the first block the notes were read in", i.e. at the column foot in reading order, not "after the block it interrupts". Record it as "where layout placed it (the column foot)". Listener-facing: inform Colin. |
| Q3 notice wording | **Change** | A caption is its own block, read as printed in its printed position, and its text already starts with its label ("Table 2: …", "Figure 1: …"). So "Table 2 is skipped. Its caption reads: …" only works when the caption follows the placeholder (tables usually have the caption above), and "Figure 1." before the caption doubles the label. Recommend: the placeholder's `replace` is one short notice naming the item through its caption's `describes` link ("Table 2 is skipped." / "Figure 1 is skipped." / "Formula 4 is skipped." / "A formula is skipped."), and the caption block is left to read as printed. One wording table in `textprep`, English only (D-50). Detail for the #64 plan. |
| Q4 textprep owns the utterance cutter; line breaks are spaces in the cutter, not edits | **Accept** | Works on `ScriptPiece`s (core), so voices never see a `Document`; no core change. Add to the #63 plan: Kokoro has an input-length limit per call, so a very long sentence needs a fallback cut at clause marks. |
| Q5 imageio-ffmpeg with PATH fallback | **Accept, with two corrections** | Verified: imageio-ffmpeg 0.8.1 (BSD-2 wrapper) bundles **ffmpeg 9.0 only, no ffprobe** (52 MB on macOS arm64). #69's "read back with ffprobe" must instead parse `ffmpeg -i` / `ffmpeg -f ffmetadata -` output or use a Python reader. The binaries are GPL builds, which is fine for GPL-3.0-or-later; the PR names the build's licence per platform and confirms libmp3lame and aac are compiled in. Alternative not chosen: PyAV (in-process, larger surface). risk:high dependency: inform Colin. |
| Q6 chapter = level-1 section; front matter = first chapter titled by document title; references deselected | **Accept, two notes** | `Document` has no title; use `Content.metadata` (Source.title) with the file name as fallback. References are handled twice (TP-06 step removes them by edits in #64, chapter deselection in #70): the #70 plan must say which wins in the report (recommend: steps run on the whole document; the chapter filter applies when utterances are cut, and the report marks edits in deselected chapters as not spoken anyway). Listener-facing: inform Colin. |
| Q7 server-rendered HTML + Jinja2 + little plain JS + SSE | **Accept** | Fits D-45 (one browser UI) and AQ-01. Licences: FastAPI MIT, uvicorn BSD-3, Jinja2 BSD-3, python-multipart Apache-2.0 (file upload); SSE via `StreamingResponse` needs no extra package. The #78 player will be the one page with real JavaScript; still no build step. Architectural: inform Colin. |
| Q8 pause defaults 2.0 / 1.0 / 0.6 / 0.5 s as output settings | **Accept** | Settings with defaults; D-61 left lengths open on purpose. Implementation detail for the #69 plan; no chat line needed. |
| Q9 read-along on block text, JSON versioned and owned by output | **Accept** | Matches OU-02 and D-61 (6); the page overlay waits. Architectural (a file format): inform Colin in one line. |
| Q10 keep German UI | **Accept** | AQ-02 is a Must; keeping it is not a decision. No chat line. |
| Q11 `sci2audio.testing` beside `app` in the layers | **Accept, one addition** | Layer line becomes `sci2audio.app \| sci2audio.testing`. The suite must not import pytest or hypothesis at module import, or they become run-time dependencies of the wheel (deptry will flag it): write it as plain callables that the tests wrap, or put it behind an optional extra. Layer contract: critical, inform Colin. |
| Q12 misaki spaCy model, espeak-ng | **Accept, with facts that narrow it** | Verified in misaki 0.9.4 `en.py`: `G2P.__init__` calls `spacy.cli.download("en_core_web_sm")` whenever the package is not installed: a network call the user did not start. **`en_core_web_sm` is not on PyPI** (explosion hosts it on GitHub releases), and PyPI rejects direct-URL dependencies, so the "pinned wheel" branch is out. It must be part of the user-started voice setup: fetch the wheel (MIT) from explosion's release, unpack into the cache and put it on `sys.path` (so `spacy.util.is_package` finds it) or install it into the environment; the #18 plan picks one and tests the no-network path. espeak-ng arrives through the `espeakng-loader` wheel (misaki[en] dependency, GPL-3.0, bundled binaries): no system install, but a licence entry. Also: `huggingface_hub` checks for updates even when the model is cached; set `HF_HUB_OFFLINE=1` except during the user-started download, or VA-04 fails the "network blocked" test in #71. Hard rule: inform Colin. |
| Q13 Colin's own steps | **Accept** | Add two items: retiring the hosted demo (playbook phase 1, never recorded done) and the `sci2audio.com` homepage URL in `pyproject.toml`. Tell Colin now. |
| Q14 #47 into v1.0 | **Accept** | Test-only. |
| Q15 earlier step in the registry wins; set-aside listed; `ask` reads the original | **Accept, one rule added** | "Earlier wins" only works if the registry is ordered **coarse to fine**: whole-block removals (furniture, reference list, placeholder notices, footnote handling) before rules inside a block, else a URL edit inside a reference block would set aside the block's removal. Write that ordering rule into the #63 plan. And: nothing in #77 answers `ask` edits (UC-04 is Should), so no v1.0 built-in step may emit `ask`; the runner and report support it. Part of the text-step contract: settle at #63 plan approval, one line to Colin. |

No recommendation silently changes a prior decision. Two come close and should be named as refinements when recorded: Q2 reads footnotes at the column foot (TP-05 said "footnote marks and footnote text" without a place), and Q11 adds a layer to the D-46/D-63 contract.

## 2. Waves, critical path, missing Must features

- **Critical path is right**: #63 → #70 → #71 → #76 → #77 → #78/#79 → #80, with #18 and #69 joining at #71. #76 needs only #70, so it can run beside #71, which the plan already allows.
- **Wave 1 is right**: #63, #18 and #69 touch different lanes and have no shared file. Start #47 first (it is a one-PR test fix and the nightly depends on it).
- **#63 is large** (interface, categories, registry, runner, cutter, furniture step, conformance suite, regression harness). Let the authoring thread split it into two PRs if it wants (interface + registry + runner + furniture step + harness, then the cutter); not required.
- **#39** says "every new sentence is checked by Colin against the PDF". Under D-80 the review thread does that check by reading the PDF; say so when the plan is approved.
- **All 41 Must features map to an issue** (I re-counted the list: IN 4, TP 11, FX 2, UC 3, VA 5, OU 2, WI 3, AQ 4, PE 7 = 41). One criterion is missing from the issues, not the list: **VA-02 install size on Linux**. The PyPI `torch` wheel for Linux pulls the CUDA libraries (several GB) unless a CPU index is used, which no PyPI dependency can express. WI-01's one-command install and VA-02 collide there; the #18 plan (or #80) must decide: document a `--index` flag for Linux, or accept the size. Add it to #18's acceptance criteria.
- D-47's "everything for offline use" download option is not named anywhere; it is the voice download of VA-03 plus the spaCy model of Q12. Mention it in #18 so it is not forgotten.

## 3. The 18 issues

Spot-checked all 18. Each has a feature ID, a problem, testable acceptance criteria, dependencies and the critical flag where D-69 applies. No overlaps found. Four small things:

- #69 "read back with ffprobe" (see Q5).
- #5 stays open as the PDF part only; its text still describes all formats. Update it when #73/#74 start.
- #72 and #76 both offer a voice download with consent; both should call the one download in `voices` (#18). Fine as written, but the #18 plan should expose that function.
- #64's corpus test ("no formula or table text in the script") will only be meaningful once #70 exists; until then it runs on `apply_edits` output, which is enough.

## 4. Architectural (one chat line to Colin each) versus implementation detail

- **Inform Colin:** Q2 (footnote placement), Q4 (textprep owns the cutter), Q5 (ffmpeg source and licence), Q6 (what a chapter is), Q7 (interface technology), Q9 (read-along file owned by output), Q11 (layer contract), Q12 (no-network handling of the spaCy model and HF cache), Q13 (his own steps, as a heads-up), Q15 (edit precedence, when the #63 plan is approved). Q1 and Q14 are process: one line together.
- **Leave to the implementing thread's plan:** Q3 (wording), Q8 (pause defaults), Q10 (no decision).

## 5. Estimate

- **30 % done** (range 25–35 %), agreeing with the plan. By feature it is lower, by PR effort higher; the user-facing half has no code.
- **Time:** the plan's 2.5–3.5 thread-days assumes one review round per PR. Layout PRs averaged two to three rounds, and the voice (PyTorch, misaki, HF cache), ffmpeg and the accessible interface are integration work with more surprises than layout rules. I expect **4 to 6 thread-days** before #80, plus Colin's hands-on steps, which cannot run in parallel with much.
