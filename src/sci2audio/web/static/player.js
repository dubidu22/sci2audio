// The read-along player (#78, OU-02; D-294 to D-303). Loaded only by the listen page,
// after app.js, whose `tr` and `say` it uses (D-302).
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
  const bar = document.querySelector(".player-bar");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

  let loaded = -1; // the chapter whose file the audio element holds
  let current = -1; // the chunk highlighted
  let marked = null; // its element
  let following = true; // false after the person scrolled away by hand (D-301)
  let frame = 0;
  let pending = null; // what to do once the file being loaded is ready

  // the bar is pinned to the top only while it takes at most a quarter of the window, and
  // then nothing focused or scrolled to may hide under it (WCAG 1.4.10, 2.4.11). Pinning
  // does not change the bar's height, so the observer below does not loop.
  function pad() {
    const fits = bar.offsetHeight <= window.innerHeight / 4;
    bar.classList.toggle("pinned", fits);
    document.documentElement.style.scrollPaddingTop = fits ? `${bar.offsetHeight + 8}px` : "";
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
  }

  function barBottom() {
    return getComputedStyle(bar).position === "sticky" ? bar.getBoundingClientRect().bottom : 0;
  }

  function visible(element) {
    const box = element.getBoundingClientRect();
    return box.top >= barBottom() && box.bottom <= window.innerHeight;
  }

  function reveal(element) {
    if (!element || !follow.checked || !following || visible(element)) return;
    const behavior = reduced.matches ? "auto" : "smooth";
    const box = element.getBoundingClientRect();
    const top = barBottom();
    if (box.height > window.innerHeight - top) {
      // taller than the window under the bar (a long code listing, #280): its start, where
      // the spoken notice stands, goes just under the bar instead of out of sight above it
      window.scrollBy({ top: box.top - top - 8, behavior });
      return;
    }
    element.scrollIntoView({ block: "center", behavior });
  }

  // the highlight never speaks: no live region follows the reading (D-300)
  function highlight(index) {
    if (index === current) return;
    if (marked) {
      marked.classList.remove("now");
      marked.removeAttribute("aria-current");
    }
    current = index;
    marked = index < 0 ? null : document.getElementById(chunks[index][3]);
    if (marked) {
      marked.classList.add("now");
      marked.setAttribute("aria-current", "true");
      reveal(marked);
    }
  }

  function update() {
    // while a file loads, its time is still 0: the jump's own highlight stands
    if (loaded < 0 || pending) return;
    highlight(chunkAt(bookTime()));
  }

  function tick() {
    update();
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

  play.addEventListener("click", () => {
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
  document.getElementById("next-chapter").addEventListener("click", () => {
    toChapter(chapterOfCurrent() + 1, !audio.paused);
  });
  document.getElementById("previous-chapter").addEventListener("click", () => {
    toChapter(chapterOfCurrent() - 1, !audio.paused);
  });
  for (const button of document.querySelectorAll(".chapter-button")) {
    button.addEventListener("click", () => toChapter(Number(button.dataset.chapter), true));
  }

  // a click (or a screen reader's Enter) on a sentence plays from it (D-298)
  text.addEventListener("click", (event) => {
    if (event.target.closest("summary, details")) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return; // the person is selecting text
    const sentence = event.target.closest(".s[data-chunk]");
    if (sentence) playFrom(Number(sentence.dataset.chunk), true);
  });

  // ---- following the reading (D-301) -----------------------------------------------------

  function scrolledByHand() {
    if (!following || !follow.checked) return;
    following = false;
    back.hidden = false;
  }
  window.addEventListener("wheel", scrolledByHand, { passive: true });
  window.addEventListener("touchmove", scrolledByHand, { passive: true });
  document.addEventListener("keydown", (event) => {
    if (!SCROLL_KEYS.has(event.key)) return;
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

  audio.addEventListener("play", () => {
    play.textContent = tr("player.pause");
    if (!frame) frame = requestAnimationFrame(tick);
  });
  audio.addEventListener("pause", () => {
    play.textContent = tr("player.play");
    update();
  });
  audio.addEventListener("seeked", update);
  audio.addEventListener("timeupdate", () => {
    if (audio.paused) update();
  });
  audio.addEventListener("ended", () => {
    // the next chapter's file follows by itself (D-296); the M4B is one file
    if (data.mode === "mp3" && loaded >= 0 && loaded < chapters.length - 1) {
      seek(loaded + 1, chapters[loaded + 1].start, true);
    }
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
}

document.addEventListener("DOMContentLoaded", readAlong);
