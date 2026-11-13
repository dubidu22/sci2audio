// The sci2audio interface's one script (#77, D-101): talks to the JSON API of this server
// only. Its strings come from the page's data block (D-256).
"use strict";

const ANNOUNCE_EVERY = 30000; // ms between progress announcements, phase changes aside (D-253)

let STRINGS = {};

function tr(key, values) {
  const text = STRINGS[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (all, name) => (values && name in values ? values[name] : all));
}

function say(text, focus) {
  const message = document.getElementById("message");
  if (!message) return;
  message.textContent = text;
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

// Follows a job's events (D-201): `progress` gets each progress, `end` the final job.
function follow(url, progress, end) {
  const events = new EventSource(url);
  let ended = false;
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
    if (events.readyState === EventSource.CLOSED) say(tr("js.lost"), true);
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
    say(error.message, true);
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

// ---- the document page -----------------------------------------------------------------

function chosen(name) {
  return Array.from(document.querySelectorAll(`input[name=${name}]`));
}

function controls() {
  return {
    switched_off: chosen("category").filter((c) => !c.checked).map((c) => c.value).sort(),
    chapters: chosen("chapter").filter((c) => c.checked).map((c) => Number(c.value)).sort((a, b) => a - b),
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
    const differs = !same(controls(), shown);
    changed.hidden = !differs;
    let blocked = blockedFirst;
    if (!blocked && differs) blocked = "needs_update";
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
      say(error.message, true);
    }
  }
  const choices = document.getElementById("choices");
  if (choices) {
    choices.addEventListener("submit", (event) => {
      event.preventDefault();
      analyse(controls());
    });
  }
  const analyseButton = document.getElementById("analyse");
  if (analyseButton) analyseButton.addEventListener("click", () => analyse({}));
  if (box.dataset.events) follow(box.dataset.events, () => {}, () => reloadAt("step-check"));

  const speed = document.getElementById("speed");
  const speedValue = document.getElementById("speed-value");
  function showSpeed() {
    const text = tr("voice.speed_value", { value: Number(speed.value).toFixed(2).replace(/0$/, "") });
    speedValue.textContent = text;
    speed.setAttribute("aria-valuetext", text);
  }
  speed.addEventListener("input", showSpeed);
  showSpeed();
  const voice = document.getElementById("voice");

  const preview = document.getElementById("preview");
  if (preview) {
    const audio = document.getElementById("preview-audio");
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
            say(ended.error ? ended.error.message : ended.state, true);
            return;
          }
          audio.src = `/api/v1/jobs/${ended.id}/files/${encodeURIComponent(ended.files[0].name)}`;
          audio.hidden = false;
          say(tr("js.preview_ready"));
          audio.focus();
        });
      } catch (error) {
        say(error.message, true);
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
      const settings = {
        language: saved.settings.language,
        switched_off: shown.switched_off,
        voice: voice.value,
        speed: Number(speed.value),
        output_folder: folder,
      };
      // remembered for the next document (D-246); chapters stay with the document
      await send("/api/v1/settings", json("PUT", settings));
      const job = await send("/api/v1/jobs", json("POST", {
        kind: "audio", document: id, settings: { ...settings, chapters: shown.chapters },
      }));
      location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(error.message, true);
    }
  });
  refresh();
}

// ---- the job page ----------------------------------------------------------------------

function describe(progress) {
  const parts = [];
  if (progress.phase) parts.push(STRINGS[`phase.${progress.phase}`] ?? progress.phase);
  if (progress.chunks_total) parts.push(tr("js.sentences", { done: progress.chunks_done, total: progress.chunks_total }));
  if (progress.phase === "speaking") {
    if (progress.seconds_left == null) parts.push(tr("js.measuring"));
    else {
      const minutes = Math.max(1, Math.ceil(progress.seconds_left / 60));
      parts.push(minutes === 1 ? tr("js.minute_left") : tr("js.minutes_left", { n: minutes }));
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
        say(error.message, true);
      }
    });
  }
  async function restart(overwrite) {
    try {
      const job = await send("/api/v1/jobs", json("POST", { kind, document: doc, settings, overwrite }));
      location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(error.message, true);
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
        say(error.message, true);
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
      say(error.message, true);
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
  documentPage();
  jobPage();
  voicePage();
  focusTarget();
});
