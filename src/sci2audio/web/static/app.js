// The sci2audio interface's one script (#77, D-101): talks to the JSON API of this server
// only. Its strings come from the page's data block, in the page's language (D-256,
// D-288 to D-291).
"use strict";

const ANNOUNCE_EVERY = 30000; // ms between progress announcements, phase changes aside (D-253)
const LOST_AFTER = 5000; // ms an event stream may stay away before the page says the server is lost

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
function follow(url, progress, end) {
  const events = new EventSource(url);
  let ended = false;
  let waiting = null;
  function lost() {
    clearTimeout(waiting);
    events.close();
    say(tr("js.lost"), true);
  }
  events.addEventListener("open", () => {
    clearTimeout(waiting);
    waiting = null;
  });
  events.addEventListener("snapshot", (event) => {
    const job = JSON.parse(event.data);
    if (job.progress) progress(job.progress);
  });
  events.addEventListener("progress", (event) => progress(JSON.parse(event.data) || {}));
  events.addEventListener("end", (event) => {
    ended = true;
    events.close();
    end(JSON.parse(event.data));
  });
  events.addEventListener("error", () => {
    if (ended) return;
    if (events.readyState === EventSource.CLOSED) lost();
    else if (waiting === null) waiting = setTimeout(lost, LOST_AFTER);
  });
  return events;
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
    fileForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const body = new FormData(fileForm);
      openAndAnalyse(() => send(fileForm.dataset.api, { method: "POST", body }));
    });
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
        const intro = document.getElementById("document-intro");
        if (intro) intro.remove();
        const done = document.getElementById("removed");
        document.getElementById("removed-title").textContent = text;
        document.getElementById("removed-text").textContent = stays;
        done.hidden = false;
        document.getElementById("removed-title").focus();
        return;
      }
      // the start page: the document leaves the list; the message says what happened
      const item = button.closest("li");
      const list = item && item.parentElement;
      if (item) item.remove();
      if (list && !list.querySelector("li")) {
        list.remove();
        const none = document.getElementById("no-documents");
        if (none) none.hidden = false;
      }
      if (stays) text = `${text} ${stays}`;
      say(text, true);
    });
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
    chapters: chosen("chapter").filter((c) => c.checked).map((c) => Number(c.value)).sort((a, b) => a - b),
    language: language ? language.value : shown.language,
  };
}

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
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
  if (all) all.addEventListener("click", () => { chosen("chapter").forEach((c) => { c.checked = true; }); refresh(); });
  if (none) none.addEventListener("click", () => { chosen("chapter").forEach((c) => { c.checked = false; }); refresh(); });

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
  }
  const analyseButton = document.getElementById("analyse");
  if (analyseButton) analyseButton.addEventListener("click", () => analyse({}));
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
  }

  make.addEventListener("click", async () => {
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
  const settings = JSON.parse(box.dataset.settings || "null") || {};

  const cancel = document.getElementById("job-cancel");
  if (cancel) {
    cancel.addEventListener("click", async () => {
      try {
        await send(box.dataset.cancel, { method: "POST" });
      } catch (error) {
        say(explain(error), true);
      }
    });
  }
  async function restart(overwrite) {
    try {
      const job = await send("/api/v1/jobs", json("POST", { kind, document: doc, settings, overwrite }));
      location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(explain(error), true);
    }
  }
  const replace = document.getElementById("job-replace");
  if (replace) replace.addEventListener("click", () => restart(true));
  const again = document.getElementById("job-again");
  if (again) again.addEventListener("click", () => restart(false));

  const free = document.getElementById("cache-free");
  if (free) {
    free.addEventListener("click", async () => {
      try {
        await send(`/api/v1/documents/${doc}/chunks`, { method: "DELETE" });
        const text = document.getElementById("cache-text");
        text.textContent = tr("js.freed");
        free.remove();
        say(tr("js.freed"), true);
      } catch (error) {
        say(explain(error), true);
      }
    });
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

// ---- the voice setup page --------------------------------------------------------------

function voicePage() {
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

function focusTarget() {
  if (!location.hash) return;
  const target = document.getElementById(location.hash.slice(1));
  if (target && target.hasAttribute("tabindex")) target.focus();
}

document.addEventListener("DOMContentLoaded", () => {
  const data = document.getElementById("strings");
  STRINGS = data ? JSON.parse(data.textContent) : {};
  startPage();
  removal();
  documentPage();
  jobPage();
  voicePage();
  focusTarget();
});
