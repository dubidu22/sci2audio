// The sci2audio interface's one script (#77, D-101): talks to the JSON API of this server
// only. Its strings come from the page's data block, in the page's language (D-256,
// D-288 to D-291).
"use strict";

const ANNOUNCE_EVERY = 30000; // ms between progress announcements, phase changes aside (D-253)
const LOST_AFTER = 5000; // ms an event stream may stay away before the page says the server is lost
const SHELF_EVERY = 2000; // ms between the shelf's questions on a page that holds no stream of the job

let STRINGS = {};

// A text with plural forms picks `one` for exactly 1, else `other`, by the value `n`: the
// rule of English and German (D-290).
function tr(key, values) {
  let text = STRINGS[key];
  if (text === undefined && values && "n" in values) {
    text = STRINGS[`${key}.${Number(values.n) === 1 ? "one" : "other"}`];
  }
  text = text ?? key;
  return text.replace(/\{(\w+)\}/g, (all, name) => (values && name in values ? values[name] : all));
}

// A decimal number with the page language's decimal sign, no trailing zeros, no grouping.
function decimal(value) {
  const text = Number(value).toFixed(2).replace(/\.?0+$/, "");
  return text.replace(".", STRINGS["common.decimal"] ?? ".");
}

// An error in the page's language: the table's sentence for its kind, then the app's own
// words as details in English (D-291); an unknown kind shows those words alone.
function failureOf(kind, words) {
  const reason = kind ? STRINGS[`error.${kind}`] : undefined;
  return reason === undefined ? { text: words || "" } : { text: reason, details: words };
}

function explain(error) {
  return error.failure || error.message;
}

function say(said, focus) {
  const message = document.getElementById("message");
  if (!message) return;
  if (typeof said === "string") {
    message.textContent = said;
  } else {
    message.textContent = said.text;
    if (said.details) {
      const details = document.createElement("span");
      details.lang = "en";
      details.textContent = said.details;
      message.append(` ${tr("common.details")} `, details);
    }
  }
  if (focus) message.focus();
}

async function send(url, options) {
  let response;
  try {
    response = await fetch(url, Object.assign({ credentials: "same-origin" }, options));
  } catch (error) {
    throw new Error(tr("js.lost"));
  }
  const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    const failure = new Error(data.message || response.statusText);
    failure.kind = data.error;
    failure.failure = failureOf(data.error, data.message || response.statusText);
    throw failure;
  }
  return data;
}

function json(method, body) {
  return { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
}

function reloadAt(hash) {
  history.replaceState(null, "", `${location.pathname}#${hash}`);
  location.reload();
}

// Follows a job's events (D-201): `progress` gets each progress, `end` the final job. A
// stream that breaks off is reopened by the browser on its own and stays CONNECTING while
// the server is away, so a stream that hasn't reopened LOST_AFTER ms after an error counts
// as lost: the page says so and stops trying.
// A page holds one stream per job, however many parts of it follow that job (#409 B2): a
// browser keeps at most six connections to this server, and every open stream holds one
// for as long as its job runs. A part that follows later gets the latest progress at once.
// `quiet` is for a part that only shows the job on the side (the rail's shelf): it adds no
// word when the stream is lost, since the page's own part says so.
const STREAMS = new Map();

function follow(url, progress, end, quiet) {
  const part = { progress, end, quiet };
  const known = STREAMS.get(url);
  if (known) {
    known.parts.push(part);
    if (known.last) progress(known.last);
    return;
  }
  const events = new EventSource(url);
  const stream = { parts: [part], last: null };
  STREAMS.set(url, stream);
  let ended = false;
  let waiting = null;
  function told(shown) {
    stream.last = shown;
    stream.parts.forEach((each) => each.progress(shown));
  }
  function lost() {
    clearTimeout(waiting);
    events.close();
    STREAMS.delete(url);
    if (stream.parts.some((each) => !each.quiet)) say(tr("js.lost"), true);
  }
  events.addEventListener("open", () => {
    clearTimeout(waiting);
    waiting = null;
  });
  events.addEventListener("snapshot", (event) => {
    const job = JSON.parse(event.data);
    if (job.progress) told(job.progress);
  });
  events.addEventListener("progress", (event) => told(JSON.parse(event.data) || {}));
  events.addEventListener("end", (event) => {
    ended = true;
    events.close();
    STREAMS.delete(url);
    const job = JSON.parse(event.data);
    stream.parts.forEach((each) => each.end(job));
  });
  events.addEventListener("error", () => {
    if (ended) return;
    if (events.readyState === EventSource.CLOSED) lost();
    else if (waiting === null) waiting = setTimeout(lost, LOST_AFTER);
  });
}

// ---- the start page --------------------------------------------------------------------

async function openAndAnalyse(store) {
  say(tr("js.opening"));
  try {
    const doc = await store();
    try {
      await send("/api/v1/jobs", json("POST", { kind: "script", document: doc.id, settings: {} }));
    } catch (error) {
      // busy: the document page shows the running job and an Analyse button
    }
    location.assign(`/documents/${doc.id}`);
  } catch (error) {
    say(explain(error), true);
  }
}

function startPage() {
  const fileForm = document.getElementById("open-file");
  if (fileForm) {
    const open = () => {
      const body = new FormData(fileForm);
      openAndAnalyse(() => send(fileForm.dataset.api, { method: "POST", body }));
    };
    fileForm.addEventListener("submit", (event) => {
      event.preventDefault();
      open();
    });
    dropOnto(fileForm, open);
  }
  const textForm = document.getElementById("open-text");
  if (textForm) {
    textForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const fields = new FormData(textForm);
      const body = { text: fields.get("text"), name: fields.get("name") || "" };
      openAndAnalyse(() => send(textForm.dataset.api, json("POST", body)));
    });
  }
}

// A file dropped onto the opener (#417): one file becomes the chosen file and opens as
// "Open and analyse" does (same request, so the same errors and size limit); the file
// input stays the keyboard way. The hint names dropping only once this is wired.
function dropOnto(form, open) {
  const input = form.querySelector('input[type="file"]');
  if (!input) return;
  let depth = 0; // dragenter and dragleave come for every child the file passes over
  const over = (on) => form.classList.toggle("over", on);
  const carriesFiles = (event) => [...(event.dataTransfer?.types || [])].includes("Files");
  form.addEventListener("dragenter", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    depth += 1;
    over(true);
  });
  form.addEventListener("dragover", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  form.addEventListener("dragleave", () => {
    depth = Math.max(depth - 1, 0);
    if (!depth) over(false);
  });
  form.addEventListener("drop", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    depth = 0;
    over(false);
    const dropped = event.dataTransfer.files;
    if (dropped.length !== 1) {
      say(tr("js.drop_one"), true);
      return;
    }
    input.files = dropped;
    open();
  });
  // a file dropped beside the opener would open in the tab and leave the app: the page
  // takes no file anywhere else (#446 review N1)
  for (const type of ["dragover", "drop"]) {
    document.addEventListener(type, (event) => {
      if (!carriesFiles(event) || form.contains(event.target)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "none";
    });
  }
  const hint = document.getElementById("drop-hint");
  if (hint) hint.hidden = false;
}

// ---- the library's search (#416) ---------------------------------------------------------

// The text as the server's `library.folded` compares it: case and accents aside.
function folded(text) {
  return text.toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replaceAll("ß", "ss");
}

// Filters the rows in place as the person types; the form itself still works (GET /?q=).
function librarySearch() {
  const form = document.getElementById("search");
  const input = document.getElementById("q");
  const region = document.getElementById("library");
  const none = document.getElementById("no-match");
  if (!form || !input || !region || !none) return;
  const rows = [...region.querySelectorAll("tbody tr[data-find]")];
  const filter = () => {
    // folded and cut as the server cuts it (#462), so the script and the page agree
    const query = input.value.split(/\s+/).filter(Boolean).join(" ").slice(0, 200);
    const words = folded(query).split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const row of rows) {
      row.hidden = !words.every((word) => row.dataset.find.includes(word));
      if (!row.hidden) shown += 1;
    }
    region.hidden = shown === 0;
    none.textContent = shown === 0 ? tr("library.search_none", { q: query }) : "";
    const url = new URL(location.href);
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    history.replaceState(history.state, "", url);
  };
  input.addEventListener("input", filter);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    filter();
  });
}

// ---- removing a document (#120, D-359 to D-362) ------------------------------------------

function removal() {
  for (const button of document.querySelectorAll("button.remove-now")) {
    let sending = false;
    button.addEventListener("click", async () => {
      // one request per press; the button keeps the focus while it runs (D-361)
      if (sending) return;
      sending = true;
      button.setAttribute("aria-disabled", "true");
      say(tr("remove.removing"));
      let removed;
      try {
        removed = await send(`/api/v1/documents/${button.dataset.document}`, { method: "DELETE" });
      } catch (error) {
        sending = false;
        button.removeAttribute("aria-disabled");
        say(explain(error), true);
        return;
      }
      let text = tr("remove.done", { name: removed.name });
      let stays = "";
      if (removed.audiobook_folder) stays = tr("remove.stays_folder", { folder: removed.audiobook_folder });
      else if (button.dataset.audio) stays = tr("remove.stays");
      const page = document.getElementById("document");
      if (page) {
        // the document page: its steps make no sense any more; the result replaces them
        page.remove();
        // the header keeps the title; its tabs and meta lead to what is gone
        document.querySelectorAll(".paper-head .tabs, .paper-head .meta").forEach((part) => part.remove());
        const done = document.getElementById("removed");
        document.getElementById("removed-title").textContent = text;
        document.getElementById("removed-text").textContent = stays;
        done.hidden = false;
        document.getElementById("removed-title").focus();
        return;
      }
      // the library: the document's row leaves the table and the counts follow; the
      // message says what happened
      const row = button.closest("tr");
      const body = row && row.parentElement;
      if (row) row.remove();
      const left = body ? body.querySelectorAll("tr").length : 0;
      const count = document.getElementById("library-count");
      if (count) count.textContent = tr("library.sub", { n: left });
      const rail = document.getElementById("nav-library");
      if (rail) {
        rail.setAttribute("aria-label", `${tr("nav.library")}, ${tr("nav.documents", { n: left })}`);
        const number = rail.querySelector(".count");
        if (number) number.textContent = String(left);
      }
      if (body && !left) {
        document.getElementById("library").remove();
        const none = document.getElementById("no-documents");
        if (none) none.hidden = false;
      }
      if (stays) text = `${text} ${stays}`;
      say(text, true);
    });
    button.disabled = false; // drawn disabled until this click is attached (#427)
  }
}

// ---- the document page -----------------------------------------------------------------

function chosen(name) {
  return Array.from(document.querySelectorAll(`input[name=${name}]`));
}

// the choices on the check form, in the order of the page's `shown` block; the text's
// language is part of them: changing it needs a new analysis (#212)
function controls(shown) {
  const language = document.getElementById("language");
  return {
    switched_off: chosen("category").filter((c) => !c.checked).map((c) => c.value).sort(),
    // in the list's order: the order they are read in (#119)
    chapters: chosen("chapter").filter((c) => c.checked).map((c) => Number(c.value)),
    language: language ? language.value : shown.language,
  };
}

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

// Move up and Move down on the chapter list (#119): the list's order is the order the
// chapters are read in. The buttons are drawn disabled and enabled only once their clicks
// are bound, so no early click is lost (#350, #427). The focus stays on the pressed button,
// or goes to its sibling when that one becomes disabled at the end of the list.
function chapterOrder(changed) {
  const list = document.querySelector("ol.choices");
  if (!list || !list.querySelector(".move")) return;
  const items = () => Array.from(list.children);
  function mark() {
    const all = items();
    all.forEach((item, n) => {
      item.querySelector(".move-up").disabled = n === 0;
      item.querySelector(".move-down").disabled = n === all.length - 1;
    });
  }
  function move(item, by, button) {
    const all = items();
    const at = all.indexOf(item);
    const to = at + by;
    if (to < 0 || to >= all.length) return;
    if (by < 0) list.insertBefore(item, all[to]);
    else list.insertBefore(item, all[to].nextSibling);
    mark();
    const other = item.querySelector(by < 0 ? ".move-down" : ".move-up");
    (button.disabled ? other : button).focus();
    say(tr("js.moved", { title: item.dataset.title, n: to + 1, total: all.length }));
    changed();
  }
  for (const item of items()) {
    const up = item.querySelector(".move-up");
    const down = item.querySelector(".move-down");
    up.addEventListener("click", () => move(item, -1, up));
    down.addEventListener("click", () => move(item, 1, down));
  }
  mark();
}

function documentPage() {
  const box = document.getElementById("document");
  if (!box) return;
  const id = box.dataset.id;
  const shown = JSON.parse(box.dataset.shown);
  const make = document.getElementById("make");
  const makeNote = document.getElementById("make-note");
  const changed = document.getElementById("changed");
  const blockedFirst = make.dataset.blocked;

  function refresh() {
    if (!changed) return;
    const differs = !same(controls(shown), shown);
    changed.hidden = !differs;
    // the controls differ from the report: the update comes first, as no chapter on the
    // report may be the very thing being changed; a missing analysis or voice stays first
    let blocked = blockedFirst;
    if (differs && (!blocked || blocked === "needs_chapters")) blocked = "needs_update";
    make.dataset.blocked = blocked;
    if (blocked) {
      make.setAttribute("aria-disabled", "true");
      makeNote.textContent = tr(`make.${blocked}`);
      makeNote.hidden = false;
    } else {
      make.removeAttribute("aria-disabled");
      makeNote.hidden = true;
    }
  }
  for (const input of [...chosen("category"), ...chosen("chapter")]) {
    input.addEventListener("change", refresh);
  }
  const languageChoice = document.getElementById("language");
  if (languageChoice) languageChoice.addEventListener("change", refresh);
  const all = document.getElementById("choose-all");
  const none = document.getElementById("choose-none");
  chapterOrder(refresh);
  // the page's buttons are drawn disabled, so a click before this script ran waits instead
  // of doing nothing; each is enabled once its click is attached (#350, #427)
  function wire(button, click) {
    if (!button) return;
    button.addEventListener("click", click);
    button.disabled = false;
  }
  wire(all, () => { chosen("chapter").forEach((c) => { c.checked = true; }); refresh(); });
  wire(none, () => { chosen("chapter").forEach((c) => { c.checked = false; }); refresh(); });

  async function analyse(settings) {
    say(tr("js.analysing"), true);
    try {
      const job = await send("/api/v1/jobs", json("POST", { kind: "script", document: id, settings }));
      follow(`/api/v1/jobs/${job.id}/events`, () => {}, () => reloadAt("step-check"));
    } catch (error) {
      say(explain(error), true);
    }
  }
  const choices = document.getElementById("choices");
  if (choices) {
    choices.addEventListener("submit", (event) => {
      event.preventDefault();
      analyse(controls(shown));
    });
    const update = document.getElementById("update");
    if (update) update.disabled = false;
  }
  wire(document.getElementById("analyse"), () => analyse({}));
  if (box.dataset.events) follow(box.dataset.events, () => {}, () => reloadAt("step-check"));

  const speed = document.getElementById("speed");
  const speedValue = document.getElementById("speed-value");
  function showSpeed() {
    const text = tr("voice.speed_value", { value: decimal(speed.value) });
    speedValue.textContent = text;
    speed.setAttribute("aria-valuetext", text);
  }
  speed.addEventListener("input", showSpeed);
  showSpeed();
  // how fast the voice reads letters it spells out (#295)
  const letterPace = () => {
    const chosen = document.querySelector('input[name="letter-pace"]:checked');
    return chosen ? chosen.value : "normal";
  };
  const voice = document.getElementById("voice");
  const languageOf = (option) => ((option && option.dataset.language) || "").split("-")[0];
  // the voice to remember: the page's, unless the saved one speaks another language
  const rememberedVoice = (savedVoice) => {
    const savedOption = [...voice.options].find((option) => option.value === savedVoice);
    const same = !savedOption || languageOf(savedOption) === languageOf(voice.selectedOptions[0]);
    return same ? voice.value : savedVoice;
  };

  const preview = document.getElementById("preview");
  if (preview) {
    const audio = document.getElementById("preview-audio");
    // the sample sentence follows the voice's language, unless the person wrote their own
    const sample = document.getElementById("preview-text");
    const samples = JSON.parse(sample.dataset.samples || "{}");
    voice.addEventListener("change", () => {
      const chosen = voice.selectedOptions[0];
      const language = ((chosen && chosen.dataset.language) || "en").split("-")[0];
      const own = !Object.values(samples).includes(sample.value);
      if (own || !samples[language]) return;
      sample.value = samples[language];
      sample.lang = language;
    });
    preview.addEventListener("submit", async (event) => {
      event.preventDefault();
      say(tr("js.listening"));
      try {
        const body = {
          voice: voice.value,
          speed: Number(speed.value),
          letter_pace: letterPace(),
          text: document.getElementById("preview-text").value,
        };
        const job = await send("/api/v1/voices/preview", json("POST", body));
        follow(`/api/v1/jobs/${job.id}/events`, () => {}, (ended) => {
          if (ended.state !== "done" || !ended.files.length) {
            say(ended.error ? failureOf(ended.error.error, ended.error.message) : tr(`job.state_${ended.state}`), true);
            return;
          }
          audio.src = `/api/v1/jobs/${ended.id}/files/${encodeURIComponent(ended.files[0].name)}`;
          audio.hidden = false;
          say(tr("js.preview_ready"));
          audio.focus();
        });
      } catch (error) {
        say(explain(error), true);
      }
    });
    const listen = document.getElementById("preview-listen");
    if (listen) listen.disabled = false;
  }

  wire(make, async () => {
    if (make.dataset.blocked) {
      makeNote.hidden = false;
      say(makeNote.textContent, true);
      return;
    }
    const folder = document.getElementById("output-folder").value.trim();
    if (!/^(\/|[A-Za-z]:[\\/]|\\\\)/.test(folder)) {
      say(tr("js.folder_needed"), true);
      return;
    }
    say(tr("js.starting"));
    try {
      const saved = await send("/api/v1/settings");
      // the language the report on screen was made with (#212)
      const settings = {
        language: shown.language,
        switched_off: shown.switched_off,
        voice: voice.value,
        speed: Number(speed.value),
        letter_pace: letterPace(),
        subtitles: document.getElementById("subtitles").checked,
        output_folder: folder,
      };
      const job = await send("/api/v1/jobs", json("POST", {
        kind: "audio", document: id, settings: { ...settings, chapters: shown.chapters },
      }));
      // remembered for the next document once the audiobook has started (D-246); a start
      // refused as busy changes nothing; chapters stay with the document. The voice is
      // remembered only in place of a voice of the same language (or none): a German book
      // read by the German voice keeps the English voice chosen before (#211)
      // the text's language belongs to this document and is not remembered (D-521)
      const remembered = {
        ...settings,
        language: saved.settings.language,
        voice: rememberedVoice(saved.settings.voice),
      };
      await send("/api/v1/settings", json("PUT", remembered)).catch(() => {});  // the job runs either way
      location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(explain(error), true);
    }
  });
  refresh();
}

// ---- the job page ----------------------------------------------------------------------

function describe(progress) {
  const parts = [];
  if (progress.phase) parts.push(STRINGS[`phase.${progress.phase}`] ?? progress.phase);
  if (progress.phase === "reading" && progress.pages) parts.push(tr("js.pages", { done: progress.page, n: progress.pages }));
  if (progress.chunks_total) parts.push(tr("js.sentences", { done: progress.chunks_done, n: progress.chunks_total }));
  if (progress.phase === "speaking") {
    if (progress.seconds_left == null) parts.push(tr("js.measuring"));
    else {
      const minutes = Math.max(1, Math.ceil(progress.seconds_left / 60));
      parts.push(tr("js.minutes_left", { n: minutes }));
    }
  }
  if (progress.bytes_total) parts.push(tr("js.percent", { n: Math.floor((100 * progress.bytes_done) / progress.bytes_total) }));
  return parts.join(", ");
}

function fraction(progress) {
  if (progress.phase === "reading" && progress.pages) return progress.page / progress.pages;
  if (progress.chunks_total) return progress.chunks_done / progress.chunks_total;
  if (progress.bytes_total) return progress.bytes_done / progress.bytes_total;
  return null;
}

// Speaks progress at most every ANNOUNCE_EVERY ms, and at once when the phase changes, so a
// screen reader is not flooded (D-253). The visible text follows every event.
function announcer(region) {
  let last = 0;
  let phase = null;
  return (progress, text) => {
    const now = Date.now();
    if (progress.phase !== phase || now - last >= ANNOUNCE_EVERY) {
      phase = progress.phase;
      last = now;
      region.textContent = text;
    }
  };
}

function jobPage() {
  const box = document.getElementById("job");
  if (!box) return;
  const kind = box.dataset.kind;
  const doc = box.dataset.document;

  // the page's buttons are drawn disabled, so a click before this script ran waits instead
  // of doing nothing; each is enabled once its click is attached (#177)
  const cancel = document.getElementById("job-cancel");
  if (cancel) {
    cancel.addEventListener("click", async () => {
      try {
        await send(box.dataset.cancel, { method: "POST" });
      } catch (error) {
        say(explain(error), true);
      }
    });
    cancel.disabled = false;
  }

  if (box.dataset.state !== "running") {
    // a job that ended before its page loaded: its result is what the person came for
    const result = document.getElementById("result");
    if (result && !location.hash) result.focus();
    return;
  }
  const bar = document.getElementById("job-bar");
  const text = document.getElementById("job-progress");
  const announce = announcer(document.getElementById("job-status"));
  follow(box.dataset.events, (progress) => {
    const shown = describe(progress);
    text.textContent = shown;
    const part = fraction(progress);
    if (part == null) bar.removeAttribute("value");
    else bar.value = Math.round(100 * part);
    bar.setAttribute("aria-valuetext", shown);
    announce(progress, shown);
  }, () => {
    if (kind === "script" && doc) {
      location.assign(`/documents/${doc}#step-check`);
    } else {
      reloadAt("result");
    }
  });
}

// ---- the audiobook job inline on Prepare (#391) -----------------------------------------

// A size as the server writes it (`Strings.size`): bytes, KB or MB, decimal units.
function sizeText(n) {
  if (n >= 1000000) return tr("common.megabytes", { n: decimal((n / 1000000).toFixed(1)) });
  if (n >= 1000) return tr("common.kilobytes", { n: Math.round(n / 1000) });
  return tr("common.bytes", { n });
}

// Where the job stands, from its latest progress (D-695): the chapter being spoken counted
// from 1, one past the chapters once every one is spoken, 0 before the first chunk. The
// progress names the last finished chunk; when that one ended its chapter, the next began.
function chapterNow(progress) {
  const chapters = progress.chapters || 0;
  if (progress.phase === "encoding" || progress.phase === "done") return chapters + 1;
  const number = progress.chapter_number || 0;
  if (progress.phase !== "speaking" || !number) return 0;
  if (progress.chapter_done) return number >= chapters ? chapters + 1 : number + 1;
  return number;
}

// The running card's words, as pages._running_lines draws them first.
function cardShown(progress) {
  const now = chapterNow(progress);
  const chapters = progress.chapters || 0;
  let head;
  if (progress.phase === "speaking" && now && now <= chapters) {
    head = tr("making.speaking", { n: now, total: chapters });
  } else {
    const words = STRINGS[`phase.${progress.phase}`] ?? tr("job.state_running");
    head = words.charAt(0).toUpperCase() + words.slice(1);
  }
  const part = fraction(progress);
  const left = [];
  if (part != null) left.push(tr("js.percent", { n: Math.floor(100 * Math.min(1, part)) }));
  if (progress.phase === "speaking") {
    if (progress.seconds_left == null) left.push(tr("js.measuring"));
    else left.push(tr("js.minutes_left", { n: Math.max(1, Math.ceil(progress.seconds_left / 60)) }));
  }
  const sentences = progress.chunks_total
    ? tr("js.sentences", { done: progress.chunks_done || 0, n: progress.chunks_total })
    : "";
  // what a screen reader is told: the same words, as one sentence
  const said = [head, sentences, ...left].filter(Boolean).join(", ");
  return { head, left: left.join(" · "), said, part, now, chapters, sentences };
}

// One segment per chapter: done, the one being spoken, or to come (classes only: the CSP
// forbids style attributes).
function drawSegments(box, chapters, now) {
  if (!box) return;
  while (box.children.length < chapters) {
    const seg = document.createElement("span");
    seg.className = "seg";
    box.append(seg);
  }
  Array.from(box.children).forEach((seg, n) => {
    seg.classList.toggle("done", n + 1 < now);
    seg.classList.toggle("now", n + 1 === now);
  });
}

// Waits until the job is no longer running, asking the server, never trusting the stream
// alone: Cancel frees the speech cache only once the voice has stopped writing to it.
// Wait until the job at `url` has left "running"; give up after `limit` ms (a voice stuck
// in native code may ignore the cancel): then nothing may be deleted (#433 N3)
async function stopped(url, limit) {
  const until = Date.now() + limit;
  for (;;) {
    const job = await send(url);
    if (job.state !== "running") return true;
    if (Date.now() >= until) return false;
    await new Promise((done) => setTimeout(done, 250));
  }
}

function makingCard() {
  const card = document.getElementById("making");
  if (!card) return;
  const id = card.dataset.job;
  const doc = card.dataset.document;
  const settings = JSON.parse(card.dataset.settings || "null") || {};
  const jobUrl = `/api/v1/jobs/${id}`;
  function wire(button, click) {
    if (!button) return;
    button.addEventListener("click", click);
    button.disabled = false;
  }

  // Resume, Make it again and Replace start the audiobook again with the job's settings;
  // the spoken sentences in the cache are used again (Pause is today's cancel, #391)
  async function restart(overwrite) {
    try {
      const job = await send("/api/v1/jobs", json("POST", { kind: "audio", document: doc, settings, overwrite }));
      location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(explain(error), true);
    }
  }
  wire(document.getElementById("job-replace"), () => restart(true));
  wire(document.getElementById("job-again"), () => restart(false));

  const free = document.getElementById("cache-free");
  wire(free, async () => {
    try {
      await send(`/api/v1/documents/${doc}/chunks`, { method: "DELETE" });
      const text = document.getElementById("cache-text") || document.getElementById("job-kept");
      if (text) text.textContent = tr("js.freed");
      free.remove();
      say(tr("js.freed"), true);
    } catch (error) {
      say(explain(error), true);
    }
  });

  if (card.dataset.state !== "running") {
    // a job that ended before its page loaded: its result is what the person came for
    const result = document.getElementById("result");
    if (result && location.pathname.startsWith("/jobs/") && !location.hash) result.focus();
    return;
  }

  let leaving = false; // Cancel's own steps decide where the page goes next
  wire(document.getElementById("job-pause"), async () => {
    say(tr("js.pausing"));
    try {
      await send(card.dataset.cancel, { method: "POST" });
    } catch (error) {
      say(explain(error), true);
    }
  });

  // Cancel = Pause, then, once the job has stopped, free the speech cache (D-694): the
  // DELETE never goes out while the voice may still write a chunk
  const cancelBox = document.getElementById("cancel-box");
  const cancelSize = document.getElementById("cancel-size");
  if (cancelBox) {
    cancelBox.addEventListener("toggle", async () => {
      if (!cancelBox.open || !cancelSize) return;
      try {
        const found = await send(`/api/v1/documents/${doc}`);
        cancelSize.textContent = tr("making.cancel_size", { size: sizeText(found.speech_cache_bytes) });
      } catch (error) {
        // the size drawn with the page stays
      }
    });
  }
  const cancel = document.getElementById("job-cancel");
  wire(cancel, async () => {
    if (leaving) return;
    leaving = true;
    cancel.setAttribute("aria-disabled", "true");
    say(tr("js.cancelling"));
    try {
      await send(card.dataset.cancel, { method: "POST" });
    } catch (error) {
      if (error.kind !== "finished") {
        leaving = false;
        cancel.removeAttribute("aria-disabled");
        say(explain(error), true);
        return;
      }
    }
    try {
      if (!(await stopped(jobUrl, Number(card.dataset.stopWait)))) {
        leaving = false;
        cancel.removeAttribute("aria-disabled");
        say(tr("js.not_stopped"), true);
        return;
      }
      say(tr("js.deleting"));
      await send(`/api/v1/documents/${doc}/chunks`, { method: "DELETE" });
    } catch (error) {
      say(explain(error), true);
      leaving = false;
      cancel.removeAttribute("aria-disabled");
      return;
    }
    reloadAt("making");
  });

  const bar = document.getElementById("job-bar");
  const chapter = document.getElementById("job-chapter");
  const left = document.getElementById("job-left");
  const count = document.getElementById("job-progress");
  const announce = announcer(document.getElementById("job-status"));
  follow(card.dataset.events, (progress) => {
    const shown = cardShown(progress);
    chapter.textContent = shown.head;
    left.textContent = shown.left;
    count.textContent = shown.sentences;
    if (shown.part == null) bar.removeAttribute("value");
    else bar.value = Math.round(100 * Math.min(1, shown.part));
    let segs = document.getElementById("job-segments");
    if (!segs && shown.chapters) {
      segs = document.createElement("span");
      segs.id = "job-segments";
      segs.className = "segs";
      segs.setAttribute("aria-hidden", "true");
      bar.after(segs);
    }
    drawSegments(segs, shown.chapters, shown.now);
    bar.setAttribute("aria-valuetext", shown.said);
    announce(progress, shown.said);
  }, () => {
    if (!leaving) reloadAt("result");
  });
}

// ---- the voice setup page --------------------------------------------------------------

function voicePage() {
  voiceSamples();
  const form = document.getElementById("voice-download");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const consent = document.getElementById("voice-consent");
    if (!consent.checked) {
      consent.focus();
      return;
    }
    try {
      const job = await send("/api/v1/voices/download", json("POST", { consent: true, plan: form.dataset.plan }));
      location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(explain(error), true);
    }
  });
}

// The voice cards' samples (#419): the document page's preview job with the sample sentence
// of the voice's language; one plays at a time, and the player keeps no position (D-664).
function voiceSamples() {
  const audio = document.getElementById("voice-sample");
  const buttons = [...document.querySelectorAll("button.voice-play")];
  if (!audio || !buttons.length) return;
  let playing = null; // the button whose sample is loading or playing
  let asked = 0; // a later click wins over a sample still being made
  const show = (button, on) => {
    button.setAttribute("aria-label", on ? button.dataset.stop : button.dataset.play);
    button.querySelector("span").textContent = on ? button.dataset.stopShort : button.dataset.playShort;
    button.querySelector("use").setAttribute("href", on ? "#i-pause" : "#i-play");
  };
  const stop = () => {
    asked += 1;
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    if (playing) show(playing, false);
    playing = null;
  };
  audio.addEventListener("ended", stop);
  for (const button of buttons) {
    button.addEventListener("click", async () => {
      const again = playing === button;
      stop();
      if (again) return;
      playing = button;
      show(button, true);
      const mine = asked;
      say(tr("js.listening"));
      try {
        const body = { voice: button.dataset.voice, speed: 1, text: button.dataset.text };
        const job = await send("/api/v1/voices/preview", json("POST", body));
        follow(`/api/v1/jobs/${job.id}/events`, () => {}, (ended) => {
          if (mine !== asked) return; // stopped, or another sample asked for since
          if (ended.state !== "done" || !ended.files.length) {
            stop();
            say(ended.error ? failureOf(ended.error.error, ended.error.message) : tr(`job.state_${ended.state}`), true);
            return;
          }
          audio.src = `/api/v1/jobs/${ended.id}/files/${encodeURIComponent(ended.files[0].name)}`;
          say("");
          audio.play().catch(() => stop());
        });
      } catch (error) {
        if (mine === asked) stop();
        say(explain(error), true);
      }
    });
    button.disabled = false;
  }
}

// ---- the rail: the running job on the shelf (#387) ---------------------------------------

function shelf() {
  const item = document.getElementById("shelf-job");
  if (!item) return;
  const state = document.getElementById("shelf-job-state");
  const bar = document.getElementById("shelf-job-bar");
  function shown(progress) {
    const words = STRINGS[`phase.${progress.phase}`] ?? state.textContent;
    const part = fraction(progress);
    if (part == null) {
      bar.removeAttribute("value");
      state.textContent = words;
    } else {
      const n = Math.floor(100 * Math.min(1, part));
      bar.value = n;
      state.textContent = tr("shelf.made", { phase: words, n });
    }
  }
  function ended(job) {
    state.textContent = tr(`job.state_${job.state}`);
    if (job.state === "done") bar.value = 100;
  }
  // a page that follows this job already (its job page, its document while analysing)
  // feeds the shelf from its own stream
  if (STREAMS.has(item.dataset.events)) {
    follow(item.dataset.events, shown, ended, true);
    return;
  }
  // every other page holds no stream for the shelf: it asks now and then, never while the
  // tab is hidden, and stops once the job has ended
  let timer = null;
  let asking = false;
  let over = false;
  async function ask() {
    timer = null;
    if (over || asking || document.hidden) return;
    asking = true;
    try {
      const job = await send(item.dataset.job);
      if (job.state !== "running") {
        over = true;
        ended(job);
      } else if (job.progress) {
        shown(job.progress);
      }
    } catch (error) {
      over = true; // the server is gone or forgot the job: the shelf keeps its last words
    } finally {
      asking = false;
    }
    if (!over && !document.hidden && timer === null) timer = setTimeout(ask, SHELF_EVERY);
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearTimeout(timer);
      timer = null;
    } else if (timer === null) {
      ask();
    }
  });
  timer = setTimeout(ask, SHELF_EVERY);
}

// ---- the Settings page (#388) -----------------------------------------------------------

function settingsPage() {
  // the announcement and keyboard switches save themselves when the script runs; their
  // buttons are for pages without the script
  for (const name of ["announce", "keys"]) {
    const box = document.getElementById(`settings-${name}`);
    if (!box) continue;
    box.addEventListener("change", () => box.form.requestSubmit());
    document.getElementById(`${name}-save-line`).hidden = true;
  }
  const form = document.getElementById("defaults");
  if (!form) return;
  const folder = document.getElementById("settings-folder");
  const speed = document.getElementById("settings-speed");
  const speedValue = document.getElementById("settings-speed-value");
  const save = document.getElementById("settings-save");
  function showSpeed() {
    const text = tr("voice.speed_value", { value: decimal(speed.value) });
    speedValue.textContent = text;
    speed.setAttribute("aria-valuetext", text);
  }
  speed.addEventListener("input", showSpeed);
  showSpeed();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!folder.value.trim()) {
      folder.focus();
      return;
    }
    say(tr("settings.saving"));
    try {
      // the settings as saved now, with only these two changed: switches, voice and letter
      // pace someone chose elsewhere are kept
      const saved = (await send(form.dataset.api)).settings;
      saved.output_folder = folder.value.trim();
      saved.speed = Number(speed.value);
      await send(form.dataset.api, json("PUT", saved));
      say(tr("settings.saved"), true);
    } catch (error) {
      say(explain(error), true);
    }
  });
  save.disabled = false;
}

// True while the person types: the page's keys leave such a field alone (#394). A select
// counts too, since letters and arrows choose in it.
const NOT_TYPED = new Set(["button", "checkbox", "radio", "range", "submit", "reset", "color", "file", "image"]);

// The page-wide single keys, unless switched off in Settings (#394 review S3): then only
// Esc and the rail's Keyboard shortcuts item are left.
function shortcutsOn() {
  return document.documentElement.dataset.keys !== "off";
}

function typing(target) {
  if (!(target instanceof Element)) return false;
  if (target.closest("textarea, select, [contenteditable]:not([contenteditable='false'])")) return true;
  return target instanceof HTMLInputElement && !NOT_TYPED.has(target.type);
}

// The keyboard shortcuts sheet (#394): a modal dialog, opened by ? on every page (unless the
// keys are switched off) and by the rail's item; Esc or its button closes it, and the focus
// goes back where it was.
function shortcutsSheet() {
  const sheet = document.getElementById("keys");
  const open = document.getElementById("keys-open");
  const close = document.getElementById("keys-close");
  if (!sheet || !open || !close || typeof sheet.showModal !== "function") return;
  let opener = null;
  function show() {
    if (sheet.open) return;
    opener = document.activeElement;
    sheet.showModal();
  }
  open.addEventListener("click", show);
  close.addEventListener("click", () => sheet.close());
  sheet.addEventListener("close", () => {
    if (opener && opener !== document.body && opener.isConnected) opener.focus();
    opener = null;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "?" || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    if (!shortcutsOn() || typing(event.target) || document.querySelector("dialog[open]")) return;
    event.preventDefault();
    show(); // a held ? opens it once: the open sheet stops the repeats above
  });
  open.disabled = false; // drawn disabled until here (#350, #427)
  close.disabled = false;
}

function focusTarget() {
  if (!location.hash) return;
  const target = document.getElementById(location.hash.slice(1));
  if (!target || !target.hasAttribute("tabindex")) return;
  target.focus();
  // the fragment has done its work: left in the address, WebKit scrolls to it and focuses
  // it once more when the page has loaded, under a key press or click made in the meantime
  history.replaceState(null, "", location.pathname + location.search);
}

document.addEventListener("DOMContentLoaded", () => {
  const data = document.getElementById("strings");
  STRINGS = data ? JSON.parse(data.textContent) : {};
  startPage();
  librarySearch();
  removal();
  documentPage();
  makingCard();
  jobPage();
  voicePage();
  settingsPage();
  shelf();
  shortcutsSheet();
  focusTarget();
});
