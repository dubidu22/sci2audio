// The read-along player (#78, OU-02; D-294 to D-303) and the Listen page around it: the
// highlight, the dock and the context panel (#392, #393), Focus listening and the keys
// (#394).
// Loaded only by the listen page, after app.js, whose `tr`, `say` and `typing` it uses
// (D-302).
//
// The page holds the text; every sentence the voice reads is an element `.s` with the
// number of its first chunk. The data block holds, per chunk, [start, end, chapter,
// element id] on the book's timeline, and per chapter its audio file and where the
// book's time 0 lies in that file's timeline (`offset`), so the time in the file is
// `book time - offset` (docs/readalong-format.md).
"use strict";

const SCROLL_KEYS = new Set(["PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown", " "]);
const RESTART_AFTER = 1.5; // seconds into a sentence after which "previous" restarts it

function readAlong() {
  const block = document.getElementById("player-data");
  const audio = document.getElementById("audio");
  if (!block || !audio) return;
  const data = JSON.parse(block.textContent);
  const chunks = data.chunks; // [start, end, chapter, element id]
  // each chunk's sentence, by its first chunk: the pieces of a sentence cut for the voice
  // are one sentence (#480); every other chunk is its own
  const firstOf = chunks.map((_, n) => data.sentences?.[n] ?? n);
  const chapters = data.chapters; // {title, file, offset, start, first}
  // each file's address is made here from the document id and the file's bare name
  const base = `/api/v1/documents/${encodeURIComponent(data.document)}/audiobook/`;
  const source = (c) => base + encodeURIComponent(chapters[c].file);
  const text = document.getElementById("text");
  const play = document.getElementById("play");
  const now = document.getElementById("now");
  const follow = document.getElementById("follow");
  const back = document.getElementById("back-to-reading");
  const speed = document.getElementById("speed");
  const bar = document.getElementById("dock");
  const timeline = document.getElementById("timeline");
  const clock = document.getElementById("clock");
  const reading = document.getElementById("reading"); // only when announcing is on (#388)
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  let total = clockOf(Number(timeline.max) || 0); // grows with a book still being made (#724)

  let loaded = -1; // the chapter whose file the audio element holds
  let current = -1; // the chunk highlighted
  let marked = null; // its element
  let following = true; // false after the person scrolled away by hand (D-301)
  let frame = 0;
  let pending = null; // a jump waiting for its file to load or the seek before it to end
  let touched = false; // the person played or moved: from then on the position is kept
  let savedAt = 0; // when the position was last sent (performance.now())
  let focusing = false; // Focus listening is shown (#394)
  let panelByKey = null; // P: shows or hides the panel, leaving the focus where it is (#461)
  let growing = null; // a book still being made (#724), see grow()

  // the dock is pinned to the window's foot only while it takes at most a quarter of the
  // window, and then nothing focused or scrolled to may hide under it (WCAG 1.4.10, 2.4.11):
  // the page gets room below and scroll padding. Pinning does not change the dock's height,
  // so the observer below does not loop.
  function pad() {
    const root = document.documentElement;
    const height = bar.offsetHeight;
    const fits = height <= window.innerHeight / 4;
    bar.classList.toggle("pinned", fits);
    root.classList.toggle("dock-pinned", fits);
    root.style.setProperty("--dock-h", fits ? `${height}px` : "0px");
    root.style.scrollPaddingBottom = fits ? `${height + 8}px` : "";
  }
  pad();
  if (window.ResizeObserver) new ResizeObserver(pad).observe(bar);
  window.addEventListener("resize", pad);

  if (data.mode === "m4b" && !audio.canPlayType('audio/mp4; codecs="mp4a.40.2"')) {
    say(tr("player.cannot_play"), true);
  }

  // ---- time --------------------------------------------------------------------------

  function chapterAt(time) {
    let found = 0;
    for (let c = 0; c < chapters.length; c++) if (chapters[c].start <= time) found = c;
    return found;
  }

  function bookTime() {
    return audio.currentTime + (loaded < 0 ? 0 : chapters[loaded].offset);
  }

  // the last chunk that started at or before `time` (-1 before the first)
  function chunkAt(time) {
    let low = 0;
    let high = chunks.length - 1;
    let found = -1;
    while (low <= high) {
      const middle = (low + high) >> 1;
      if (chunks[middle][0] <= time + 0.0005) {
        found = middle;
        low = middle + 1;
      } else high = middle - 1;
    }
    return found;
  }

  // ---- what is shown -------------------------------------------------------------------

  function showChapter(c) {
    // the title is the document's own words, in the text's language (D-291)
    const title = document.createElement("span");
    title.lang = text.lang;
    title.textContent = chapters[c].title;
    now.replaceChildren(tr("player.chapter", { n: c + 1, total: chapters.length }), " ", title);
    focusChapter.textContent = chapters[c].title;
    for (const button of chapterButtons) {
      if (Number(button.dataset.chapter) === c) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
  }

  // where the window's free height ends: at the pinned dock's top, else at its foot
  function dockTop() {
    return bar.classList.contains("pinned") ? bar.getBoundingClientRect().top : window.innerHeight;
  }

  function visible(element) {
    const box = element.getBoundingClientRect();
    return box.top >= 0 && box.bottom <= dockTop();
  }

  function reveal(element) {
    if (!element || !follow.checked || !following || visible(element)) return;
    const behavior = reduced.matches ? "auto" : "smooth";
    const box = element.getBoundingClientRect();
    if (box.height > dockTop()) {
      // taller than the window above the dock (a long code listing, #280): its start, where
      // the spoken notice stands, goes to the window's top instead of out of sight above it
      window.scrollBy({ top: box.top - 8, behavior });
      return;
    }
    element.scrollIntoView({ block: "center", behavior });
  }

  // ---- the highlight (#392, #452) -------------------------------------------------------
  // The sentence being read is marked at once, plainly and without motion (D-709): the
  // stylesheet's `.now` on the sheet, and the stage's copy of it in Focus listening.

  // the sentence being read is told to screen readers only if the person switched that on
  // in Settings (#388); otherwise the highlight never speaks (D-300)
  function announce(element) {
    if (reading && element && !audio.paused) reading.textContent = element.textContent.trim();
  }

  function highlight(index) {
    if (index === current) return;
    const element = index < 0 ? null : document.getElementById(chunks[index][3]);
    current = index;
    if (element === marked) return; // empty spans share their sentence's element
    if (marked) {
      // a sentence heard keeps no mark (D-720)
      marked.classList.remove("now");
      marked.removeAttribute("aria-current");
    }
    marked = element;
    stage();
    if (marked) {
      marked.classList.add("now");
      marked.setAttribute("aria-current", "true");
      announce(marked);
      reveal(marked);
    }
    placeBars();
    markerState();
  }

  function update() {
    // while a file loads, its time is still 0, and while a jump waits for the seek before
    // it, the time is that seek's: the jump's own highlight stands
    if (loaded < 0 || pending) return;
    highlight(chunkAt(bookTime()));
    showTime(bookTime());
  }

  // ---- the dock's clock and timeline (#393) ----------------------------------------------

  function clockOf(seconds) {
    const whole = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(whole / 3600);
    const minutes = Math.floor((whole % 3600) / 60);
    const secs = String(whole % 60).padStart(2, "0");
    return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${secs}` : `${minutes}:${secs}`;
  }

  let shownSecond = -1;
  let dragging = false; // the person holds the timeline: it shows their time, not the voice's

  function showTime(time, force = false) {
    if (dragging && !force) return;
    const second = Math.floor(time);
    const share = Number(timeline.max) > 0 ? (time / Number(timeline.max)) * 100 : 0;
    timeline.style.setProperty("--fill", `${Math.min(Math.max(share, 0), 100)}%`);
    if (second === shownSecond && !force) return;
    shownSecond = second;
    const said = tr("player.time_of", { time: clockOf(time), total });
    clock.textContent = said;
    timeline.value = String(time);
    timeline.setAttribute("aria-valuetext", said);
  }

  function tick() {
    update();
    if (!audio.paused && !pending && loaded >= 0) keep(loaded, bookTime(), false);
    frame = audio.paused ? 0 : requestAnimationFrame(tick);
  }

  // ---- moving ----------------------------------------------------------------------------

  // put the audio at `time` on the book's timeline, in chapter `c`; start it if `start`
  function seek(c, time, start) {
    const target = chapters[c];
    const at = Math.max(0, time - target.offset);
    const go = () => {
      audio.currentTime = at;
      if (start) audio.play().catch(() => {});
      update();
    };
    if (loaded !== c) showChapter(c);
    // a jump made while another file is still loading, or another seek still runs, replaces
    // that jump
    if (pending) audio.removeEventListener(pending.event, pending.run);
    pending = null;
    const src = source(c);
    loaded = c;
    // one seek at a time: Linux WebKit loses the place of a seek started while another one
    // still runs and ends at 0, with nothing marked (#720)
    const event =
      audio.getAttribute("src") !== src ? "loadedmetadata" : audio.seeking ? "seeked" : "";
    if (!event) {
      go();
      return;
    }
    const run = () => {
      pending = null;
      go();
    };
    pending = { event, run };
    audio.addEventListener(event, run, { once: true });
    if (event === "loadedmetadata") audio.src = src;
  }

  function playFrom(index, start) {
    if (index < 0 || index >= chunks.length) return;
    following = true;
    back.hidden = true;
    const [time, , c] = chunks[index];
    highlight(index);
    seek(c, time, start);
    reveal(marked);
    keep(c, time);
  }

  // ---- the listening position (#153) ---------------------------------------------------
  // kept by the server in the document's working folder, so the next run of sci2audio
  // (on another port, where the browser's storage starts empty) can offer to continue.
  // A failed save says nothing: the reading goes on (D-300).
  const SAVE_EVERY = 5000; // ms while playing
  const position = `/api/v1/documents/${encodeURIComponent(data.document)}/position`;

  function keep(c = loaded, time = bookTime(), force = true) {
    if (c < 0 || !data.audiobook) return;
    touched = true;
    if (!force && performance.now() - savedAt < SAVE_EVERY) return;
    savedAt = performance.now();
    fetch(position, {
      method: "POST",
      credentials: "same-origin",
      keepalive: true, // also when the page is going away
      headers: { "content-type": "application/json" },
      // the audiobook this page shows: a save from a page left open over a new audiobook
      // is refused (409), never written into the new one
      body: JSON.stringify({ chapter: c, time: Math.max(0, time), audiobook: data.audiobook }),
    }).catch(() => {});
  }

  function keepIfTouched() {
    if (!data.audiobook) return;
    if (touched && loaded >= 0 && !pending) keep();
  }

  function chapterOfCurrent() {
    return current >= 0 ? chunks[current][2] : Math.max(loaded, 0);
  }

  function toChapter(c, start) {
    const target = Math.min(Math.max(c, 0), chapters.length - 1);
    playFrom(chapters[target].first, start);
    say(`${tr("player.chapter", { n: target + 1, total: chapters.length })} ${chapters[target].title}`);
  }

  // ---- controls --------------------------------------------------------------------------

  let chapterButtons = [...document.querySelectorAll(".chapter-button")];

  play.addEventListener("click", () => {
    touched = true;
    if (loaded < 0) seek(0, chapters[0].start, true);
    else if (audio.paused) audio.play().catch(() => {});
    else audio.pause();
  });
  // next and previous step by sentence, never into the middle of a cut one (#480)
  document.getElementById("next-sentence").addEventListener("click", () => {
    let next = current + 1;
    while (next < chunks.length && firstOf[next] !== next) next++;
    playFrom(next < chunks.length ? next : firstOf[chunks.length - 1], !audio.paused);
  });
  document.getElementById("previous-sentence").addEventListener("click", () => {
    const start = current >= 0 ? firstOf[current] : -1;
    const into = start >= 0 ? bookTime() - chunks[start][0] : 0;
    const target = !audio.paused && into > RESTART_AFTER ? start : start - 1;
    playFrom(target >= 0 ? firstOf[target] : 0, !audio.paused);
  });
  function chapterButton(button) {
    button.addEventListener("click", () => toChapter(Number(button.dataset.chapter), true));
  }
  chapterButtons.forEach(chapterButton);

  // the timeline: a move by pointer or keys goes to that time, in its chapter (#393)
  timeline.addEventListener("input", () => {
    dragging = true;
    const time = Number(timeline.value);
    clock.textContent = tr("player.time_of", { time: clockOf(time), total });
    timeline.style.setProperty("--fill", `${(time / Number(timeline.max)) * 100}%`);
  });
  function moveTo(to) {
    dragging = false;
    const time = Math.min(Math.max(to, 0), Number(timeline.max));
    timeline.value = String(time);
    const c = chapterAt(time);
    following = true;
    back.hidden = true;
    highlight(chunkAt(time));
    seek(c, time, !audio.paused);
    reveal(marked);
    keep(c, time);
    showTime(time, true);
  }
  timeline.addEventListener("change", () => moveTo(Number(timeline.value)));
  // the keys move 5 s (30 s by page), and Home and End reach both ends: the slider takes
  // any time, so the voice's own time and the book's end are never rounded to a step
  timeline.addEventListener("keydown", (event) => {
    const by = { ArrowRight: 5, ArrowUp: 5, ArrowLeft: -5, ArrowDown: -5, PageUp: 30, PageDown: -30 };
    let to = null;
    if (event.key in by) to = Number(timeline.value) + by[event.key];
    else if (event.key === "Home") to = 0;
    else if (event.key === "End") to = Number(timeline.max);
    if (to === null || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    moveTo(to);
  });

  // a figure that can't be shown (gone, or the reader stopped) leaves only its notice (#293)
  function figuresIn(root) {
    for (const figure of root.querySelectorAll("img.figure")) {
      const hide = () => { figure.hidden = true; };
      figure.addEventListener("error", hide);
      if (figure.complete && figure.naturalWidth === 0) hide(); // failed before this ran
    }
  }
  figuresIn(text);

  // a click (or a screen reader's Enter) on a sentence plays from it (D-298)
  text.addEventListener("click", (event) => {
    if (event.target.closest("summary, details")) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return; // the person is selecting text
    const sentence = event.target.closest(".s[data-chunk]");
    if (sentence) playFrom(Number(sentence.dataset.chunk), true);
  });

  // ---- speed (#152, #651) ---------------------------------------------------------------
  // a new file resets `playbackRate` to `defaultPlaybackRate`, so both are set: the speed
  // stays across the chapters' files, jumps and the M4B; the voice keeps its pitch. The dock
  // shows it on a button that opens the usual speeds and the speed field (app.js); the speed
  // chosen is kept for the next Listen page in a cookie (PUT /api/v1/player/speed).
  const speedPanel = document.getElementById("speed-panel");
  const speedNow = document.getElementById("speed-now");
  const presets = speedPanel.querySelectorAll("button[data-speed]");
  const speedSaid = (value) => tr("listen.speed_value", { value: speedText(value) });
  let keepSpeed = 0; // the timer that keeps the speed once the person stops changing it
  const playerSpeed = speedField(speedPanel.querySelector(".speed-field"), speedSaid, (value) => {
    applySpeed(value);
    clearTimeout(keepSpeed);
    keepSpeed = setTimeout(() => {
      // a speed not kept is only not offered next time: nothing to tell the person
      send("/api/v1/player/speed", json("PUT", { speed: value })).catch(() => {});
    }, 500);
  });
  function applySpeed(value) {
    audio.preservesPitch = true;
    if ("webkitPreservesPitch" in audio) audio.webkitPreservesPitch = true;
    if ("mozPreservesPitch" in audio) audio.mozPreservesPitch = true;
    audio.defaultPlaybackRate = value;
    audio.playbackRate = value;
    speedNow.textContent = speedSaid(value);
    for (const preset of presets) {
      preset.setAttribute("aria-pressed", String(Number(preset.dataset.speed) === value));
    }
  }
  audio.addEventListener("loadedmetadata", () => applySpeed(playerSpeed.value));
  applySpeed(playerSpeed.value);
  for (const preset of presets) {
    preset.addEventListener("click", () => playerSpeed.set(Number(preset.dataset.speed), true));
    preset.disabled = false; // drawn disabled (#350)
  }

  // the panel opens above the button; a keyboard opens it with the focus in the field, a
  // pointer leaves the focus on the button (a touch screen's keyboard stays away). Esc, a
  // click elsewhere or the focus leaving it closes it.
  function showSpeedPanel(open, focus) {
    speedPanel.hidden = !open;
    speed.setAttribute("aria-expanded", String(open));
    placeSpeedPanel();
    if (open && focus) document.getElementById("speed-exact").focus();
  }
  // a narrow window may put the button near its left edge: the panel moves right to stay in
  function placeSpeedPanel() {
    speedPanel.style.right = "";
    if (speedPanel.hidden) return;
    const left = speedPanel.getBoundingClientRect().left;
    if (left < 8) speedPanel.style.right = `${left - 8}px`;
  }
  window.addEventListener("resize", placeSpeedPanel);
  speed.addEventListener("click", (event) => showSpeedPanel(speedPanel.hidden, event.detail === 0));
  speed.disabled = false;
  const speedMenu = speed.parentElement;
  // Esc from anywhere while the panel is open: Safari gives a clicked button no focus, so
  // after a click on the speed button or a preset the focus is not in the menu (#699)
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || speedPanel.hidden) return;
    event.preventDefault(); // Esc closes the panel only, and leaves Focus listening on
    showSpeedPanel(false);
    speed.focus();
  });
  // a press inside the menu keeps it open: Safari's mousedown on a button there moves the
  // focus out to the page, and closing then lost the button's click (#699)
  let pressedInside = false;
  document.addEventListener("pointerdown", (event) => {
    pressedInside = speedMenu.contains(event.target);
    if (!speedPanel.hidden && !pressedInside) showSpeedPanel(false);
  });
  document.addEventListener("pointerup", () => {
    pressedInside = false;
  });
  speedMenu.addEventListener("focusout", (event) => {
    if (pressedInside) return;
    if (event.relatedTarget && !speedMenu.contains(event.relatedTarget)) showSpeedPanel(false);
  });

  // ---- Focus listening (#394, DESIGN.md "Focus") ------------------------------------------
  // A mode of this page with no address of its own: the rail, the sheet and the panel give
  // way to the stage, which shows the sentence being read between its neighbours, copied
  // from the sheet's own elements (with their marks); the dock and the voice go on.
  const focusView = document.getElementById("focus-view");
  const focusOn = document.getElementById("focus-on");
  const focusOff = document.getElementById("focus-off");
  const focusPrevious = document.getElementById("focus-prev");
  const focusNow = document.getElementById("focus-now");
  const focusNext = document.getElementById("focus-next");
  const focusChapter = document.getElementById("focus-chapter");
  let order = [...new Set(chunks.map((chunk) => chunk[3]))]; // sentences in reading order
  let place = new Map(order.map((id, at) => [id, at]));

  function copy(id) {
    const element = id ? document.getElementById(id) : null;
    if (!element) return [];
    // a spoken notice: its words, without the icon or the text found in the file
    const words = element.classList.contains("notice") ? element.querySelector("p > span") : element;
    return [...(words || element).childNodes].map((node) => node.cloneNode(true));
  }

  function stage() {
    if (!focusing) return;
    const id = marked ? marked.id : order[0];
    const at = place.get(id) ?? 0;
    focusPrevious.replaceChildren(...copy(order[at - 1]));
    focusNow.replaceChildren(...copy(id));
    focusNext.replaceChildren(...copy(order[at + 1]));
    placeBars();
  }

  // ---- the bar beside the sentence being read (D-724) ------------------------------------
  // The fill alone is too pale to be told apart by colour (below 3:1), so a bar in the margin
  // marks the lines the sentence stands on: on the sheet in its left padding, in Focus left of
  // the sentence. It is placed from the sentence's own line boxes, again whenever the mark
  // moves or the text reflows (width, fonts), and hidden while nothing shown is marked.
  const sheet = document.querySelector(".sheet");
  const sheetBar = document.getElementById("now-bar");
  const focusBar = document.getElementById("focus-bar");

  // the line boxes an element stands on, as drawn
  function linesOf(element) {
    return element ? [...element.getClientRects()].filter((r) => r.width && r.height) : [];
  }

  function placeBar(bar, element, box, left) {
    if (!bar) return;
    const lines = linesOf(element);
    if (!lines.length) {
      bar.hidden = true;
      return;
    }
    const top = Math.min(...lines.map((r) => r.top));
    const bottom = Math.max(...lines.map((r) => r.bottom));
    const at = box.getBoundingClientRect();
    bar.style.top = `${top - at.top - box.clientTop}px`;
    bar.style.height = `${bottom - top}px`;
    bar.style.left = `${left(lines) - at.left - box.clientLeft - 12}px`;
    bar.hidden = false;
  }

  let barFrame = 0;
  function placeBars() {
    if (barFrame) return;
    barFrame = requestAnimationFrame(() => {
      barFrame = 0;
      // on the sheet: 12 px left of the text column, whatever the sentence's first line does
      placeBar(sheetBar, focusing ? null : marked, sheet, () => text.getBoundingClientRect().left);
      // in Focus: 12 px left of the sentence's leftmost line (the stage centres it)
      const now = focusing && focusNow.textContent.trim() ? focusNow : null;
      placeBar(focusBar, now, focusBar?.parentElement, (lines) => Math.min(...lines.map((r) => r.left)));
      placeFlags();
    });
  }
  if (window.ResizeObserver) {
    const watch = new ResizeObserver(placeBars);
    watch.observe(text);
    if (focusBar) watch.observe(focusBar.parentElement);
  }
  // a chapter far from the window is laid out again once it comes near (content-visibility)
  const laidOut = (chapter) => chapter.addEventListener("contentvisibilityautostatechange", placeBars);
  text.querySelectorAll(".sheet-chapter").forEach(laidOut);
  window.addEventListener("resize", placeBars);
  document.fonts?.ready.then(placeBars);

  // ---- markers (#474, D-723, D-728) -----------------------------------------------------
  // A marker on the sentence being read, set or removed by M or the dock's button, with an
  // optional note in the panel. The server keeps them in the working folder and places each
  // in this audiobook; the page draws a flag beside its sentence (no fill: the reading mark
  // stays the only fill), a tick above the timeline and a row in the panel. A removal never
  // asks: the toast's Undo puts it back, for 60 s (D-723 ruling 1).
  const markerButton = document.getElementById("marker");
  const markerList = document.getElementById("marker-list");
  const markersTab = document.getElementById("tab-markers");
  const markersEmpty = document.getElementById("markers-empty");
  const flags = document.getElementById("marker-flags");
  const focusFlag = document.getElementById("focus-flag");
  const markerTicks = document.getElementById("marker-ticks");
  const toast = document.getElementById("marker-toast");
  const toastSaid = document.getElementById("marker-said");
  const undoButton = document.getElementById("marker-undo");
  const addNoteButton = document.getElementById("marker-add-note");
  const markersUrl = `/api/v1/documents/${encodeURIComponent(data.document)}/markers`;
  const markersOff = Boolean(data.markers_file); // a file this version can't read: hands off
  const MARK_BACK = 1.2; // seconds into a sentence in which M marks the one that just ended
  const TOAST_FOR = 60000; // ms the toast's Undo stays
  const NOTE_LIMIT = 4000;
  let markers = data.markers || []; // {id, text, note, chunk, state}, in the server's order
  let undo = null; // what the toast's Undo does
  let noteFor = null; // the marker the toast's "Add note" opens
  let toastTimer = 0;
  let editing = null; // the marker whose note box is open
  let resumeAfterNote = false;
  let showMarkers = null; // opens the panel on the Markers tab (contextPanel)
  let markerQueue = Promise.resolve(); // the marker changes M and the button asked for

  const elementOf = (marker) => (marker.chunk === null ? "" : chunks[marker.chunk]?.[3] || "");
  const markersOn = (id) => (id ? markers.filter((m) => elementOf(m) === id) : []);

  // reading order: found ones by their sentence, then those not read, then those not found
  function sortMarkers() {
    const rank = { found: 0, "not-read": 1, "not-found": 2 };
    markers = markers
      .map((marker, at) => [marker, at])
      .sort(([a, i], [b, j]) => rank[a.state] - rank[b.state] || (a.state === "found" ? a.chunk - b.chunk : 0) || i - j)
      .map(([marker]) => marker);
  }

  // the sentence M acts on: the one being read, or the one that just ended while the voice
  // is in the first 1.2 s of the next (#397), counted from the start of the next one's first
  // piece (#480); the chunk its element starts with
  function markerTarget() {
    if (current < 0) return null;
    let at = current;
    if (!audio.paused && bookTime() - chunks[firstOf[current]][0] < MARK_BACK) {
      const id = chunks[current][3];
      let back = current - 1;
      while (back >= 0 && (!chunks[back][3] || chunks[back][3] === id)) back--;
      if (back >= 0) at = back;
    }
    const id = chunks[at][3];
    const element = id ? document.getElementById(id) : null;
    return element ? { id, chunk: Number(element.dataset.chunk) } : null;
  }

  async function markerCall(url, method, body) {
    try {
      const options = { method };
      if (body) {
        options.headers = { "content-type": "application/json" };
        options.body = JSON.stringify(body);
      }
      return await send(url, options);
    } catch (error) {
      hideToast();
      say(explain(error), true);
      return null;
    }
  }

  function tell(said, then = null, noted = null) {
    clearTimeout(toastTimer);
    toastSaid.textContent = said;
    undo = then;
    noteFor = noted;
    undoButton.hidden = !then;
    addNoteButton.hidden = !noted;
    toast.hidden = false;
    say(said); // the status line, for screen readers
    toastTimer = setTimeout(hideToast, TOAST_FOR);
  }

  function hideToast() {
    clearTimeout(toastTimer);
    const inside = toast.contains(document.activeElement);
    toast.hidden = true;
    undo = null;
    noteFor = null;
    if (inside) play.focus(); // the button pressed goes away: the focus goes to the player
  }

  undoButton.addEventListener("click", () => {
    const then = undo;
    hideToast();
    then?.();
  });
  addNoteButton.addEventListener("click", () => {
    const id = noteFor;
    hideToast();
    if (id) openNote(id);
  });

  async function setMarker(chunk) {
    const marker = await markerCall(markersUrl, "POST", { chunk, audiobook: data.audiobook });
    if (!marker) return;
    keepMarker(marker);
    tell(tr("marker.set"), () => removeMarker(marker), marker.id);
  }

  async function removeMarker(marker) {
    const gone = await markerCall(`${markersUrl}/${marker.id}`, "DELETE");
    if (!gone) return;
    if (editing === gone.id) editing = null;
    markers = markers.filter((m) => m.id !== gone.id);
    drawMarkers();
    tell(gone.note ? tr("marker.removed_note") : tr("marker.removed"), () => restoreMarker(gone.id));
  }

  async function restoreMarker(id) {
    const marker = await markerCall(`${markersUrl}/${id}/restore`, "POST");
    if (!marker) return;
    keepMarker(marker);
    tell(tr("marker.restored"));
  }

  function keepMarker(marker) {
    const kept = { id: marker.id, text: marker.text, note: marker.note, chunk: marker.chunk, state: marker.state };
    markers = [...markers.filter((m) => m.id !== kept.id), kept];
    sortMarkers();
    drawMarkers();
  }

  function toggleMarker() {
    if (markersOff) {
      say(tr("error.markers-unreadable"), true);
      return;
    }
    const target = markerTarget(); // the sentence when the key was pressed
    if (!target) return;
    // one change at a time, in the order pressed: a second press on the same sentence
    // removes what the first one set
    markerQueue = markerQueue.then(() => {
      const there = markersOn(target.id)[0];
      return there ? removeMarker(there) : setMarker(target.chunk);
    });
  }
  markerButton.addEventListener("click", toggleMarker);

  // the button is pressed while the sentence being read has a marker
  function markerState() {
    const id = current >= 0 ? chunks[current][3] : "";
    markerButton.disabled = markersOff || !id;
    markerButton.setAttribute("aria-pressed", String(markersOn(id).length > 0));
  }

  // ---- the flags and the ticks ----

  function placeFlags() {
    const box = sheet.getBoundingClientRect();
    const column = text.getBoundingClientRect();
    const ids = focusing ? [] : [...new Set(markers.map(elementOf).filter(Boolean))];
    while (flags.children.length > ids.length) flags.lastElementChild.remove();
    while (flags.children.length < ids.length) {
      const flag = document.createElement("span");
      flag.className = "marker-flag";
      flag.append(focusFlag.querySelector("svg").cloneNode(true));
      flags.append(flag);
    }
    ids.forEach((id, n) => {
      const flag = flags.children[n];
      const lines = linesOf(document.getElementById(id));
      flag.dataset.for = id;
      flag.hidden = !lines.length;
      if (!lines.length) return;
      const width = flag.offsetWidth;
      const height = flag.offsetHeight;
      flag.style.top = `${lines[0].top - box.top - sheet.clientTop + (lines[0].height - height) / 2}px`;
      flag.style.left = `${column.right - box.left - sheet.clientLeft + (box.right - column.right - width) / 2}px`;
    });
    // in Focus: right of the stage's sentence, at its first line
    const staged = focusing && marked && markersOn(marked.id).length ? linesOf(focusNow) : [];
    focusFlag.hidden = !staged.length;
    if (staged.length) {
      const at = focusFlag.parentElement.getBoundingClientRect();
      const right = Math.max(...staged.map((r) => r.right));
      focusFlag.style.top = `${staged[0].top - at.top + (staged[0].height - focusFlag.offsetHeight) / 2}px`;
      focusFlag.style.left = `${right - at.left + 8}px`;
    }
  }

  function drawTicks() {
    const length = Number(timeline.max) || 0;
    const times = [...new Set(markers.filter((m) => m.chunk !== null).map((m) => chunks[firstOf[m.chunk]][0]))];
    markerTicks.replaceChildren(
      ...times.map((time) => {
        const tick = document.createElementNS(markerTicks.namespaceURI, "rect");
        tick.setAttribute("x", `${length > 0 ? (time / length) * 100 : 0}%`);
        tick.setAttribute("y", "0");
        tick.setAttribute("width", "7");
        tick.setAttribute("height", "10");
        return tick;
      }),
    );
  }

  // ---- the panel's list ----

  function made(tag, className, words) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (words !== undefined) element.textContent = words;
    return element;
  }

  function action(words, then) {
    const button = made("button", "sm quiet", words);
    button.type = "button";
    button.addEventListener("click", then);
    return button;
  }

  function row(marker) {
    const item = made("li", "marker-row");
    item.dataset.marker = marker.id;
    if (marker.state === "found") {
      const [time, , chapter] = chunks[firstOf[marker.chunk]]; // the sentence's start (#480)
      item.append(made("p", "mk-at", tr("marker.at", { n: chapter + 1, time: clockOf(time) })));
    } else {
      const notice = marker.state === "not-read" ? tr("marker.not_read") : tr("marker.not_found");
      item.append(made("p", "mk-state", notice));
    }
    const quote = made("blockquote", "mk-text", marker.text);
    quote.lang = text.lang;
    item.append(quote);
    if (marker.text.length > 200) {
      quote.classList.add("clamped");
      const more = action(tr("marker.show_all"), () => {
        const open = quote.classList.toggle("clamped") === false;
        more.textContent = open ? tr("marker.show_less") : tr("marker.show_all");
        more.setAttribute("aria-expanded", String(open));
      });
      more.classList.add("mk-more");
      more.setAttribute("aria-expanded", "false");
      item.append(more);
    }
    if (marker.note) item.append(made("p", "mk-note", marker.note));
    if (editing === marker.id) {
      item.append(noteBox(marker));
      return item;
    }
    const actions = made("p", "mk-actions");
    if (marker.state === "found") {
      actions.append(action(tr("marker.go_to"), () => playFrom(firstOf[marker.chunk], !audio.paused)));
    }
    const edit = action(marker.note ? tr("marker.edit_note") : tr("marker.add_note"), () => openNote(marker.id));
    edit.classList.add("mk-edit-note");
    actions.append(edit, action(tr("marker.remove"), () => removeMarker(marker)));
    item.append(actions);
    return item;
  }

  function noteBox(marker) {
    const box = made("div", "mk-edit");
    const id = `note-${marker.id}`;
    const label = made("label", "", tr("marker.note"));
    label.htmlFor = id;
    const area = made("textarea");
    area.id = id;
    area.rows = 4;
    area.maxLength = NOTE_LIMIT;
    area.value = marker.note;
    const left = made("p", "hint mk-left");
    left.id = `${id}-left`;
    left.setAttribute("aria-live", "polite");
    area.setAttribute("aria-describedby", left.id);
    const count = () => {
      const rest = NOTE_LIMIT - area.value.length;
      left.textContent = rest <= 400 ? tr("marker.note_left", { n: rest }) : "";
    };
    area.addEventListener("input", count);
    count();
    area.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        saveNote(marker.id, area.value);
      } else if (event.key === "Escape") {
        event.preventDefault(); // the panel stays open, and Focus is not left
        event.stopPropagation();
        closeNote(marker.id);
      }
    });
    const buttons = made("p", "buttons");
    const save = action(tr("marker.save"), () => saveNote(marker.id, area.value));
    save.classList.replace("quiet", "primary");
    buttons.append(save, action(tr("marker.cancel"), () => closeNote(marker.id)));
    box.append(label, area, left, buttons);
    return box;
  }

  function rowOf(id) {
    return markerList.querySelector(`li[data-marker="${CSS.escape(id)}"]`);
  }

  // the note box: playback pauses while it is open and goes on after it closes (#397)
  function openNote(id) {
    if (!markers.some((m) => m.id === id)) return;
    if (focusing) setFocus(false);
    if (editing === null) resumeAfterNote = !audio.paused;
    audio.pause();
    editing = id;
    drawList();
    showMarkers?.();
    rowOf(id)?.querySelector("textarea")?.focus();
  }

  function closeNote(id) {
    editing = null;
    drawList();
    rowOf(id)?.querySelector(".mk-edit-note")?.focus();
    if (resumeAfterNote) audio.play().catch(() => {});
    resumeAfterNote = false;
  }

  async function saveNote(id, value) {
    const note = value.trim() ? value : "";
    const marker = await markerCall(`${markersUrl}/${id}`, "PATCH", { note });
    if (!marker) return;
    editing = null;
    keepMarker(marker);
    say(tr("marker.saved"));
    closeNote(id);
  }

  function drawList() {
    // the focus never falls out of the panel while its rows are drawn again: over the page
    // that would close it (#444); the caller puts it where it belongs
    if (markerList.contains(document.activeElement)) markersTab.focus({ preventScroll: true });
    markerList.replaceChildren(...markers.map(row));
    markersEmpty.hidden = markers.length > 0;
    markersTab.textContent = tr("marker.tab_count", { n: markers.length });
  }

  function drawMarkers() {
    drawList();
    drawTicks();
    markerState();
    placeBars();
  }

  function setFocus(on) {
    if (on === focusing) return;
    focusing = on;
    document.documentElement.classList.toggle("focus-listening", on);
    focusView.hidden = !on;
    stage();
    placeBars(); // leaving Focus: back on the sheet
    pad();
    // Focus shows the reading itself, and leaving it comes back to the reading: either way
    // the page follows the reading again, and Back to the reading has nothing to offer
    following = true;
    back.hidden = true;
    if (on) {
      focusView.focus(); // a panel open over the page closes, as the focus leaves it (#447)
      return;
    }
    reveal(marked);
    focusOn.focus();
  }
  focusOn.addEventListener("click", () => setFocus(true));
  focusOff.addEventListener("click", () => setFocus(false));

  // ---- the keys (#394) ------------------------------------------------------------------
  // Space, the arrows and Shift with them on a focused control do what the control does; no
  // key acts while the person types, while a dialog is open, or with ⌘, Ctrl or Alt held,
  // so no browser or system shortcut is taken.
  const CONTROLS = "button, a[href], input, select, textarea, summary, audio, [role='tab'], [tabindex]:not([tabindex='-1'])";

  // − and + step the speed by 0.05, as the panel's buttons (#651), and say it
  function stepSpeed(by) {
    if (!playerSpeed.set(playerSpeed.value + by * 0.05, true)) return; // at a limit
    say(tr("player.speed_now", { speed: speedSaid(playerSpeed.value) }));
  }

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    if (document.querySelector("dialog[open]")) return;
    const key = event.key;
    // Esc leaves Focus from anywhere in it, a field or the speed list too, and with the keys
    // switched off (#394)
    if (key === "Escape") {
      if (!focusing) return;
      event.preventDefault();
      setFocus(false);
      return;
    }
    if (!shortcutsOn() || typing(event.target)) return;
    const onControl = event.target instanceof Element && event.target.closest(CONTROLS);
    const once = !event.repeat; // a held key toggles once (#394)
    if (key === " " && !onControl) {
      if (once) play.click();
    } else if ((key === "ArrowLeft" || key === "ArrowRight") && !onControl) {
      const by = key === "ArrowRight" ? 1 : -1;
      if (event.shiftKey) toChapter(chapterOfCurrent() + by, !audio.paused);
      else document.getElementById(by > 0 ? "next-sentence" : "previous-sentence").click();
    } else if (key === "-") stepSpeed(-1);
    else if (key === "+" || key === "=") stepSpeed(1);
    else if (key === "f" || key === "F") {
      if (once) setFocus(!focusing);
    } else if ((key === "p" || key === "P") && !focusing) {
      if (once) panelByKey?.(); // the focus stays where it is (#461)
    } else if (key === "m" || key === "M") {
      if (once) toggleMarker(); // also in Focus (#474)
    } else return;
    event.preventDefault();
  });

  // ---- following the reading (D-301) -----------------------------------------------------

  function scrolledByHand() {
    if (focusing || !following || !follow.checked) return;
    following = false;
    back.hidden = false;
  }
  window.addEventListener("wheel", scrolledByHand, { passive: true });
  window.addEventListener("touchmove", scrolledByHand, { passive: true });
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || !SCROLL_KEYS.has(event.key)) return; // not a key taken above
    if (event.target.closest("button, input, select, textarea, audio, summary, a")) return;
    scrolledByHand();
  });
  back.addEventListener("click", () => {
    following = true;
    reveal(marked);
    play.focus(); // the button hides itself: the focus goes to the player, not the page
    back.hidden = true;
  });
  follow.addEventListener("change", () => {
    following = true;
    back.hidden = true;
    reveal(marked);
  });

  // ---- the audio element -----------------------------------------------------------------

  // the play button says what it does next: its name and its icon (DESIGN.md "Player dock")
  function showPlaying(playing) {
    const name = playing ? tr("player.pause") : tr("player.play");
    play.setAttribute("aria-label", name);
    play.title = name;
    play.querySelector("use")?.setAttribute("href", playing ? "#i-pause" : "#i-play");
  }

  audio.addEventListener("play", () => {
    showPlaying(true);
    if (!frame) frame = requestAnimationFrame(tick);
  });
  audio.addEventListener("pause", () => {
    showPlaying(false);
    update();
    keepIfTouched();
  });
  audio.addEventListener("seeked", update);
  audio.addEventListener("timeupdate", () => {
    if (audio.paused) update();
  });
  audio.addEventListener("ended", () => {
    // the next chapter's file follows by itself (D-296); the M4B is one file
    if (data.mode === "mp3" && loaded >= 0 && loaded < chapters.length - 1) {
      seek(loaded + 1, chapters[loaded + 1].start, true);
    } else if (growing?.coming()) {
      growing.wait(); // the next chapter is still being made (#724)
      keepIfTouched();
    } else keepIfTouched(); // the end: nothing is offered for it next time
  });
  window.addEventListener("pagehide", keepIfTouched);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") keepIfTouched();
  });
  audio.addEventListener("error", () => {
    if (audio.getAttribute("src")) say(tr("player.load_failed"), true);
  });

  if (data.mode === "m4b") {
    // one file: the chapter follows the time
    audio.addEventListener("timeupdate", () => {
      const c = chapterAt(bookTime());
      if (c !== loaded) {
        loaded = c;
        showChapter(c);
      }
    });
  }
  growing = data.growing ? grow() : null;
  seek(0, chapters[0].start, false);
  const panel = contextPanel();
  panelByKey = panel?.byKey;
  showMarkers = panel?.show;
  drawMarkers();

  // drawn disabled: a press before this script ran would be lost (#350, #427)
  for (const control of [
    play,
    timeline,
    document.getElementById("previous-sentence"),
    document.getElementById("next-sentence"),
    focusOn,
    focusOff,
    ...chapterButtons,
  ]) {
    control.disabled = false;
  }
  undoButton.disabled = false;
  addNoteButton.disabled = false;
  markerState(); // drawn disabled too: enabled once a sentence is there to mark

  // ---- a book still being made (#724, LW-02) ---------------------------------------------
  // The audio job makes each chapter playable as soon as it is spoken (#723). The page
  // follows the job's events: when they name more playable chapters than the page holds, it
  // fetches the next one, drawn by the server as the page draws its chapters, and adds it at
  // the end of the text, the timeline and the chapter list. The book only grows at its end,
  // so nothing before moves; a chapter that does not continue the page's chunks (the book
  // was made again meanwhile) reloads the page instead. At the end of the last chapter the
  // player waits, says so, and goes on by itself once the next chapter is there, unless the
  // person moved meanwhile.
  function grow() {
    const status = document.getElementById("growing-status");
    const waiting = document.getElementById("waiting");
    const outline = document.getElementById("outline");
    const ticks = document.querySelector(".timeline .ticks");
    let rows = data.growing.planned; // {index, title, chapter, state}
    let running = Boolean(data.growing.events);
    let wanted = chapters.length; // chapters the job says are playable
    let held = false; // the player stopped at the end of the last chapter, waiting

    function later() {
      return rows.some((row) => row.chapter === null && row.state === "generating");
    }

    function showWaiting(on) {
      held = on;
      waiting.hidden = !on;
      // set while shown, so the status is said (a hidden region is not)
      waiting.textContent = on ? tr("player.waiting_next") : "";
    }

    function drawRow(row) {
      const item = outline.querySelector(`li.chapter-later[data-index="${row.index}"]`);
      // a chapter the server has and this page not yet: it stays a row until it is added
      if (!item || row.chapter >= chapters.length) return;
      if (row.chapter === null) {
        const said = row.state === "missing" ? tr("player.missing") : tr("player.generating");
        item.querySelector(".chapter-state").textContent = said;
        return;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chapter-button";
      button.dataset.chapter = String(row.chapter);
      button.lang = text.lang;
      const title = made("span", "ot", row.title);
      const at = made("span", "oc", clockOf(chapters[row.chapter].start));
      button.append(title, at);
      const fresh = document.createElement("li");
      fresh.append(button);
      item.replaceWith(fresh);
      chapterButton(button);
      chapterButtons = [...outline.querySelectorAll(".chapter-button")];
    }

    function add(part) {
      const n = chapters.length;
      if (part.first !== chunks.length || part.audiobook !== data.audiobook) {
        location.reload(); // not the book this page holds any more
        return;
      }
      const holder = document.createElement("template");
      holder.innerHTML = part.html; // drawn by the server, as the page's own chapters
      const section = holder.content.firstElementChild;
      text.append(section);
      laidOut(section);
      figuresIn(section);
      chapters.push(part.chapter);
      chunks.push(...part.chunks);
      part.sentences.forEach((first) => firstOf.push(first));
      order = [...new Set(chunks.map((chunk) => chunk[3]))];
      place = new Map(order.map((id, at) => [id, at]));
      timeline.max = String(part.duration);
      total = clockOf(part.duration);
      ticks.replaceChildren(
        ...part.ticks.slice(1).map((at) => {
          const line = document.createElementNS(ticks.namespaceURI, "line");
          for (const [name, value] of [["x1", at], ["x2", at], ["y1", "0"], ["y2", "8"]]) {
            line.setAttribute(name, value);
          }
          return line;
        }),
      );
      if (part.growing) rows = part.growing.planned;
      else {
        // the book is done: its record names the chapter's row
        const row = rows.find((each) => each.index === part.index);
        if (row) Object.assign(row, { chapter: n, state: "ready" });
      }
      for (const row of rows) drawRow(row);
      if (!part.markers_file) {
        markers = part.markers;
        drawMarkers();
      }
      if (loaded >= 0) showChapter(loaded);
      showTime(bookTime(), true);
      status.textContent = `${tr("player.chapter_ready", { n: n + 1 })} ${part.chapter.title}`;
      // waiting at the end of the chapter before it: go on into it
      if (held && audio.ended && loaded === n - 1) {
        showWaiting(false);
        seek(n, chapters[n].start, true);
      }
    }

    // one fetch at a time; a call while one runs gets that one, which goes on as long as
    // `wanted` says more chapters are playable
    let busy = null;
    function more() {
      busy ??= fetchMore().finally(() => {
        busy = null;
      });
      return busy;
    }
    async function fetchMore() {
      while (chapters.length < wanted) {
        let part;
        try {
          const answer = await fetch(data.growing.chapter + chapters.length, {
            credentials: "same-origin",
          });
          if (!answer.ok) break; // not there (yet): the next event asks again
          part = await answer.json();
        } catch {
          break; // the server is away: app.js says so for the stream
        }
        add(part);
      }
    }

    async function ended(job) {
      running = false;
      if (job.state === "done") wanted = Infinity; // every chapter there is, until a 404
      if (busy) await busy; // a fetch started before the end: then one for what is left
      for (;;) {
        const before = chapters.length;
        await more();
        if (chapters.length === before) break;
      }
      wanted = chapters.length;
      for (const row of rows) {
        if (row.chapter === null) {
          row.state = "missing";
          drawRow(row);
        }
      }
      if (held) showWaiting(false);
    }

    // the person played or moved while the player waited: it no longer goes on by itself
    for (const type of ["play", "seeking"]) {
      audio.addEventListener(type, () => {
        if (held) showWaiting(false);
      });
    }
    if (running) {
      // app.js's `follow`: this function's `follow` is the "scroll with the reading" switch
      window.follow(
        data.growing.events,
        (progress) => {
          const playable = (progress.playable || []).length;
          if (playable > wanted) {
            wanted = playable;
            more();
          }
        },
        ended,
      );
    }
    return {
      coming: () => running && later(),
      wait: () => showWaiting(true),
    };
  }

  // the offer to continue: it moves there and never plays by itself (D-300)
  const resume = document.getElementById("resume");
  if (resume) {
    const done = (message) => {
      resume.remove();
      play.focus();
      say(message);
    };
    document.getElementById("resume-continue").addEventListener("click", (event) => {
      const c = Number(event.currentTarget.dataset.chapter);
      const time = Number(event.currentTarget.dataset.time);
      if (!(c >= 0 && c < chapters.length) || !Number.isFinite(time)) return;
      following = true;
      back.hidden = true;
      highlight(chunkAt(time));
      seek(c, time, false);
      reveal(marked);
      const title = chapters[c].title;
      done(`${tr("player.chapter", { n: c + 1, total: chapters.length })} ${title}`);
    });
    document.getElementById("resume-start").addEventListener("click", () => {
      highlight(-1);
      seek(0, chapters[0].start, false);
      done(`${tr("player.chapter", { n: 1, total: chapters.length })} ${chapters[0].title}`);
    });
    // drawn disabled: a click before this script ran would be lost (#350)
    for (const id of ["resume-continue", "resume-start"]) {
      document.getElementById(id).disabled = false;
    }
    // "Continue listening" on the rail's shelf (#389, D-664) comes as #continue: the offer is
    // taken at once, so the page opens at the saved time, paused as ever (D-300)
    if (location.hash === "#continue") {
      history.replaceState(null, "", location.pathname + location.search);
      document.getElementById("resume-continue").click();
    }
  }
}

// ---- the context panel (#393): Changes, Chapters and Markers (#474) --------------------------
// Beside the desk from 1280 px, where its button hides and shows it; below, it opens over
// the page, takes the focus, and Esc or its button closes it and gives the focus back. The
// focus never reaches what it covers: when the focus leaves it, it closes (#444).
function contextPanel() {
  const listen = document.getElementById("listen");
  const panel = document.getElementById("context");
  const toggle = document.getElementById("panel-toggle");
  const close = document.getElementById("panel-close");
  if (!listen || !panel || !toggle || !close) return;
  const wide = window.matchMedia("(min-width: 1280px)");
  const tabs = [...panel.querySelectorAll('[role="tab"]')];
  let wideOpen = true;
  let narrowOpen = false;

  function show() {
    listen.classList.toggle("no-panel", !wideOpen);
    listen.classList.toggle("panel-open", narrowOpen);
    const open = wide.matches ? wideOpen : narrowOpen;
    toggle.setAttribute("aria-expanded", String(open));
    const name = open ? toggle.dataset.hide : toggle.dataset.show;
    toggle.setAttribute("aria-label", name);
    toggle.title = name;
  }

  function selected() {
    return tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
  }

  // the button and Esc give the focus to the toggle when the panel closes (#444); P keeps it
  // where it is, so Space and the arrows go on acting on the player (#461). If the focus is
  // in the panel when P closes it, it goes back where it was when P opened the panel, or to
  // the page if that was nowhere, never to the toggle, where Space would open the panel
  // again (#489); with no such place (the wide panel open from the start) it goes
  // to the toggle.
  let before = null; // the element focused when P opened the panel, or null
  function set(open, keep = false) {
    const active = document.activeElement;
    const inside = panel.contains(active);
    const back = before;
    if (!keep || !open) before = null;
    else if (!inside) before = active;
    if (wide.matches) wideOpen = open;
    else narrowOpen = open;
    show();
    if (open && !wide.matches) selected().focus();
    if (open || !inside) return;
    if (!keep || back === null) toggle.focus();
    else if (back.isConnected && back !== document.body && !panel.contains(back)) back.focus();
    else active.blur();
  }

  toggle.addEventListener("click", () => set(toggle.getAttribute("aria-expanded") !== "true"));
  // the Close button gives the focus to the toggle (#444), also where a click gives a button
  // no focus, as in Safari, so the focus was never inside the panel (#498)
  close.addEventListener("click", () => {
    set(false);
    toggle.focus();
  });
  // over the page the panel covers its own button, so the focus leaves it only by the keys
  // or to elsewhere: it closes, and the focus stays where it went. A press inside it is no
  // leaving, though the focus may go to the page (a press on its text, or in Safari on its
  // buttons, #447); the next move of the focus outside it closes it then.
  let pressing = false; // a pointer went down inside the panel and is not up yet
  panel.addEventListener("pointerdown", () => {
    pressing = true;
  });
  // the press ends with the pointer, and also when it can no longer be one: a key, a
  // context menu, or the window losing the focus (#394)
  function released() {
    pressing = false;
  }
  for (const type of ["pointerup", "pointercancel", "contextmenu", "blur"]) {
    window.addEventListener(type, released);
  }
  window.addEventListener("keydown", released, true);
  function left(to) {
    if (wide.matches || !narrowOpen || pressing || panel.contains(to)) return;
    narrowOpen = false;
    show();
  }
  // to nowhere (Tab past its last control reaches the browser's own bar) or to the page
  panel.addEventListener("focusout", (event) => left(event.relatedTarget));
  document.addEventListener("focusin", (event) => left(event.target));
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !wide.matches && narrowOpen) {
      event.preventDefault();
      set(false);
    }
  });
  wide.addEventListener?.("change", () => {
    narrowOpen = false;
    show();
  });

  // the tabs: one tab stop; the arrow keys, Home and End move between them (APG tabs)
  function choose(tab, focus) {
    for (const other of tabs) {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      document.getElementById(other.getAttribute("aria-controls")).hidden = !on;
    }
    if (focus) tab.focus();
  }
  for (const tab of tabs) {
    tab.addEventListener("click", () => choose(tab, false));
    tab.addEventListener("keydown", (event) => {
      const at = tabs.indexOf(tab);
      const to = {
        ArrowRight: (at + 1) % tabs.length,
        ArrowLeft: (at - 1 + tabs.length) % tabs.length,
        Home: 0,
        End: tabs.length - 1,
      }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      choose(tabs[to], true);
    });
  }
  show();
  for (const control of [toggle, close, ...tabs]) control.disabled = false;
  const markersTab = document.getElementById("tab-markers");
  return {
    byKey: () => set(toggle.getAttribute("aria-expanded") !== "true", true),
    // the Markers tab, the panel open: as P opens it, so the focus comes back where it was
    show: () => {
      if (markersTab) choose(markersTab, false);
      if (toggle.getAttribute("aria-expanded") !== "true") set(true, true);
    },
  };
}

document.addEventListener("DOMContentLoaded", readAlong);
