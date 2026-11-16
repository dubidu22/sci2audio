// The read-along player (#78, OU-02; D-294 to D-303) and the Listen page around it: the
// sweep, the dock and the context panel (#392, #393), Focus listening and the keys (#394).
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
  const total = clockOf(Number(timeline.max) || 0);

  // each sentence element's stretch of the book's timeline: the sweep runs over all of it,
  // also where empty spans share the element (one pass, for books of 1,000+ pages, #392)
  const stretch = new Map();
  for (const [start, end, , id] of chunks) {
    const known = stretch.get(id);
    if (known) known[1] = Math.max(known[1], end);
    else stretch.set(id, [start, end]);
  }

  let loaded = -1; // the chapter whose file the audio element holds
  let current = -1; // the chunk highlighted
  let marked = null; // its element
  let following = true; // false after the person scrolled away by hand (D-301)
  let frame = 0;
  let pending = null; // what to do once the file being loaded is ready
  let touched = false; // the person played or moved: from then on the position is kept
  let savedAt = 0; // when the position was last sent (performance.now())
  let focusing = false; // Focus listening is shown (#394)

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

  // ---- the sweep (#392, DESIGN.md "Reading sweep") ---------------------------------------
  // The reading yellow grows over the sentence for as long as the voice reads it: an
  // animation of its background-size (the Web Animations API; the page allows no style
  // attribute), held at the audio's time and rate. Under reduced motion nothing moves: the
  // whole sentence is highlighted at once (the stylesheet's `.now`).
  // In Focus listening a second sweep runs over the stage's copy of the sentence (#394).
  let sweep = null;
  let focusSweep = null;

  function sweepStop() {
    for (const one of [sweep, focusSweep]) if (one) one.cancel();
    sweep = null;
    focusSweep = null;
  }

  function sweepSync() {
    if (!marked || reduced.matches || !marked.animate) {
      sweepStop();
      return;
    }
    const [start, end] = stretch.get(marked.id) || [0, 0];
    const length = Math.max(end - start, 0.001) * 1000;
    const grow = [{ backgroundSize: "0% 100%" }, { backgroundSize: "100% 100%" }];
    const timing = { duration: length, easing: "linear", fill: "forwards" };
    if (!sweep) sweep = marked.animate(grow, timing);
    if (focusing && !focusSweep) focusSweep = focusNow.animate(grow, timing);
    if (!focusing && focusSweep) {
      focusSweep.cancel();
      focusSweep = null;
    }
    for (const one of [sweep, focusSweep]) {
      if (!one) continue;
      one.currentTime = Math.min(Math.max((bookTime() - start) * 1000, 0), length);
      one.playbackRate = audio.playbackRate || 1;
      if (audio.paused || pending || loaded < 0) one.pause();
      else one.play();
    }
  }
  reduced.addEventListener?.("change", sweepSync);

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
      // a sentence the voice read through keeps the pale tint (#392)
      if (element && !audio.paused && index > 0 && chunks[index - 1][3] === marked.id) {
        marked.classList.add("done");
      }
      marked.classList.remove("now");
      marked.removeAttribute("aria-current");
    }
    sweepStop();
    marked = element;
    stage();
    if (marked) {
      marked.classList.add("now");
      marked.setAttribute("aria-current", "true");
      sweepSync();
      announce(marked);
      reveal(marked);
    }
  }

  function update() {
    // while a file loads, its time is still 0: the jump's own highlight stands
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
    // a jump made while another file is still loading replaces that jump
    if (pending) audio.removeEventListener("loadedmetadata", pending);
    pending = null;
    const src = source(c);
    if (audio.getAttribute("src") !== src) {
      loaded = c;
      pending = () => {
        pending = null;
        go();
      };
      audio.addEventListener("loadedmetadata", pending, { once: true });
      audio.src = src;
    } else {
      loaded = c;
      go();
    }
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

  const chapterButtons = [...document.querySelectorAll(".chapter-button")];

  play.addEventListener("click", () => {
    touched = true;
    if (loaded < 0) seek(0, chapters[0].start, true);
    else if (audio.paused) audio.play().catch(() => {});
    else audio.pause();
  });
  document.getElementById("next-sentence").addEventListener("click", () => {
    playFrom(Math.min(current + 1, chunks.length - 1), !audio.paused);
  });
  document.getElementById("previous-sentence").addEventListener("click", () => {
    const into = current >= 0 ? bookTime() - chunks[current][0] : 0;
    const target = !audio.paused && into > RESTART_AFTER ? current : current - 1;
    playFrom(Math.max(target, 0), !audio.paused);
  });
  for (const button of chapterButtons) {
    button.addEventListener("click", () => toChapter(Number(button.dataset.chapter), true));
  }

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

  // a click (or a screen reader's Enter) on a sentence plays from it (D-298)
  text.addEventListener("click", (event) => {
    if (event.target.closest("summary, details")) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return; // the person is selecting text
    const sentence = event.target.closest(".s[data-chunk]");
    if (sentence) playFrom(Number(sentence.dataset.chunk), true);
  });

  // ---- speed (#152) -------------------------------------------------------------------
  // a new file resets `playbackRate` to `defaultPlaybackRate`, so both are set: the speed
  // stays across the chapters' files, jumps and the M4B; the voice keeps its pitch
  function applySpeed() {
    const value = Number(speed.value) || 1;
    audio.preservesPitch = true;
    if ("webkitPreservesPitch" in audio) audio.webkitPreservesPitch = true;
    if ("mozPreservesPitch" in audio) audio.mozPreservesPitch = true;
    audio.defaultPlaybackRate = value;
    audio.playbackRate = value;
    for (const one of [sweep, focusSweep]) if (one) one.playbackRate = value;
  }
  speed.addEventListener("change", applySpeed);
  audio.addEventListener("loadedmetadata", applySpeed);
  applySpeed();

  // ---- Focus listening (#394, DESIGN.md "Focus") ------------------------------------------
  // A mode of this page with no address of its own: the rail, the sheet and the panel give
  // way to the stage, which shows the sentence being read between its neighbours, copied
  // from the sheet's own elements (with their marks); the dock and the voice go on.
  const listen = document.getElementById("listen");
  const focusView = document.getElementById("focus-view");
  const focusOn = document.getElementById("focus-on");
  const focusOff = document.getElementById("focus-off");
  const focusPrevious = document.getElementById("focus-prev");
  const focusNow = document.getElementById("focus-now");
  const focusNext = document.getElementById("focus-next");
  const focusChapter = document.getElementById("focus-chapter");
  const order = [...stretch.keys()]; // the sentence elements in reading order
  const place = new Map(order.map((id, at) => [id, at]));

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
  }

  function setFocus(on) {
    if (on === focusing) return;
    // the panel over the page closes first, so it covers nothing when Focus ends
    if (on && listen.classList.contains("panel-open")) document.getElementById("panel-close").click();
    focusing = on;
    document.documentElement.classList.toggle("focus-listening", on);
    focusView.hidden = !on;
    sweepStop();
    stage();
    sweepSync();
    pad();
    if (on) {
      focusView.focus();
      return;
    }
    following = true;
    back.hidden = true;
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

  function stepSpeed(by) {
    const to = speed.selectedIndex + by;
    if (to < 0 || to >= speed.options.length) return;
    speed.selectedIndex = to;
    speed.dispatchEvent(new Event("change"));
    say(tr("player.speed_now", { speed: speed.options[to].text }));
  }

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    if (document.querySelector("dialog[open]") || typing(event.target)) return;
    const onControl = event.target instanceof Element && event.target.closest(CONTROLS);
    const key = event.key;
    if (key === "Escape" && focusing) setFocus(false);
    else if (key === " " && !onControl) play.click();
    else if ((key === "ArrowLeft" || key === "ArrowRight") && !onControl) {
      const by = key === "ArrowRight" ? 1 : -1;
      if (event.shiftKey) toChapter(chapterOfCurrent() + by, !audio.paused);
      else document.getElementById(by > 0 ? "next-sentence" : "previous-sentence").click();
    } else if (key === "-") stepSpeed(-1);
    else if (key === "+" || key === "=") stepSpeed(1);
    else if (key === "f" || key === "F") setFocus(!focusing);
    else if ((key === "p" || key === "P") && !focusing) document.getElementById("panel-toggle").click();
    else return;
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
  audio.addEventListener("playing", sweepSync);
  audio.addEventListener("waiting", sweepSync);
  audio.addEventListener("ratechange", sweepSync);
  audio.addEventListener("pause", () => {
    showPlaying(false);
    update();
    sweepSync();
    keepIfTouched();
  });
  audio.addEventListener("seeked", () => {
    update();
    sweepSync();
  });
  audio.addEventListener("timeupdate", () => {
    if (audio.paused) update();
  });
  audio.addEventListener("ended", () => {
    // the next chapter's file follows by itself (D-296); the M4B is one file
    if (data.mode === "mp3" && loaded >= 0 && loaded < chapters.length - 1) {
      seek(loaded + 1, chapters[loaded + 1].start, true);
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
  seek(0, chapters[0].start, false);
  contextPanel();

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
    // drawn disabled: a click before this script ran would be lost (#350, review N1)
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

// ---- the context panel (#393): Changes and Chapters ----------------------------------------
// Beside the desk from 1280 px, where its button hides and shows it; below, it opens over
// the page, takes the focus, and Esc or its button closes it and gives the focus back. The
// focus never reaches what it covers: when the focus leaves it, it closes (#444 review S2).
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

  function set(open) {
    if (wide.matches) wideOpen = open;
    else narrowOpen = open;
    show();
    if (open && !wide.matches) selected().focus();
    if (!open) toggle.focus();
  }

  toggle.addEventListener("click", () => set(toggle.getAttribute("aria-expanded") !== "true"));
  close.addEventListener("click", () => set(false));
  // over the page the panel covers its own button, so the focus leaves it only by the keys
  // or to elsewhere: it closes, and the focus stays where it went. A press inside it is no
  // leaving, though the focus may go to the page (a press on its text, or in Safari on its
  // buttons, #447); the next move of the focus outside it closes it then.
  let pressing = false; // a pointer went down inside the panel and is not up yet
  panel.addEventListener("pointerdown", () => {
    pressing = true;
  });
  for (const type of ["pointerup", "pointercancel"]) {
    window.addEventListener(type, () => {
      pressing = false;
    });
  }
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
}

document.addEventListener("DOMContentLoaded", readAlong);
