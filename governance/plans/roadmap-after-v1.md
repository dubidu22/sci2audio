# sci2audio: roadmap after v1.0

> **Superseded in part (18 Nov 2026, D-738).** Release contents changed after this file: D-666 made v1.3 "The Working Reader" and moved installers, the update check and the public plugin interface (D-458, D-459 below) to v1.4; D-721 parks publishing until the v1.4 installers; D-722 puts the general marker in v1.3 and keeps the Study layer in v1.5. The current order is `roadmap_order` in rules/project-state.yaml. Where this file differs, those decisions win.

Status: **DECIDED by Colin**, 13 Nov 2026 (thread "Decide the roadmap after v1.0"). For the KB as plain "Decided" entries in Colin's wording. Proposal and full issue table by theme: `plans/roadmap-after-v1-proposal.md` (section 3; where its "Prop." column differs, this file wins).

## Colin's words

- 21:50:48 UTC: "bigger releases weekly sounds good. i mostly use the app myself and i do quite a bit of german reading. Formulas are not priority (for me personally)"
- 21:56:42 UTC, answering (1) installers v1.1 → v1.3, (2) public plugin interface v1.1 → v1.3, (3) German voice if no good free German Kokoro voice exists: "1. yes 2. yes 3. search for the best german option and just pick it then"

## Decisions

1. **One bigger release per week, each with one theme.** Colin is the first audience: releases follow his own reading, and work only other people need comes last.
2. **v1.1, German reading** (about one week after v1.0):
   - A German voice. The v1.1 work starts by searching for the best offline German voice under a free licence and **picks it without asking Colin** (Colin: "search for the best german option and just pick it then"). Kokoro's official voices include no German, and misaki has no German pronunciation of its own. Candidates are a German Kokoro voice (D-50) and Piper's German voices (VA-08). The choice still goes through the normal plan and review, with a licence check (D-52, VA-03) and the offline rule (D-47, Q12).
   - German text rules: #96 line-end hyphens, #101 links and citations, #113 abbreviations, symbols and units, #130 numbers, dates and statistics.
   - German spoken notices (this changes Q10 of the v1.0 plan, where notices stayed English). The job's language comes from the document or from the user's choice.
   - Player wins for Colin's own use: #152 speed control, #153 remembered position, #154 open an audiobook from another folder, #119 chapter order, #190 EPUB front and back matter deselected.
3. **v1.2, better listening for Colin's papers** (about two weeks after v1.0):
   - Footnotes read next to their mark (core change, D-61 (1); the v1.0 plan's Q2 named v1.1).
   - Report warnings #186 (partly scanned PDFs) and #187 (garbled font text).
   - The rest of the English reading fixes: #100, #150, #97, #114, #131, #193, #191, #92, #93, plus stacked-fraction spacing (D-442).
   - Robustness: #185 (PDFium stream bomb), #174 + #158 (D-377), #175 (D-378), #165.
   - SRT/VTT export (OU-04) and #155 read-along on the PDF page images (D-102).
4. **v1.3, ready for others** (about three weeks after v1.0):
   - Installers with an app window (WI-08) plus #13 smoke tests. **This moves them from v1.1 (D-47) to v1.3.**
   - The public text-step plugin interface (PE-10). **This moves it from v1.1 (D-57) to v1.3**, after the v1.2 core change, so the published contract does not have to break.
   - Opt-in update check (AQ-07) and the layout edge cases (#32, #49, #54, #55, #56, #59, #122, #125, #126).
5. **Later, with no release date:** formulas spoken via MathCAT (FX-05; D-55 stays: "Formula N is skipped." until then), OCR (IN-05), DOCX/HTML import (IN-06), a batch queue (WI-06), a layout model (#25), local LLM (AI-01/02), Android (WI-10), EPUB media overlays (OU-06).
6. **v1.0.1 only if needed:** it carries blockers from Colin's listening test or screen-reader pass and the larger v1.0 leftovers (D-443). Anything else goes into v1.1.
7. **Items that wait for Colin's own release steps:**
   - The listening test may reorder items inside v1.1 and v1.2: pause lengths, notice wording, footnote urgency, en-US/en-GB spelling, stacked fractions.
   - The screen-reader pass feeds v1.0.1 or v1.1.
   - The M4 speed run decides #178 and #28.

## Follow-ups for the coordinator

- KB: these decisions as plain "Decided" (Colin, 13 Nov 21:50 and 21:56 UTC). They amend D-47 (installers v1.1 → v1.3), D-57 (public interface v1.1 → v1.3) and D-50 (German follows in v1.1). They also overturn v1.0 plan Q10 for spoken notices from v1.1 on, and plan Q2's "v1.1" for footnotes by mark (now v1.2).
- GitHub milestones: create v1.2 and v1.3 and move issues to match this file. Retitle the v1.1 milestone description ("German reading"), since it now promises installers and the public plugin interface. Move the German issues into v1.1. The installer and plugin items go to v1.3, and the v1.2 items listed above move out of v1.1. Moving #28, #41, #135, #156, #181, #134, #178 and other v1.1 items not named above is the coordinator's call.
- New issues are needed for: the German voice (v1.1), German spoken notices (v1.1), footnotes next to their mark (v1.2), SRT/VTT (v1.2), installers with an app window (v1.3), the public plugin interface (v1.3) and the update check (v1.3).

## KB entries (numbers assigned by the coordinator: D-453 to D-460)

All are **Decided** (Colin, 13 Nov 2026; his words at 21:50:48 and 21:56:42 UTC in the thread "Decide the roadmap after v1.0"; Colin decided them himself in that thread, so no separate "informed" post is needed, 21:56:42Z). Source: `plans/roadmap-after-v1.md`.

| D | Title | Decision |
|---|---|---|
| D-453 | Weekly themed releases, Colin first | After v1.0, one bigger release per week, each with one theme. Colin is the first audience ("i mostly use the app myself"). Work only other people need comes last. A v1.0.1 ships only if the listening test, the screen-reader pass or the larger v1.0 leftovers (D-443) need it. Question: how are releases after v1.0 paced and ordered? |
| D-454 | v1.1 is German reading | v1.1 = German rules #96, #101, #113, #130; a German voice (D-455); German spoken notices (D-456); the job's language from the document or the user's choice; player wins #152, #153, #154, #119, #190. Brings German forward from "after English works end to end" (D-50) to the first release after v1.0 ("i do quite a bit of german reading"). |
| D-455 | German voice: Claude searches and picks | The v1.1 work searches for the best offline German voice under a free licence and picks it without asking Colin ("search for the best german option and just pick it then"). Kokoro's official voices have no German and misaki has no German pronunciation of its own; candidates are a German Kokoro voice (D-50) and Piper's German voices (VA-08). The choice still goes through plan and review with a licence check (D-52, VA-03) and the offline rule (D-47, plan Q12). |
| D-456 | German spoken notices from v1.1 | Spoken notices (placeholders, footnotes) are spoken in the job's language from v1.1 on. Changes v1.0 plan Q10 (notices English only in v1.0). |
| D-457 | v1.2 is better listening for Colin's papers | v1.2 = footnotes read next to their mark (core change, D-61 (1); v1.0 plan Q2 had said v1.1); report warnings #186, #187; English reading fixes #100, #150, #97, #114, #131, #193, #191, #92, #93 and stacked-fraction spacing (D-442); robustness #185, #174 + #158 (D-377), #175 (D-378), #165; SRT/VTT export (OU-04); read-along on PDF page images #155 (D-102). |
| D-458 | Installers move to v1.3 | Installers with an app window (WI-08) and #13 smoke tests move from v1.1 to v1.3 ("ready for others"), with the opt-in update check (AQ-07). **Amends D-47** ("PyPI first in v1 then installers in v1.1"). Reason: Colin installs with uv himself and is the first audience. Colin: "1. yes". |
| D-459 | Public plugin interface moves to v1.3 | The public text-step plugin interface (PE-10, entry point `sci2audio.text_steps`) moves from v1.1 to v1.3, after the v1.2 footnote core change, so the published contract does not break right after release. **Amends D-57** ("internal in v1.0, public in v1.1"). Colin: "2. yes". |
| D-460 | Formulas and other ideas stay Later | Formulas spoken via MathCAT (FX-05) have no release ("Formulas are not priority (for me personally)"); D-55's skip notice stays. Also Later: OCR, DOCX/HTML, batch queue, layout model #25, local LLM, Android, EPUB media overlays. v1.3 also takes the layout edge cases #32, #49, #54, #55, #56, #59, #122, #125, #126. |
