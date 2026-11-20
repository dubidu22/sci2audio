# sci2audio v2.0 — Feature & UX/UI Design Specification

**Product Type:** Open-Source, Local-First Academic Paper-to-Audio Converter & Player  
**Target Platforms:** Desktop (macOS, Windows, Linux) with Offline Companion Apps (iOS, Android)  
**Primary Target Audience:** University Students, PhD Candidates, and Academic Researchers  

---

## 1. Executive Summary & Core UX Philosophy

### 1.1 The Core UX Tension: Temporal Audio vs. Spatial Note-Taking
Reading a scientific paper and listening to an audio track operate on fundamentally different cognitive mechanics:
* **Audio is continuous and temporal:** The synthetic voice (`Heart`) moves forward relentlessly in time.
* **Academic annotation is paused and spatial:** Synthesizing an argument, connecting it to prior literature, or saving a verbatim quotation requires stopping, isolating a specific passage, and recording a structured thought.

In a traditional HTML/PDF view, forcing a student to hunt for their mouse, drag-select character-by-character across line breaks, and type a note while the audio keeps playing creates immediate cognitive overload. **sci2audio v2.0** resolves this tension by combining **sentence-level tokenization**, **dual-intent keyboard/headphone capture**, and **progressive disclosure** inside a crisp, pure-white minimalist workspace.

### 1.2 Why Local-First Desktop Architecture is a UX Superpower
Because `sci2audio` is a strictly local, open-source application with zero hosted backend services:
1. **Zero Copyright Friction:** Students process their own university PDFs locally without uploading copyrighted publisher material to third-party servers.
2. **Native Desktop Ecosystem Bridges:** Unlike browser-sandboxed cloud tools (e.g., NotebookLM), a local desktop app can communicate directly with **Zotero Desktop** (`127.0.0.1:23119`), **Anki** (`127.0.0.1:8765`), and local **Obsidian Vault** folders on disk, and listen to global **OS Media Keys** when minimized.

---

## 2. Workspace Architecture & Layout UX

### 2.1 The 3-Pane Adjustable Academic Workspace
The v1.0.0 prototype stacked navigation buttons, audio controls,chapter links, and text vertically, pushing the actual paper content down the viewport. Version 2.0 introduces a **3-Pane Horizontal Split View** with a **Full-Width Docked Bottom Play Bar**:

| Workspace Zone | Default State | Resizable Range | Primary Purpose |
| :--- | :--- | :--- | :--- |
| **Left Pane: Outline & Figures Drawer** | Collapsed (Off) | `180px` – `420px` | Houses chapter navigation (`Kapitel`), page jumps (`Seite 1`, `Seite 14`), skipped PDF figures, and page footnotes. |
| **Center Pane: Bimodal Reading Canvas** | Expanded (Active) | `50ch` – `90ch` (Default `62ch`) | High-contrast, distraction-free editorial reading column with sentence-level audio synchronization. |
| **Right Pane: Margin Stream & Settings** | Expanded (Active) | `260px` – `520px` | Displays captured Obsidian notes, Zotero quotes, headphone Inbox bookmarks, Anki flashcards, and the `⚙️ Settings` drawer. |
| **Bottom Dock: Full-Width Play Bar** | Docked (Active) | `100%` Viewport Width | Edge-to-edge transport bar with a full-width top timeline scrubber, sentence stepping, speed control, and Pacing Mode. |

### 2.2 UX Rationale for Layout Choices
* **Crisp Pure-White Minimalism (`#FFFFFF` / `#0F172A`):** Academic papers are dense. By removing decorative cards, heavy drop shadows, and competing accent colors, the user's visual attention stays anchored on the active sentence.
* **Why a Full-Width Docked Play Bar Beats a Floating Pill:** A floating pill hovers over text, creates visual clutter around its margins, and limits the width of the timeline scrubber. Docking the play bar flush across the bottom edge grounds the interface like a native desktop DAW or IDE and turns the entire top border of the footer into a precision $100\%$-width timeline scrubber with visual annotation markers.
* **Drag-to-Resize Splitters & Measure Control:** Students working on a $13\text{"}$ laptop screen vs. a $27\text{"}$ external monitor next to Word/Overleaf have vastly different window proportions. Vertical drag handles between panes and a character-measure slider (`50ch`–`90ch`) let users tailor the workspace to their screen setup.

---

## 3. Independent View System & Reading Modes (`⚙️ Settings` Tab)

### 3.1 Modular UI Visibility (9 Independent Toggles)
Students exhibit wide variation in sensory preference—especially neurodivergent learners (ADHD, dyslexia) who use text-to-speech to maintain focus. Inside the **`⚙️ Settings`** tab (Shortcut: `S`), every visual element can be toggled on or off independently:

1. **Top Navigation Bar** (when hidden, a quiet floating pill appears in the top-right corner to restore settings).
2. **Document Header & Metadata** (Paper title, author, voice indicator, and usage instructions).
3. **Skipped Figures & Page Dividers** (`Seite 1`, `Figure 1` callout box, `Seite 14` header).
4. **Inline Sentence Action Bar** (`[-1 Satz]`, `[+1 Satz]`, `Note (N)`, `Quote (Q)`, `Bookmark (B)`, `Voice (V)`, `Anki (A)`).
5. **Inline Footnote Badges** (Interactive superscript pills `[41]`, `[42]`, `[43]`).
6. **Bottom Footnotes Reference Block** (Full footnote text at the bottom of the page).
7. **Right Margin Stream** (Captured notes and quotes sidebar).
8. **Left Outline & Chapters Drawer** (Chapter list and figure inspector).
9. **Bottom Audio Player Dock** (Full-width playback controls).

### 3.2 Sentence-Level Reading Mode ($N \pm 1$) & Pure Zen
* **The UX Problem:** Full-page academic paragraphs can cause "wall-of-text" fatigue or visual tracking loss while listening.
* **The Solution — Sentence Focus ($N \pm 1$):** Toggling **Sentence Focus** isolates the currently spoken sentence ($N$) in the vertical center of the screen at an enlarged editorial size (`28px`), while displaying **only the previous sentence ($N-1$) above and the next sentence ($N+1$) below** at a faint opacity.
* **Adjustable Neighbor Faintness (`0%` – `60%`):** A slider in Settings lets the user tune the opacity of sentences $N-1$ and $N+1$ (default `22%`). Setting the slider to `0%` isolates strictly one sentence on screen at a time.
* **1-Click View Presets:**
  * **Pure Sentence (Zen):** Enables Sentence Focus ($N \pm 1$) and hides all 9 chrome elements for a completely blank white canvas containing only the three sentences.
  * **Focused $N \pm 1$:** Enables Sentence Focus ($N \pm 1$) while keeping the Top Bar, Inline Actions, and Bottom Play Bar active.
  * **Full Studio:** Restores full-text scrolling view with all sidebars and reference panels open.

### 3.3 Typography & Accessibility Modes
* **Editorial Serif vs. Crisp Sans:** Users can switch the reading canvas between **Newsreader** (an optical-size editorial serif designed for long-form academic reading) and **Inter** (a high-x-height neo-grotesque sans-serif preferred by many readers with dyslexia).
* **Pure White, Evening Dark, and AAA High Contrast Mode (`H`):**
  * **AAA High Contrast Mode** (accessible inside `⚙️ Settings` or via hotkey `H`) strips all intermediate grays, enforcing pure `#000000` ink on `#FFFFFF` backgrounds, `2px solid #000000` structural borders, and an unmistakable `#FFEB3B` yellow highlight box around the active sentence for low-vision accessibility or glare-heavy environments.

---

## 4. Frictionless "Flow-State" Annotation & Capture UX

### 4.1 Sentence-Snapping Selection (Zero Mouse Dragging)
Because `sci2audio` already tokenizes the paper into discrete sentences for TTS synthesis, the UI eliminates manual character-level drag selection:
1. **Instant Active-Sentence Targeting:** Pressing `N`, `Q`, `B`, `V`, or `A` automatically targets the currently active sentence ($N$).
2. **Range Expansion Pills (`[-1 Satz]` / `[+1 Satz]`):** If an argument spans two or three sentences, clicking `[-1 Satz]` or `[+1 Satz]` on the inline action bar snaps the selection boundary backward or forward by whole sentences, updating the quote preview in real time.

### 4.2 Dual-Intent Capture: Separating "Notes" from "Quotes"
In academic workflows, writing a personal synthesis note (Obsidian) and saving a verbatim citation (Zotero) have completely different cognitive requirements:

| Dimension | 💬 Obsidian Note Track (`N` Key) | ❝ Zotero Quote Track (`Q` Key) |
| :--- | :--- | :--- |
| **User Intent** | Synthesize an idea, critique a claim, or link to another concept (`[[WikiLink]]`). | Collect a verbatim passage + page number to cite in a term paper or thesis. |
| **Audio Playback Behavior** | **Auto-Pauses Audio Immediately.** Prevents the narrator from talking over the student's internal monologue while typing. | **Continues Playing Uninterrupted.** Saves the quote silently in the background with a subtle confirmation toast so listening flow is never broken. |
| **Resume Mechanics** | Pressing `Cmd/Ctrl + Enter` (or clicking **Save & Resume ▶**) saves the note and automatically resumes audio from the start of the active sentence. | N/A (Audio never paused). |
| **Metadata Captured** | User Markdown note + `[[WikiLinks]]` + `#tags` + verbatim blockquote + page number + `sci2audio://` timestamp link + attached footnote. | Auto-healed verbatim quote + exact PDF page number (`p. 14`) + parent paper Citekey + attached footnote text. |

### 4.3 Hold-to-Speak Offline Voice Notes (`V` Key)
* **UX Context:** When listening in a "lean-back" posture or pacing the room, typing on a keyboard is inconvenient.
* **Mechanism:** Pressing `V` (or clicking `🎙️`) pauses playback and activates local offline speech-to-text (`whisper.cpp` tiny/base model running on-device). The spoken thought is transcribed locally, linked to the active sentence and page number, and saved to the Obsidian stream before playback automatically resumes.

---

## 5. Hands-Free & "Eyes-Busy" Acoustic UX ("Pacing Mode")

Students frequently listen to 60+ minute readings while walking, commuting, cooking, or resting their eyes. `sci2audio` turns hands-free listening into an active study session without requiring cloud AI.

### 5.1 The 3-Second Reaction-Time Grace Buffer
* **The UX Problem:** When listening to an audiobook or paper, a student only realizes a sentence was profound *after* the narrator finishes speaking it—by which time playback has already crossed into the first 1–3 seconds of the *next* sentence.
* **The Solution:** When the **3s Reaction-Time Buffer** is enabled in Settings, triggering a bookmark (`B` or Headphone Double-Tap) within the first $3.5\text{ seconds}$ of Sentence $N$ automatically expands the capture range backward to include **Sentence $N-1$ and Sentence $N$**.

### 5.2 Hijacking OS Media Keys & Bluetooth Headphones
Nobody listening to a single 68-minute academic paper wants their Bluetooth headphone's "Next Track" button to skip the entire paper. `sci2audio` rebinds standard OS media transport events (`MediaTrackNext` / `MediaTrackPrevious`):
1. **Double-Tap Headphone (`MediaTrackNext`) $\rightarrow$ Acoustic Bookmark (`🔖`):**
   * Plays a soft, non-intrusive wooden "tick" earcon in the headphones.
   * Captures the active sentence (with the 3-second Grace Buffer applied) and places it into the **Inbox** filter tab in the Margin Stream for desk review later.
2. **Triple-Tap Headphone (`MediaTrackPrevious`) $\rightarrow$ The "Wait, What?" Loop (`🐢`):**
   * Plays a gentle two-tone descending earcon.
   * Jumps back $2$ sentences (`Vorheriger Satz` $\times 2$) and automatically drops playback speed to $0.85\times$ so the student can digest a dense philosophical or sociological sentence without touching their phone or laptop.

### 5.3 Deterministic Acoustic Typography (Audio Formatting Cues)
When eyes are off the screen, listeners lose visual typography cues (quotation marks, footnotes, page breaks, and figures). `sci2audio` restores structural awareness through optional, deterministic audio cues:
* **🔔 Embedded Quote Chime:** Plays a subtle two-note harmonic chime before the voice reads an embedded quotation (such as the Alicia Garza quote on page 14) so the listener knows the primary author is quoting another scholar.
* **📄 Page-Turn Earcon:** Emits a soft, tactile sound when crossing a PDF page boundary (`Seite 13` $\rightarrow$ `Seite 14`), helping the student maintain a mental map of paper length and progress.
* **🔊 15-Second Local Audio Caption for Skipped Figures:** Instead of merely stating *"A figure is skipped"*, users can trigger a concise $15\text{-second}$ audio description of the extracted diagram (or inspect the SVG/image directly inline).

---

## 6. Solving PDF-to-Audio Academic Edge Cases

Raw text extracted from multi-column or typeset academic PDFs contains structural artifacts that corrupt citations when pasted into a thesis or Zotero library.

### 6.1 ✨ Auto-Healing PDF Hyphenation Artifacts
* **The Problem:** Typeset PDFs break words across lines with hard hyphens—for example, `mate-rial`, `soci-ety`, and `institu-tions` in the Christopher Chapman paper.
* **The UX Fix:** When **Auto-Heal PDF Artifacts** is active, `sci2audio` rejoins line-break hyphenations both in the reading canvas (marked with a subtle dotted underline on hover so the student can verify the original print) and in all exported Obsidian/Zotero/Clipboard strings (`"material violence"` instead of `"mate-rial violence"`).

### 6.2 Inline Footnote Separation & Automatic Attachment
* **The Problem:** PDF extractors frequently merge superscript citation numbers directly into the preceding word or punctuation mark (e.g., `citizens.41`, `movement.42`, `oppression.”43`), causing TTS engines to read *"citizens forty-one"* aloud and polluting quotes.
* **The UX Fix:**
  1. `sci2audio` strips trailing footnote numbers from the spoken and quoted sentence text and renders them as interactive superscript badges (`[41]`, `[42]`, `[43]`).
  2. Clicking any badge opens an **Inline Footnote Popover** directly above the paragraph without losing scroll position.
  3. Whenever a sentence containing a footnote badge is saved as a Note (`N`) or Quote (`Q`), `sci2audio` **automatically attaches the full corresponding footnote text** from the bottom of the page (`Thobani, 2007, p. 18`) as metadata on the exported card.

---

## 7. Local Student Ecosystem Integrations & Export Hub

### 7.1 Permanent `sci2audio://` Custom OS URI Protocol
In v1.0.0, the player ran on an ephemeral localhost port (`http://127.0.0.1:49346/documents/...`). If a student pasted that URL into Obsidian and restarted their computer the next day, the port changed and broke every link.
* **The Solution:** Registering a custom OS protocol handler (`sci2audio://`) creates permanent, port-independent deep links:
  ```text
  sci2audio://listen/1b970f352ff479f7?page=14&sentence=s6&t=1445
  ```
  Clicking this link inside Obsidian, Zotero, or Anki months later launches the `sci2audio` desktop app, loads the paper, and begins playback at `24:05` (`p. 14`).

### 7.2 Obsidian Vault Integration (`.md` & Live File Watcher)
* **YAML Frontmatter & Callout Formatting:** Generates structured Markdown with YAML properties (`title`, `author`, `year`, `citekey`, `doc_id`, `tags`) and native Obsidian `> [!quote]` callouts containing the `🎧 Listen at 24:05` deep link, auto-healed quote, attached footnote, and user commentary with `[[WikiLinks]]`.
* **3 Export Modes:** Copy Markdown to clipboard, Download `.md` file, or sync directly via `obsidian://new` / a local Vault folder file watcher.

### 7.3 Zotero Desktop Integration (`http://127.0.0.1:23119`)
* **Localhost Connector Sync:** Communicates directly with the local Zotero Desktop HTTP server on port `23119` to attach captured quotes as **Zotero Child Notes** under the parent bibliographic item (`Chapman, 2014`).
* **Smart Citation Clipboard (`Cmd/Ctrl + Shift + C`):** Copies any sentence or saved quote pre-formatted in **APA** `(Chapman, 2014, p. 14)`, **Chicago** `(Chapman 2014, 14)`, or **LaTeX BibLaTeX** `\enquote{...} \autocite[p.~14]{chapman2014violent}` for immediate pasting into Word, Overleaf, or Typst.

### 7.4 Anki Flashcard Bridge (`http://127.0.0.1:8765`)
* Pressing `A` on any key definition or theoretical claim queues a Q&A or Cloze card for **AnkiConnect** (`127.0.0.1:8765`) and automatically slices the corresponding $8\text{-second}$ `.opus` sentence audio clip into Anki's local media collection for bimodal spaced repetition.

### 7.5 Zero-Cloud Mobile Sync (`.s2a` Open Bundle Format)
To support future free, offline iOS and Android apps without running a cloud server:
* Papers are packaged into an open `.s2a` directory/archive containing `manifest.json` (sentence-to-timestamp map and page anchors), `audio/heart_neural.opus`, and `annotations.jsonl` (an append-only log of notes and bookmarks).
* Students can sync their `.s2a` folder via **Syncthing, iCloud Drive, or Nextcloud**, or scan a **Local LAN Wi-Fi QR Code** in the Export Hub to beam a paper directly between their desktop and phone over their home router.

---

## 8. Complete Keyboard Shortcut & Gesture Matrix

| Shortcut / Gesture | Action | Audio Behavior | Target Destination |
| :--- | :--- | :--- | :--- |
| `Space` | Play / Pause Audio (`Abspielen` / `Pause`) | Toggles playback | Bottom Play Bar |
| `←` / `[` | Previous Sentence (`Vorheriger Satz`) | Jumps to start of $N-1$ | Reading Canvas |
| `→` / `]` | Next Sentence (`Nächster Satz`) | Jumps to start of $N+1$ | Reading Canvas |
| `N` | Open Obsidian Note Composer | **Auto-pauses audio** | Obsidian Track (Margin Stream) |
| `Cmd/Ctrl + Enter` | Save Note & Resume Audio | **Auto-resumes audio** | Obsidian Track (Margin Stream) |
| `Q` | Instant Capture Verbatim Quote | **Keeps playing uninterrupted** | Zotero Track (Margin Stream) |
| `B` | Quick Acoustic Bookmark (3s Grace Buffer) | Plays wooden tick earcon | Inbox Tab (Margin Stream) |
| `V` | Dictate Offline Voice Note (`whisper.cpp`) | **Auto-pauses**, records, resumes | Obsidian Track (Margin Stream) |
| `A` | Create Anki Flashcard + `.opus` Audio Slice | Keeps playing uninterrupted | AnkiConnect (`:8765`) |
| `Cmd/Ctrl + Shift + C` | Copy Formatted Citation (APA / LaTeX) | Keeps playing uninterrupted | OS System Clipboard |
| `S` | Toggle `⚙️ View & Settings` Drawer | Keeps playing uninterrupted | Settings Drawer |
| `H` | Toggle AAA High Contrast Mode | Keeps playing uninterrupted | Global Theme |
| **Headphone 2x Tap** | Hands-Free Acoustic Bookmark (`MediaTrackNext`) | Plays tick earcon + 3s buffer | Inbox Tab (Margin Stream) |
| **Headphone 3x Tap** | "Wait, What?" Loop (`MediaTrackPrevious`) | Rewinds $2$ sentences at $0.85\times$ | Audio Engine |