---
name: sci2audio
description: A faithful audiobook of your paper, read along and marked up on your own computer.
colors:
  cobalt: "#2340A8"
  cobalt-deep: "#1A3087"
  cobalt-line: "#3A56BE"
  on-cobalt: "#FFFFFF"
  on-cobalt-2: "#CCD5F4"
  ink: "#16181D"
  ink-2: "#3A3E46"
  pencil: "#5A5E66"
  paper: "#FFFFFF"
  desk: "#EDEFF2"
  desk-2: "#E3E6EA"
  rule: "#D7DADF"
  rule-strong: "#8C9199"
  hl-read: "#FFE94A"
  hl-note: "#7BE38A"
  hl-quote: "#6CC4FF"
  hl-card: "#FF8FC8"
  hl-mark: "#FFB347"
  error: "#B42318"
  error-wash: "#FDECEA"
  wait: "#7A4B00"
  wait-wash: "#FFF3DC"
typography:
  display:
    fontFamily: "Literata, Georgia, serif"
    fontSize: "clamp(30px, 3.4vw, 48px)"
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Literata, Georgia, serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.005em"
  view-title:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.3
  reading:
    fontFamily: "Literata, Georgia, serif"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: 1.8
  body:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1.3
  figures:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    fontFeature: "\"tnum\" 1, \"lnum\" 1"
rounded:
  hair: "1px"
  sheet: "2px"
  key: "3px"
  base: "4px"
  dialog: "6px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "40px"
  rail: "264px"
  panel: "340px"
  dock: "88px"
components:
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "7px 14px"
    height: "38px"
  button-hover:
    backgroundColor: "{colors.desk-2}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.base}"
    padding: "7px 14px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.ink-2}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "7px 14px"
  button-danger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.error}"
    rounded: "{rounded.base}"
    padding: "7px 14px"
  play:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    size: "52px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "7px 10px"
    height: "38px"
  chip-ready:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "2px 8px 2px 6px"
  chip-making:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px 2px 6px"
  chip-warn:
    backgroundColor: "transparent"
    textColor: "{colors.wait}"
    rounded: "{rounded.pill}"
    padding: "2px 8px 2px 6px"
  chip-failed:
    backgroundColor: "{colors.error-wash}"
    textColor: "{colors.error}"
    rounded: "{rounded.base}"
    padding: "2px 8px 2px 6px"
  flag:
    backgroundColor: "{colors.hl-note}"
    textColor: "{colors.ink}"
    width: "24px"
    height: "18px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.on-cobalt}"
    rounded: "{rounded.base}"
    padding: "9px 10px"
  nav-item-current:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
  sheet:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "28px 64px 56px"
  toast:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.base}"
    padding: "10px 12px 10px 14px"
---

# Design System: sci2audio

## Overview

**Creative North Star: "The Working Reader"**

The app is the student's own marked-up copy of the paper. A bright white sheet of bond paper lies on a cool grey desk; the shell around it is a binder-cobalt rail. Ink is black, marginalia and cancels are pencil grey, and colour enters only as highlighter: the voice sweeps the sentence it reads in yellow, and every capture sticks out of the page edge as a small coloured flag at its sentence, mirrored along the top of the timeline.

Density is that of a working document, not a showcase. Hairline rules divide everything; surfaces are paper panels with 4px corners and no lift. The reading column is the product and is defended at every width: tools appear beside it and recede. The interface speaks in Atkinson Hyperlegible, the paper speaks in Literata, and every number is set in tabular figures.

The world refuses the category default for reading tools: a grey sidebar, a blue selection highlight, and a notes panel of rounded cards.

**Key Characteristics:**
- White paper sheet on a cool grey desk, cobalt rail as the shell.
- Highlighter fluorescents carry meaning, never decoration.
- Captures are flags and ruled marginalia, not cards.
- Changes cancel in pencil and can be undone; nothing silently disappears.
- Two bundled faces: Atkinson Hyperlegible for interface, Literata for reading.
- Hairline rules and 4px corners; one soft shadow, reserved for the sheet and popovers.

## Colors

Paper, ink and pencil on a cool desk, one binder cobalt, and five highlighter fluorescents that each mean exactly one thing.

### Primary
- **Binder Cobalt** (`cobalt`): the rail, the whole left shell, and nothing else as a fill. On paper it appears only as the light-mode focus ring, checkbox accent and switched-on switch. **Cobalt Deep** (`cobalt-deep`) is rail hover and the current shelf item; **Cobalt Line** (`cobalt-line`) draws hairlines inside the rail. Text on cobalt is white (`on-cobalt`), secondary rail text is **Cobalt Mist** (`on-cobalt-2`).

### Secondary: the highlighters
- **Reading Yellow** (`hl-read`): the sentence being read (the sweep), the held/hover tint behind sentences (at 30%), text selection, the "2" in the wordmark, listened-progress meters, and the focus ring inside the rail.
- **Note Green** (`hl-note`): note captures.
- **Quote Blue** (`hl-quote`): quotes to cite. In dark mode it also becomes the focus ring and switched-on switch on paper.
- **Card Pink** (`hl-card`): review cards.
- **Mark Orange** (`hl-mark`): marks (bookmarks).

Text on any highlighter is ink (`on-hl`, the same value as `ink`).

### Tertiary: state
- **Error Red** (`error`) with **Error Wash** (`error-wash`): failed chips, bad notices, danger buttons.
- **Wait Umber** (`wait`) with **Wait Wash** (`wait-wash`): warning chips and notices (offline, needs update, voice missing).

### Neutral
- **Ink** (`ink`): body text, primary buttons, the play button, progress fills, the active tab underline.
- **Ink Soft** (`ink-2`): secondary prose, footnotes, inactive tabs, primary-button hover.
- **Pencil** (`pencil`): meta lines, hints, labels, struck-through cancels, footnote marks.
- **Paper** (`paper`): the sheet and every panel surface.
- **Desk** (`desk`) and **Desk Shade** (`desk-2`): the app ground and the side panel; Desk Shade is the hover wash for buttons and rows.
- **Rule** (`rule`) and **Rule Strong** (`rule-strong`): hairlines; Rule Strong outlines controls, dashed slots and the ready chip.

Dark mode re-tones every token (paper `#1C1F25` on desk `#111317`, ink `#E9EAED`, cobalt `#1C2E78`, fluorescents slightly dimmed); the sweep becomes yellow at 36% with white text so it stays a highlight rather than a block.

### Named Rules
**The Highlighter Rule.** Fluorescents appear only for reading (the yellow sweep) and the four capture types (note green, quote blue, card pink, mark orange). Never on status chips, buttons, navigation or decoration. Never two highlighter fills in one region of text: a sentence carries one highlight at a time. Flags, flag strips, timeline ticks and the four capture keys are the capture index and show each type in its own colour as a small tab.

**The One Cobalt Rule.** Cobalt is the shell. It is not an accent for buttons or links on paper; primary actions are ink.

**The Form-Not-Colour Rule.** State is carried by an icon and a word as well as colour: every chip has its icon, every cancel its strike-through.

## Typography

**Display Font:** Literata (with Georgia, serif), bundled variable 200–900, roman and italic
**Body Font:** Atkinson Hyperlegible (with system-ui, sans-serif), bundled 400, 400 italic, 700

**Character:** A legibility face built for low-vision readers runs the interface; a screen-tuned book serif carries the paper itself. The split tells the user at a glance what is the text and what is the tool.

### Hierarchy
- **Display** (Literata 500, clamp(30px, 3.4vw, 48px), 1.35, max 28ch, centred): the current sentence in focus listening only.
- **Headline** (Literata 600, 30px, 1.2): chapter titles on the sheet; 28px for the paper title in the paper header; 22px/1.3 for section heads on the sheet; 19px for capture group heads.
- **View Title** (Atkinson 700, 30px, 1.15, -0.01em): page titles for app views (Library, Captures, Voices).
- **Title** (Atkinson 700, 17–19px): step headers, dialog titles, pack and settings section heads; 16px for export-target names; 22px for the wordmark and 24px for empty-state heads.
- **Reading** (Literata 400, 20px, 1.8, max 66ch): the sheet's paragraphs. Footnotes 16px/1.65; quotes in captures italic 15.5px/1.5; review cards 24px front, 17px back.
- **Body** (Atkinson 400, 15px, 1.45): all interface text; prose pages 15.5px/1.6 at 68ch with an 18px lead; summary lines on Prepare 16px/1.5.
- **Label** (Atkinson 700, 12.5–14px, sentence case, no tracking): field labels, column heads, capture type labels, rail section heads. Never uppercase.

### Named Rules
**The Two Voices Rule.** Literata is for the paper and anything quoted from it (sheet, printed/read columns, captured quotes, card faces). Atkinson is for everything the app says. Never mix them within one line of interface.

**The Tabular Rule.** Every number (counts, times, pages, sizes, percentages) is set with tabular lining figures (`tnum`, `lnum`).

## Layout

A three-part desk: cobalt rail (264px), a centre that scrolls, and a full-width player dock (88px) under the centre. On the listen screen the centre splits into the desk with the sheet and one context panel (340px) on desk ground, separated by a hairline. The sheet is centred, max 66ch of reading plus 64px side padding; flags hang 24px off its right edge.

App views sit in a centred column up to 1160px with 32px/40px padding; the paper header and prepare view widen to 1240px with a 340px sticky side column. Spacing runs on a 4px base, chiefly 4 / 8 / 12 / 16 / 24 / 32 / 40.

Breakpoints: at 1399px and below the rail narrows to 232px, the panel to 320px, sheet padding to 48px, and capture keys drop their labels (keeping key caps). At 1279px and below the context panel leaves the grid and becomes a fixed overlay from the right; side columns stack below the main column. Focus listening collapses the rail to zero width.

**The Column Wins Rule.** The reading column never collapses. Panels collapse first, then labels, then the rail narrows.

## Elevation & Depth

Flat by default. Depth comes from the paper-on-desk contrast and hairline rules, not shadows. One soft, low-offset ambient shadow exists in two strengths: on the paper sheet, and on things that float above it.

### Shadow Vocabulary
- **Sheet** (`box-shadow: 0 1px 2px rgba(22,24,29,.06), 0 8px 24px -12px rgba(22,24,29,.18)`): the paper sheet on the listen screen only.
- **Pop** (`box-shadow: 0 2px 6px rgba(22,24,29,.10), 0 16px 40px -16px rgba(22,24,29,.30)`): popovers, menus, dialogs, toasts, the capture composer, and the context panel when it overlays at narrow widths.

### Named Rules
**The One Sheet Rule.** A soft offset shadow belongs only to the paper sheet and to popovers. Panels, steps, rows and cards are flat with a hairline. No hard offset shadows anywhere.

## Shapes

Squared and papery. The base corner is 4px on buttons, inputs, panels and chips; the sheet itself is 2px; document thumbnails are 1px; key caps 3px; dialogs 6px. Fully round forms are reserved for the play button, switches and the in-progress / warning chip pills. Flags are squared tabs, flat on the page-edge side and rounded 3px on the free edge, like a sticky index tab. Dashed lines mean "not here": drop slots, spoken notices for skipped tables, page breaks, and cancelled captures.

## Components

### Buttons
Plain and inked.
- **Shape:** gently squared (4px), 38px min height, 1px Rule Strong outline, Atkinson 700 14.5px.
- **Default:** paper fill, ink text; hover Desk Shade.
- **Primary:** ink fill, paper text; hover Ink Soft. One per region.
- **Quiet:** no border or fill until hover. **Danger:** error text and outline on paper. **Small:** 32px, 13.5px.
- **Play:** 52px ink circle, the only round button.
- **Focus:** 2px cobalt ring at 2px offset (quote blue in dark mode, reading yellow inside the rail).

### Chips (state)
- **Ready:** transparent with a hairline outline (Rule Strong) and a check icon, ink text, 4px corners.
- **In progress:** transparent ink-outline pill with its icon.
- **Warning:** transparent pill outlined and lettered in Wait Umber with an alert icon.
- **Failed:** Error Wash fill, error text, alert icon, 4px corners.
- **Idle:** Desk Shade wash, Ink Soft text (not analysed, voice missing).
- Chips never use highlighter colours and never look like filled buttons: no ink or cobalt fill, no button height.

### Cards / Containers
- **Corner Style:** 4px.
- **Background:** paper on desk.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px Rule.
- **Internal Padding:** 16–22px; headers split from bodies by a hairline.
- Containers never nest inside containers; inside a panel, structure is ruled rows.

### Inputs / Fields
- **Style:** paper fill, 1px Rule Strong outline, 4px, 38px; label above in Atkinson 700 14px, hint below in pencil 13.5px.
- **Switch:** 36×20 pill, Rule Strong off, cobalt on (quote blue in dark).
- **Segmented:** outlined group; pressed segment is ink with paper text.
- **Focus:** the global ring.

### Navigation
- **Rail:** cobalt, white text; items 9px/10px padding at 4px; hover Cobalt Deep; current item becomes a paper tab with ink 700 text, as if pulled out of the binder. Counts right-aligned in tabular figures.
- **Shelf:** papers being read, two-line title, meta line, a 4px meter (yellow for listened, white for making) and a flag strip.
- **Tabs:** ink text 700, current tab has a 3px ink underline on a hairline baseline. The reading panel's tabs are set at 13px, the small end of the Label size, with 4px side padding (the German labels are the longest: "Änderungen", "Kapitel" and "Fundstücke (999)" must stay on one row in the 320px panel at 1280px; #889, #1000, #1001).

### Flags (signature)
The capture vocabulary. A 24×18 squared tab in its highlighter colour, an ink line icon, a faint inset outline. On capture a flag slides out of the sheet's right edge at its sentence (0.45s, `cubic-bezier(.16,1,.3,1)`) and a 7×10 tick appears on the timeline. Flag strips repeat them as 8×10 ticks on shelf items and library rows.

### Captures as marginalia (signature)
A capture is a ruled row: hairline above, the flag hanging in a 40px left margin, a pencil type label, the quoted sentence in Literata italic, the user's text in Atkinson, and a pencil foot line (page, time, actions). No box, no fill, no radius.

### Reading sweep (signature)
The sentence being read fills left to right with Reading Yellow as the voice advances (a background-size transition over the sentence's duration). Already-swept text stays held in a pale yellow tint. Under reduced motion the sentence is highlighted whole.

### Cancels
Switched-off changes, deselected chapters and removed captures stay in place, struck through in pencil (cancelled captures also get a dashed rule), with an undo or restore action beside them. Citations the voice skips are shown struck in pencil at 0.92em; text read differently gets a dotted pencil underline.

### Player dock
Paper bar under the centre, 88px: a 3px timeline along its top edge with chapter ticks and capture flags, prev / play / next, title and tabular time, speed select, the four capture keys (flag + label + key cap), and the AI-voice label.

## Do's and Don'ts

### Do:
- **Do** keep the reading column at full measure (66ch) and collapse the panel, labels and rail before it.
- **Do** use exactly one highlighter per meaning: yellow for being read; green note, blue quote, pink card, orange mark.
- **Do** draw captures as ruled marginalia with a hanging flag.
- **Do** cancel instead of deleting: pencil strike-through plus undo for switched-off changes and removed captures.
- **Do** set every number in tabular figures.
- **Do** carry state with icon and word: ready is an outline with a check, in progress an ink-outline pill, warning an outline in Wait Umber, error an error wash.
- **Do** use Literata for anything from the paper and Atkinson Hyperlegible for everything the app says.

### Don't:
- **Don't** put highlighter fluorescents on status chips, buttons or decoration, or two highlighter fills in one region.
- **Don't** box captures as cards or nest a card inside a card.
- **Don't** make a status chip look like a filled button.
- **Don't** give a shadow to anything but the paper sheet and popovers; never a hard offset shadow.
- **Don't** use cobalt as an accent on paper; primary actions are ink.
- **Don't** silently remove anything the user or the rules changed.
- **Don't** use uppercase tracked labels or kickers above headings.
