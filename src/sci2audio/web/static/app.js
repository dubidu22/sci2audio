// The minimal pages' script (#76): talks to the JSON API on this server only.
"use strict";

function say(text) {
  const message = document.getElementById("message");
  if (message) message.textContent = text;
}

async function send(url, options) {
  const response = await fetch(url, Object.assign({ credentials: "same-origin" }, options));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || response.statusText);
  return data;
}

function json(method, body) {
  return { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
}

function openForms() {
  const fileForm = document.getElementById("open-file");
  if (fileForm) {
    fileForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      say("Opening…");
      try {
        const body = new FormData(fileForm);
        const doc = await send(fileForm.dataset.api, { method: "POST", body });
        window.location.assign(`/documents/${doc.id}`);
      } catch (error) {
        say(error.message);
      }
    });
  }
  const textForm = document.getElementById("open-text");
  if (textForm) {
    textForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      say("Opening…");
      try {
        const fields = new FormData(textForm);
        const doc = await send(
          textForm.dataset.api,
          json("POST", { text: fields.get("text"), name: fields.get("name") || "pasted text" }),
        );
        window.location.assign(`/documents/${doc.id}`);
      } catch (error) {
        say(error.message);
      }
    });
  }
}

async function voiceDownload() {
  const box = document.getElementById("voice-download");
  if (!box) return;
  const voices = await send("/api/v1/voices");
  const megabytes = Math.round(voices.plan.missing_bytes / 1e6);
  document.getElementById("voice-plan").textContent =
    `The voice files are about ${megabytes} MB from ${voices.plan.hosts.join(", ")}. ` +
    `Licences: ${voices.plan.licences.join(" ")}`;
  box.hidden = false;
  document.getElementById("voice-consent").addEventListener("click", async () => {
    try {
      const job = await send(
        "/api/v1/voices/download",
        json("POST", { consent: true, plan: voices.plan.digest }),
      );
      window.location.assign(`/jobs/${job.id}`);
    } catch (error) {
      say(error.message);
    }
  });
}

function startButtons() {
  for (const button of document.querySelectorAll(".start-job")) {
    button.addEventListener("click", async () => {
      const chosen = Array.from(document.querySelectorAll("input[name=chapter]"));
      const settings = {};
      if (chosen.length) settings.chapters = chosen.filter((c) => c.checked).map((c) => Number(c.value));
      try {
        const job = await send(
          "/api/v1/jobs",
          json("POST", { kind: button.dataset.kind, document: button.dataset.document, settings }),
        );
        window.location.assign(`/jobs/${job.id}`);
      } catch (error) {
        say(error.message);
      }
    });
  }
}

function describe(progress) {
  if (!progress) return "";
  const parts = [progress.phase];
  if (progress.chunks_total) parts.push(`${progress.chunks_done} of ${progress.chunks_total} sentences`);
  if (progress.seconds_left != null) parts.push(`about ${Math.ceil(progress.seconds_left / 60)} min left`);
  if (progress.bytes_total) parts.push(`${Math.round((100 * progress.bytes_done) / progress.bytes_total)} %`);
  return parts.join(", ");
}

function jobPage() {
  const box = document.getElementById("job");
  if (!box) return;
  const state = document.getElementById("job-state");
  const progress = document.getElementById("job-progress");
  const cancel = document.getElementById("job-cancel");
  if (cancel) {
    cancel.addEventListener("click", async () => {
      try {
        await send(box.dataset.cancel, { method: "POST" });
      } catch (error) {
        progress.textContent = error.message;
      }
    });
  }
  if (state.textContent !== "running") return;
  const events = new EventSource(box.dataset.events);
  events.addEventListener("snapshot", (event) => {
    progress.textContent = describe(JSON.parse(event.data).progress);
  });
  events.addEventListener("progress", (event) => {
    progress.textContent = describe(JSON.parse(event.data));
  });
  events.addEventListener("end", () => {
    events.close();
    window.location.reload();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  openForms();
  voiceDownload().catch((error) => say(error.message));
  startButtons();
  jobPage();
});
