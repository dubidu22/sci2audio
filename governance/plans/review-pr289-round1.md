# Review PR #289, round 1 (layout: code listings are CODE blocks, #280)

Head reviewed: ce016cc (70a443d plus a merge of main after #288's squash 407f5bd; tree identical to 70a443d, pushed by the reviewer, so pull before fixing).
Plan: plans/issue280-code-blocks-plan.md (D-542 to D-546).

## Verdict
Changes needed: three must-fix (M1 to M3), one should-fix (S1), and F1 carried over from #288.

## What I ran myself
- Fast suite on ce016cc (HYPOTHESIS_PROFILE=ci, -n 4): 4,343 passed, 1 skipped. CI on ce016cc: green so far (Windows still running).
- Spoken scripts of all 13 corpus files, main (407f5bd) vs PR, defaults: 11 byte-identical; seaborn's ten code lines become "A code block is skipped." (one line); sample note's fenced and indented blocks become the notice (two lines). Exactly what the plan predicts.
- Golden diffs: layout corpus changes only seaborn (blocks 32-41 one `code` block 32, 73 to 64 blocks, sections shifted by 9); tagged corpus only sample note blocks 15 and 16; citations/links and furniture snapshots only seaborn renumbering and the code/numbers counts; app corpus only seaborn. Nowak's two-line GitHub URL stays a paragraph. Extraction golden files untouched.
- Truth counts confirmed against the files (asked by the coordinator in place of Colin): seaborn page 2 holds exactly one listing (the ten LMMono10 lines between the intro paragraph and Figure 1; pages 1, 3, 4 none); sci2audio-sample-note.md holds two code blocks (the fenced python block, lines 43-46, and the indented line 48; line 5 is front matter, line 81 a footnote continuation); beispiel-notiz none.
- Tagged probe (own Markdown): a fenced block with a blank line inside is one CODE block; fenced code inside a list item is CODE between the two list items; inline `code` stays in its paragraph.

## Must fix

M1. A document set wholly in a typewriter font becomes one code block. A PDF made with `tests/unit/pdf_maker` of four paragraphs in Courier 10 pt (a typed memo, a text file printed to PDF, an RFC): main reads every line; the PR's whole script is "A code block is skipped." (end to end with `sci2audio script`). The same with made-up `Content` lines. Code can only be told from text when the body text is not itself monospace. Fix suggestion: find the body font as layout does the body size (the font most body letters use) and take no code when it is monospace; test with a Courier-only PDF (read as today) and a Courier body with a listing (read, accepted).

M2. A monospace heading becomes CODE, not a heading. Three numbered headings ("1 Introduction", "2 The relplot() function", "3 Results"), bold, at body size 10 pt over Times running text: in Times-Bold, LMMono10-Bold and CourierNewPS-BoldMT main makes three headings; the PR makes three CODE blocks for both monospace fonts (sections lost). The same at 10.5 pt (under the 1.1 size guard). `find_code` runs before `find_headings`, and the size guard only catches headings larger than 1.1 x body. The coordinator's list asks that a monospace heading stays a heading; there is no test for it. Fix suggestion: leave out blocks that `find_headings` would take (for instance bold lines, which code listings almost never are), or find code after headings and keep section indices right; test the three-heading case above.

M3. The bare `code` in the font pattern matches proportional fonts. `monospace()` is True for "LucidaSansUnicode" and "ArialUnicodeMS" (standard Windows and Word fonts, also used for whole lines of CJK or symbols), "EncodeSans-Regular" and "Barcode39"; a paragraph in Lucida Sans Unicode on its own lines after running text becomes a CODE block. "AmericanTypewriter" (macOS, proportional) matches `typewriter`. Fix: name the code families instead (sourcecode, firacode, cascadiacode, codenewroman, ...) or exclude "unicode", "encode", "barcode", and exclude American Typewriter; add these names to `test_other_fonts_are_not_monospace`. Optional, not required: TeXGyreCursor (TeX's Courier, "cursor") is a missed typewriter font.

## Should fix

S1. Only a run that is exactly one link stays read. Two monospace e-mail lines (one per author, common in author blocks), whether layout makes them one paragraph or two, become one CODE block ("alice@uni-x.de\nbob@uni-y.org"); ACL's "{alice,bob}@cs.uni-x.edu" in typewriter type also becomes CODE. Fix: a run stays read when every line (or every white-space-separated piece) is a URL, e-mail address or DOI, with the brace form as an e-mail; add the three cases to `test_a_monospace_link_on_lines_of_its_own_is_read`.

## Carried from #288

F1. A long listing hides the spoken notice in the player. At 1280x720 a 44-line Courier listing gives a 922 px notice box; when the reading reaches it, `reveal()` centres the box and the notice `<p>` sits at -34 px, under the sticky bar (bottom 110 px). Fix in player.js: when the element is taller than the space under the bar, scroll its top to just under the bar (or reveal the notice `<p>`); extend `test_a_skipped_code_block_shows_its_notice_and_its_code` or add a case with a listing taller than the window that checks the notice is in view.

## For the coordinator (not for the author)

C1. "Code blocks" switched off does not read seaborn's code as today. Today (main) each code line is its own paragraph with a pause, and the notation step reads "=" as "equals". With the PR and `--off code`, the listing is one block that the number, link and hyphen steps skip (D-545 step list), so it is read as one run-on sentence: "import seaborn as sns sns.set_theme(context="paper") fmri = sns.load_dataset("fmri") ..." with "=" left to the voice. The approved plan says both "switched off, code is read as today" and "the steps that list placeholder kinds skip CODE", which cannot both hold. Recommendation: accept for v1.0.1 and file a follow-up (read a switched-on-again code block line by line, with a pause per line), since the default (on) is what Colin asked for.
