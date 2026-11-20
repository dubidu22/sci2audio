# Review PR #288, round 1 (core, textprep, web: a code block is a placeholder read as one notice, #280)

Head reviewed: a55faab (base main d91a074, up to date). Reviewer: review thread "Review code block placeholder PRs".
Plan: plans/issue280-code-blocks-plan.md (D-542 to D-546; PR order deviation D-549).

## Verdict
Approve and merge. No must-fix in this PR. One player finding (F1) is fixed in #289, where a PDF can first make a code block and the browser test lives.

## What I ran myself
- ruff check, ruff format --check, lint-imports, deptry: clean.
- Fast suite (`-m "not slow and not benchmark and not browser"`, HYPOTHESIS_PROFILE=ci, -n 4): 4,296 passed, 1 skipped (Windows-only junction test).
- Browser suite (Chromium 1243): 51 passed.
- CI on a55faab: every check green (tests on Linux, macOS, Windows; browser; lint and layers; security; licences; CodeQL; ZAP).
- Spoken output: `sci2audio script --chapters all --ignore-settings` on all 13 corpus files (8 papers, 1 EPUB, 2 Markdown, 2 text), main vs PR: all 13 .script.txt byte-identical.

## Checks against the coordinator's list
- No read script changes: confirmed (13/13 identical). Golden diffs: only the empty "Code blocks" report row (3 papers) and the CLI help line. Regression cases: one new each (en `code-block`, de `de-notice-code-block`), none changed.
- Category switched off: probed six code blocks (citations "[1]", "(Smith, 2019)", "et al. (2019)", "e.g.", "5 %", "mg-\nper-kg", "10^3", "1.5e-3") in en and de. On: one notice, no other step proposes any edit inside the block (no set-aside noise in the report). Off: read exactly as printed, line breaks as spaces, no citation, link, unit, abbreviation or hyphen edit. Note: "as printed" is not quite "as today" for the seaborn listing, which main reads with the notation step ("g equals ..."); measured in the #289 review, where code blocks first exist.
- Wording: "A code block is skipped." / "Ein Codeblock wird übersprungen." (wording.py, both tables), reason "this code block is not read; a short notice is read instead (D-55)".
- Steps that list placeholder kinds: notation.SKIPPED_KINDS, links.SKIPPED_KINDS, hyphens.SKIPPED_KINDS include CODE; abbreviations and units use `is_placeholder`; citations and footnotes edit only prose kinds. Core `Document` caption check uses `is_placeholder`, so a caption may describe a code block (needed for #281).
- Settings: stored as `switched_off`, so the new category starts on for people with saved settings too.
- Player: notice box with `<pre class="code" translate="no"><code>`, line breaks kept (`strip("\n")` only), code not a read-along element of its own (inside the notice's single `.s` element); a figure's found text stays folded. Clicking inside the code to select it does not jump (selection guard in player.js). Axe check of a real code block is in #289's browser test.

## Findings

F1 (fix in #289). A long listing hides the spoken notice. When the reading reaches a code block's notice box taller than the window, `reveal()` centres the whole box (`scrollIntoView({block: "center"})`), so the notice sentence ends up above the window, under the sticky player bar. Measured with a 44-line listing at 1280x720 on #289's head: box 922 px tall, notice `<p>` at top -34 px (bar bottom at 110 px). The seaborn listing fits on a laptop, but not on a phone or at 400 % zoom, and longer listings are common. Fix: when the highlighted element is taller than the space under the bar, scroll its top to just under the bar (or reveal the notice `<p>` rather than the box); add a browser case with a listing taller than the window that checks the notice is in view.

N1 (nit, optional). German settings line "Codeblöcke: mit einem kurzen Hinweis übersprungen, der Code im Player gezeigt" reads elliptical; "…, der Code wird im Player gezeigt" is smoother. Not required.

N2 (note, no action). While the notice is highlighted, the `.now` underline runs under every code line (44 underlines in the probe). Consistent with the read-along style; leave unless Colin finds it noisy.
