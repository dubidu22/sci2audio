# Speed in 0.01 steps: player and voice (plan, 19 Nov 2026)

Colin, 19 Nov 10:27Z: "playback speed and generation speed should be adjustable to .01 values. think about the usability when you design the solution."
Lane: web (`src/sci2audio/web/**` only). Not critical: no layer contract, no core dataclass, no golden file, no pipeline change.

## Today (main fac140c)
- **Player** (listen page dock): a native `<select>` with 0.75, 1, 1.25, 1.5, 1.75, 2. Keys − and + move one option. Not remembered: every page load starts at 1.
- **Voice speed** (document page and Settings): a range slider 0.5–2.0, step 0.05, read-out "1.25 times" / "1,25-fach". Saved in settings.json and sent with each job. The app already accepts any value in 0.5–2.0 (`JobSettings`), so 0.01 values need no change below `web`; the chunk key already holds the speed, so no golden moves.

## Recommended design: one speed field, used in both places

**The speed field** (shared code in app.js): `[−] [ 1,07 ] [+]` with the unit after the number ("×" in the player, "times"/"-fach" for the voice).
- The middle is a text box (`inputmode="decimal"`, ARIA `spinbutton` with valuenow/min/max/valuetext). It shows **two decimals always** (1,00 · 1,07 · 1,50), so its width never jumps, in the page language's decimal sign.
- **Typing:** "1,07", "1.07" or "1,07×" are all read; Enter or leaving the box applies. A value outside the range is set to the nearest limit and the box shows it. Text that is not a number marks the box invalid (`aria-invalid`, red outline) and leaving it restores the last good value; nothing is applied while invalid.
- **Arrow Up/Down:** ±0.01. **Page Up/Down:** ±0.10. **Home/End:** the limits. These are the ARIA spinbutton keys, so screen readers announce them.
- **− and + buttons:** ±0.05 (a click is a coarse step, the arrows the fine one). Disabled at the limits.
- Every value is rounded to 0.01 before it is used or saved (no 1.0700000001).

**Player:** the dock keeps one small button showing the speed ("1,07×", same place and size as today's select). It opens a small panel above it with:
1. The presets as one row of buttons: 0,75 · 1 · 1,25 · 1,5 · 1,75 · 2 (one click, the current one pressed).
2. The speed field, range **0.50–3.00**.
The panel closes with Esc (focus back on the button), a click outside, or the button again; changes apply at once while it is open, so the person hears them. The keyboard shortcuts − and + step ±0.05 everywhere on the page (as the panel's buttons) and say the new speed, as today. The chosen speed is **remembered** in its own cookie like appearance and keys (D-671), set by a small guarded `PUT /api/v1/player/speed` (HttpOnly, SameSite=Strict, one year); the listen page starts from it.

**Voice speed (document page and Settings):** the slider stays for quick dragging, now step 0.01, and the read-out beside it becomes the speed field (range **0.50–2.00**, the app's tested limits; Kokoro itself has no hard limit but sounds unnatural outside it). Slider and field move together. Saved exactly as now (settings.json, job settings).

Why this one: presets keep the one-click common speeds; the field makes any 0.01 value reachable in one typed entry or a few arrow presses, not 100 slider pixels; a 0.01-step slider alone is not precise by mouse and a 250-option list is unusable. One field for both places means one behaviour to learn and one piece of code to test.

## Tests
- Unit (Python): the server parses and bounds the player speed cookie (bad text, out of range, NaN → 1 or the limit); `PUT /api/v1/player/speed` accepts 0.5–3.0 strict numbers only (422 otherwise, bool refused), sets the cookie, needs the token; Schemathesis covers it as part of the schema.
- Browser (Playwright, Chromium in CI): typing "1,07" in German and "1.07" in English sets `playbackRate` 1.07 and shows "1,07×"; arrows ±0.01, Page keys ±0.10, buttons ±0.05, limits clamp; invalid text is marked and restored; presets; Esc closes and returns focus; speed kept after a reload; − / + shortcuts ±0.05; voice speed slider and field in step, 1.07 saved in settings; axe light and dark with the panel open. The JS parse/format/clamp is tested in the browser (the project has no JS unit runner) with a table of inputs.
- Existing tests that read the old select or the 0.05 read-out are updated to the new control, not weakened.

## Size
About 250 lines of JS/HTML/CSS, 40 of Python, 300 of tests. One PR.
