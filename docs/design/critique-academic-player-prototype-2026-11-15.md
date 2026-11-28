---
target: design proposal in folder (prototype + spec)
total_score: 17
max_score: 40
na_heuristics:
p0_count: 1
p1_count: 3
target_identity: "file:/Users/colinmeng/Documents/Projekte/sci2audio-design/sci2audio_v2_0_academic_player_annotation_prototype.html"
target_fingerprint: "sha256:964faec7cae1974c0113dc3815a655dd2f4401ee83a595f66c7086f4e365c960"
target_path: /Users/colinmeng/Documents/Projekte/sci2audio-design/sci2audio_v2_0_academic_player_annotation_prototype.html
timestamp: 2026-11-15T17-34-50Z
slug: academic-player-annotation-prototype-html-11313521
---
DEGRADED: single-context for Assessment B (detector sub-agent blocked by permission check; CLI detector run in parent after A; no overlay).

Score 17/40 (H1 2, H2 3, H3 1, H4 1, H5 1, H6 2, H7 3, H8 2, H9 0, H10 2).

Specificity: concept product-specific (Note pauses / Quote continues, grace buffer, Wait-what loop, hyphen healing, deep links); visual layer generic Tailwind slate SaaS. Detector: nested-cards x7, pulsing-dot x2 (fake Connected status), flat-type-hierarchy x1 (likely false positive, Tailwind CDN).

Priority issues:
- [P0] Layout collapses when panes stack (28px canvas at 1280 with Full Studio + Settings); floating dock contradicts spec 2.2 full-width bar and covers margin (L648). Fix: one right pane, canvas min ~50ch, docked bar. /impeccable layout, adapt
- [P1] Keyboard model fragile: shortcuts fire with Cmd/Ctrl (Cmd+A=Anki, Cmd+S=Settings), focused checkbox swallows Space, no H, Esc doesn't close modals (L2228-2273). /impeccable harden
- [P1] No undo/failure/offline states for captures & integrations; fake connected status; 2.4s corner toast. /impeccable harden, clarify
- [P1] Accessibility: unfocusable sentence spans, 0 aria-label/aria-live, outline-none, contrast fails (slate-400 ~2.6:1, neighbours 22% ~1.3:1), no dialog semantics. /impeccable audit
- [P2] 9 toggles + presets + modes overlap; 3 toggles inert in Sentence mode (L1196-1198); DE/EN mixing, language switch translates 2 strings. /impeccable distill, clarify

Personas: Alex (OS hijacks, mouse-only range), Jordan (3 mode systems, no play in Zen, JSON export), Sam (no SR access), dyslexic/ADHD PhD (invisible neighbours, no spacing controls, action bar after paragraph).

Minor: orphaned footnote badge, fake timeline %, 0.85x never restored, Anki preview lists Obsidian notes (L2071), QR white in dark, inverted faintness slider, label mismatch, popover off-screen (L365), focus sentence not centred.
