/* sci2audio prototype: views, player simulation, captures, keyboard. Everything is local and synthetic. */
(() => {
  const D = window.S2A_DATA, I18N = window.S2A_I18N;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const icon = (n, cls = "") => `<svg class="i ${cls}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
  const flag = (k) => `<span class="flag ${k}" aria-hidden="true">${icon(k)}</span>`;
  const mod = /Mac|iPhone/.test(navigator.platform) ? "⌘" : "Ctrl";

  const st = {
    lang: localStore("lang") || "en",
    theme: localStore("theme") || "system",
    scenario: "normal",
    papers: structuredClone(D.papers),
    captures: structuredClone(D.captures),
    current: "sleep", ch: 2, si: 0, playing: false, speed: 1.25,
    panel: "captures", panelOpen: true, focus: false, composer: null,
    voiceEN: true, voiceDE: false, download: null, consent: false,
    catsOff: new Set(), dirty: false, analysing: null,
    capFilter: "all", capPaper: "all", review: null, sent: {}, ankiOffline: false,
    announce: false, sounds: true, defaultVoice: "Heart",
  };
  function localStore(k, v) {
    try { if (v === undefined) return localStorage.getItem("s2a-" + k); localStorage.setItem("s2a-" + k, v); } catch { return null; }
  }

  /* ---------- i18n ---------- */
  const t = (k, vars = {}) => {
    let s = (I18N[st.lang] && I18N[st.lang][k]) ?? I18N.en[k] ?? k;
    for (const [a, b] of Object.entries(vars)) s = s.replaceAll(`{${a}}`, b);
    return s;
  };
  const nf = (n) => n.toLocaleString(st.lang === "de" ? "de-DE" : "en-GB");
  const paper = (id = st.current) => st.papers.find((p) => p.id === id);
  const fmt = (sec) => {
    sec = Math.max(0, Math.round(sec)); const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) + `:${String(s).padStart(2, "0")}`;
  };
  const hasAudio = (p) => p && (p.state === "ready" || p.state === "cli");

  /* ---------- theme ---------- */
  function applyTheme() {
    if (st.theme === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", st.theme);
    document.documentElement.lang = st.lang;
  }

  /* ---------- listening content ---------- */
  function contentFor(p) {
    if (p.content) return p.content;
    if (p.lang === "de") return [
      { h: "4.1 Erholung nach dem Aufenthalt" },
      { p: ["Nach zwanzig Minuten in einem Park lösten die Teilnehmenden die Aufmerksamkeitsaufgabe schneller als nach einem Gang durch die Innenstadt.",
            "Der Unterschied war in kleinen Parks ähnlich groß wie in großen.",
            "Das spricht dafür, dass schon kurze Wege ins Grüne die Konzentration im Studienalltag stützen können."] },
      { p: ["Synthetisches Beispiel: Dieser Text wurde für den Prototyp geschrieben."] },
    ];
    return [
      { h: "Synthetic example text" },
      { p: ["This chapter stands in for the real text of the document in the prototype.",
            "Every sentence is highlighted while the voice reads it, and you can capture any of them.",
            "Nothing here is taken from a published work."] },
    ];
  }
  function sentences(p) {
    const out = []; let pi = 0;
    for (const b of contentFor(p)) if (b.p) { b.p.forEach((html) => out.push({ html, para: pi })); pi++; }
    return out.map((s, i) => {
      const plain = s.html.replace(/<span class="(cut|fnmark)"[^>]*>.*?<\/span>/g, "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").replace(/\s+([.,;:])/g, "$1").trim();
      const words = plain.split(" ").length;
      return { ...s, i, plain, dur: Math.max(2.2, words / 2.7) };
    });
  }
  const chStart = (p, ch) => p.chapters.slice(0, ch).reduce((a, c) => a + c.sec, 0);
  function position() {
    const p = paper(); const ss = sentences(p); const c = p.chapters[st.ch] || { sec: 600 };
    const frac = ss.length ? (st.si + (st.playing ? elapsedFrac() : st.pausedFrac || 0)) / ss.length : 0;
    return chStart(p, st.ch) + frac * c.sec;
  }

  /* ---------- router ---------- */
  function route() {
    const h = location.hash.replace(/^#\/?/, "") || "library";
    const [view, id, sub] = h.split("/");
    return { view, id, sub };
  }
  window.addEventListener("hashchange", () => { closeComposer(false); render(); $("#main").focus({ preventScroll: true }); });

  /* ---------- shell ---------- */
  function renderShell(r) {
    const n = st.captures.filter((c) => !c.removed).length;
    const visible = st.scenario === "empty" || st.scenario === "firstrun" ? [] : st.papers;
    const cur = (v) => (r.view === v ? ' aria-current="page"' : "");
    $("#nav").innerHTML = `
      <a href="#/library"${cur("library")}>${icon("library")}${t("nav.library")}<span class="count num">${visible.length}</span></a>
      <a href="#/captures"${cur("captures")}>${icon("captures")}${t("nav.captures")}<span class="count num">${visible.length ? n : 0}</span></a>
      <a href="#/library/open">${icon("open")}${t("nav.open")}</a>
      <a href="#/voices"${cur("voices")}>${icon("voices")}${t("nav.voices")}${!st.voiceEN ? `<span class="count" title="${t("firstrun.title")}">${icon("alert", "s")}<span class="sr">${t("firstrun.title")}</span></span>` : ""}</a>`;
    $("#shelf-h").textContent = visible.length ? t("nav.reading") : "";
    $("#shelf").innerHTML = visible.slice(0, 4).map((p) => {
      const href = hasAudio(p) ? `#/paper/${p.id}/listen` : `#/paper/${p.id}/prepare`;
      const on = r.view === "paper" && r.id === p.id ? ' aria-current="page"' : "";
      let meta = "", meter = "";
      if (p.state === "making") { meta = t("lib.making", { p: Math.round(p.progress * 100) }); meter = `<div class="meter making"><i style="width:${p.progress * 100}%"></i></div>`; }
      else if (hasAudio(p)) { meta = p.listened ? t("lib.listened", { p: Math.round(p.listened * 100) }) : t("lib.notstarted"); meter = `<div class="meter"><i style="width:${(p.listened || 0) * 100}%"></i></div>`; }
      else meta = t("state." + p.state);
      return `<a href="${href}"${on}><span class="t">${esc(p.title)}</span><span class="m num">${meta}</span>${meter}${flagstrip(p.id)}</a>`;
    }).join("");
    $("#rail-foot").innerHTML = `
      <a href="#/settings"${cur("settings")}>${icon("settings")}${t("nav.settings")}</a>
      <a href="#/privacy"${cur("privacy")}>${icon("privacy")}${t("nav.privacy")}</a>
      <button type="button" data-act="keys">${icon("keyboard")}${t("nav.shortcuts")}<kbd style="margin-left:auto">?</kbd></button>
      <details class="proto"><summary class="btn quiet" style="color:var(--on-cobalt);justify-content:flex-start;width:100%;font-weight:400">${icon("proto")}${t("nav.proto")}</summary>
        <div class="menu" role="menu">
          <b>${t("nav.proto")}</b>
          <button type="button" data-scn="normal">${t("proto.normal")}</button>
          <button type="button" data-scn="firstrun">${t("proto.firstrun")}</button>
          <button type="button" data-scn="empty">${t("proto.empty")}</button>
          <button type="button" data-scn="offline">${t("proto.offline")}</button>
          <button type="button" data-act="lang">${t("proto.lang")}</button>
          <button type="button" data-act="theme">${t("proto.theme")}</button>
        </div></details>`;
  }
  function flagstrip(pid) {
    const cs = st.captures.filter((c) => c.paper === pid && !c.removed);
    if (!cs.length) return "";
    return `<span class="flagstrip" aria-label="${cs.length} ${t("nav.captures")}">${cs.slice(0, 12).map((c) => `<i class="${c.kind}"></i>`).join("")}</span>`;
  }

  /* ---------- views ---------- */
  function render() {
    applyTheme();
    const r = route();
    renderShell(r);
    st.focus = r.view === "paper" && r.sub === "focus";
    $("#app").classList.toggle("focus", st.focus);
    const main = $("#main");
    if (r.view === "paper" && paper(r.id)) {
      if (st.current !== r.id && (r.sub === "listen" || r.sub === "focus")) loadPaper(r.id);
      main.innerHTML = r.sub === "listen" ? viewListen(paper(r.id)) : r.sub === "focus" ? viewFocus() : viewPrepare(paper(r.id));
      if (r.sub === "listen") afterListen();
      if (r.sub === "focus") updateFocus();
    } else if (r.view === "captures") main.innerHTML = viewCaptures();
    else if (r.view === "voices") main.innerHTML = viewVoices();
    else if (r.view === "privacy") main.innerHTML = viewPrivacy();
    else if (r.view === "settings") main.innerHTML = viewSettings();
    else { main.innerHTML = viewLibrary(); if (r.id === "open") setTimeout(() => $("#choose")?.focus(), 0); }
    renderDock();
    document.title = (paper(r.id)?.title ? paper(r.id).title + " · " : "") + "sci2audio";
  }

  function viewLibrary() {
    const papers = st.scenario === "empty" || st.scenario === "firstrun" ? [] : st.papers;
    const q = (st.q || "").toLowerCase();
    const list = papers.filter((p) => !q || (p.title + p.authors).toLowerCase().includes(q));
    const head = `<header class="view-head"><div><h1>${t("lib.title")}</h1><p class="sub num">${t("lib.sub", { n: papers.length })}</p></div></header>`;
    const firstrun = !st.voiceEN ? `<div class="notice warn">${icon("alert", "l")}<div><b>${t("firstrun.title")}</b>${t("firstrun.body")}</div><a class="btn primary" href="#/voices">${t("firstrun.cta")}</a></div>` : "";
    const opener = `<section class="opener" aria-labelledby="open-h">
      <div class="drop" id="drop"><div class="slot">${icon("open", "l")}</div><div><h2 id="open-h">${t("lib.drop.title")}</h2><p>${t("lib.drop.hint")}</p></div>
        <label class="btn primary" id="choose" tabindex="0">${t("lib.drop.choose")}<input type="file" class="sr" accept=".pdf,.epub,.md,.txt" data-act="file"></label></div>
      <details class="paste"><summary>${icon("text")}${t("lib.paste")}${icon("chev", "s")}</summary>
        <div class="field"><label for="pname">${t("lib.paste.name")}</label><input class="input" id="pname" value="${st.lang === "de" ? "eingefügter Text" : "pasted text"}"></div>
        <textarea class="input" aria-label="${t("lib.paste")}"></textarea><button class="btn" type="button" data-act="paste">${t("lib.paste.open")}</button></details>
    </section>`;
    if (!papers.length) {
      return `<div class="view">${head}${firstrun}${opener}
        <section class="empty"><div><h2>${t("empty.title")}</h2><p>${t("empty.body")}</p></div>
        ${st.lang === "de" ? `<div class="specimen"><figure><figcaption>${t("empty.printed")}</figcaption><p lang="de">Die Teilnehmenden schliefen im Mittel 7,5 h <span class="cut">(Schmidt et al., 2020)</span>, und die Reaktionszeit sank um 12 ms pro Stunde Schlaf <span class="cut">(t(34) = 2,81, p &lt; ,01)</span>. Nickerchen, z. B. nach dem Mittagessen, wurden nicht gezählt.</p></figure><figure><figcaption>${t("empty.read")}</figcaption><p lang="de">Die Teilnehmenden schliefen im Mittel 7,5 Stunden, und die Reaktionszeit sank um 12 Millisekunden pro Stunde Schlaf. Nickerchen, zum Beispiel nach dem Mittagessen, wurden nicht gezählt.</p></figure></div>` : `<div class="specimen"><figure><figcaption>${t("empty.printed")}</figcaption><p>Participants slept 7.5 h on average <span class="cut">(Smith et al., 2020)</span>, and reaction times fell by 12 ms per hour of sleep <span class="cut">(t(34) = 2.81, p &lt; .01)</span>. Naps, e.g. after lunch, were not counted.</p></figure>
        <figure><figcaption>${t("empty.read")}</figcaption><p>Participants slept 7.5 hours on average, and reaction times fell by 12 milliseconds per hour of sleep. Naps, for example after lunch, were not counted.</p></figure></div>`}</section></div>`;
    }
    const rows = list.map((p) => {
      const href = hasAudio(p) ? `#/paper/${p.id}/listen` : `#/paper/${p.id}/prepare`;
      const cls = { ready: "ready", cli: "ready", making: "making", failed: "failed" }[p.state] || "idle";
      const ic = { ready: "check", cli: "check", making: "voices", failed: "alert", analysed: "text", new: "open" }[p.state];
      let prog = "";
      if (p.state === "making") prog = `<div class="progress"><div class="meter making" style="background:var(--rule)"><i style="width:${p.progress * 100}%;background:var(--ink)"></i></div><small class="num">${t("lib.making", { p: Math.round(p.progress * 100) })}</small></div>`;
      else if (p.state === "failed") prog = `<div class="progress"><small class="num">${t("lib.stopped", { k: p.failure.kept })}</small></div>`;
      else if (hasAudio(p)) prog = `<div class="progress"><div class="meter"><i style="width:${(p.listened || 0) * 100}%"></i></div><small class="num">${p.listened ? t("lib.listened", { p: Math.round(p.listened * 100) }) : t("lib.notstarted")}</small></div>`;
      else prog = `<div class="progress"><small>—</small></div>`;
      const meta = [p.authors, p.pages ? t("paper.pages", { n: nf(p.pages) }) : t("paper.words", { n: nf(p.words) }), p.audio ? (p.state === "ready" || p.state === "cli" ? p.audio : "") : ""].filter(Boolean).join(" · ");
      return `<a class="paper-row" href="${href}"><span class="thumb ${p.kind}" aria-hidden="true"><i></i><i></i><i></i><i style="width:70%"></i><i></i><i style="width:85%"></i></span>
        <span><span class="title">${esc(p.title)}</span><span class="meta num" style="display:block">${esc(meta)}</span></span>
        <span><span class="state ${cls}">${icon(ic, "s")}${t("state." + p.state)}</span></span>${prog}
        <span>${flagstrip(p.id) || `<small style="color:var(--pencil)">—</small>`}</span><span class="when">${esc(p.lastOpened)}</span></a>`;
    }).join("");
    return `<div class="view">${head}${firstrun}${opener}
      <div class="lib-tools"><div class="search">${icon("search", "s")}<input class="input" type="search" placeholder="${t("lib.search")}" aria-label="${t("lib.search")}" value="${esc(st.q || "")}" data-act="search"></div></div>
      <div class="papers" role="list"><div class="headrow" aria-hidden="true"><span></span><span>${t("lib.col.doc")}</span><span>${t("lib.col.state")}</span><span>${t("lib.col.progress")}</span><span>${t("lib.col.caps")}</span><span class="when" style="text-align:right">${t("lib.col.when")}</span></div>
      ${rows || `<p style="padding:24px">${t("lib.none", { q: esc(st.q) })}</p>`}</div></div>`;
  }

  function paperHead(p, sub) {
    const audio = hasAudio(p);
    const langName = t("lang." + p.lang);
    return `<header class="paper-head"><h1>${esc(p.title)}</h1>
      <p class="meta num"><span>${esc(p.authors)}</span>${p.pages ? `<span>${t("paper.pages", { n: nf(p.pages) })}</span>` : ""}<span>${t("paper.words", { n: nf(p.words) })}</span><span>${t("paper.lang", { lang: langName, source: p.langSource })}</span>${audio ? `<span>${t("paper.audio", { d: p.audio })}</span>` : ""}</p>
      <nav class="tabs" aria-label="${esc(p.title)}">
        <a href="#/paper/${p.id}/prepare"${sub === "prepare" ? ' aria-current="page"' : ""}>${icon("text", "s")}${t("paper.prepare")}</a>
        ${audio ? `<a href="#/paper/${p.id}/listen"${sub === "listen" ? ' aria-current="page"' : ""}>${icon("speaker", "s")}${t("paper.listen")}</a>` : `<a aria-disabled="true" title="${t("paper.noaudio")}">${icon("speaker", "s")}${t("paper.listen")} · ${t("paper.noaudio")}</a>`}
      </nav></header>`;
  }

  function viewPrepare(p) {
    const head = paperHead(p, "prepare");
    if (p.state === "new" || st.analysing === p.id) {
      const busy = st.analysing === p.id;
      return `${head}<div class="prepare"><div><section class="step"><div class="body"><p class="summary-line">${busy ? (st.lang === "de" ? "Das Dokument wird analysiert …" : "Analysing the document…") : (st.lang === "de" ? "Dieses Dokument ist noch nicht analysiert. Die Analyse findet Kapitel, Fußnoten, Zitate und alles, was die Stimme stolpern ließe. Sie braucht keine Stimme und kein Netz." : "This document has not been analysed yet. The analysis finds chapters, footnotes, citations and everything a voice would stumble on. It needs no voice and no network.")}</p>
        ${busy ? `<div class="job"><div class="bar"><i style="width:${st.analyseP || 10}%"></i></div></div>` : `<button class="btn primary" data-act="analyse" data-id="${p.id}">${st.lang === "de" ? "Dokument analysieren" : "Analyse the document"}</button>`}</div></section></div></div>`;
    }
    const chosen = p.chapters.filter((c) => !c.off && !c.unchosen).length;
    const f = p.words / 9180, cats = D.categories.map((c) => ({ ...c, n: Math.max(1, Math.round(c.n * f * (0.7 + ((p.id.length * 7 + c.id.length * 3) % 7) / 10))), heard: Math.round(c.heard * f * (0.7 + ((p.id.length * 7 + c.id.length * 3) % 7) / 10)) }));
    const total = cats.reduce((a, c) => a + c.n, 0), heard = cats.filter((c) => !st.catsOff.has(c.id)).reduce((a, c) => a + c.heard, 0);
    const maxN = Math.max(...cats.map((c) => c.n));
    const chapters = p.chapters.map((c, i) => {
      const off = c.off && !c.chosen || c.unchosen;
      return `<li class="chapter${off ? " off" : ""}" data-i="${i}"><input type="checkbox" ${off ? "" : "checked"} aria-label="${esc(c.t)}" data-act="chap" data-i="${i}">
        <span><span class="ct">${esc(c.t)}</span>${c.off ? `<span class="why">${t("prep.off." + c.off)}</span>` : ""}</span>
        <span class="cm num">${t("prep.page", { n: c.page })} · ${t("prep.sent", { n: nf(c.sentences) })}</span>
        <span class="moves"><button class="icon-btn" data-act="up" data-i="${i}" aria-label="${t("prep.up")}: ${esc(c.t)}" ${i === 0 ? "disabled" : ""}>${icon("up", "s")}</button><button class="icon-btn" data-act="down" data-i="${i}" aria-label="${t("prep.down")}: ${esc(c.t)}" ${i === p.chapters.length - 1 ? "disabled" : ""}>${icon("down", "s")}</button></span></li>`;
    }).join("");
    const catRows = cats.map((c) => {
      const off = st.catsOff.has(c.id);
      const w = Math.max(4, Math.round((c.n / maxN) * 72));
      return `<div class="cat${off ? " off" : ""}"><input type="checkbox" role="switch" class="switch" ${off ? "" : "checked"} aria-label="${t("cat." + c.id)}" data-act="cat" data-id="${c.id}"><details><summary class="row">
        <span class="cl"><b>${t("cat." + c.id)}</b><span>${off ? t("prep.switchedoff") : t("cat." + c.id + ".d")}</span></span>
        <span class="cn num"><span class="ramp" style="width:${w}px" aria-hidden="true"></span>${nf(c.n)}</span>${icon("chev", "s exp")}</summary>
        <table class="changes"><thead><tr><th>${t("prep.printed")}</th><th>${t("prep.read")}</th><th>${t("prep.why")}</th><th class="where">${t("prep.page", { n: "" }).trim()}</th></tr></thead><tbody>
        ${c.examples.map(([a, b, why], k) => `<tr class="${off ? "off" : ""}"><td class="printed">${esc(a)}</td><td class="read">${b === "not read" ? `<span class="gone">${t("prep.notread")}</span>` : esc(b)}</td><td>${esc(why)}</td><td class="where num">${7 + k}</td></tr>`).join("")}
        </tbody></table><p class="more num">${t("prep.more", { k: c.examples.length, n: nf(c.n) })}</p></details></div>`;
    }).join("");
    const voices = p.lang === "de" ? ["Thorsten"] : ["Heart", "Bella", "Nicole", "Michael", "Emma", "George", "Fable"];
    const jobTop = p.state === "making" || p.state === "failed" ? `<section class="step" aria-labelledby="sj"><header><h2 id="sj">${t("job.title")}</h2></header><div class="body" id="jobbody">${makeBlock(p)}</div></section>` : "";
    return `${head}<div class="prepare"><div>${jobTop}
      <section class="step" aria-labelledby="s1"><header><span class="n">1</span><h2 id="s1">${t("prep.s1")}</h2></header><div class="body">
        <p class="summary-line num">${t("prep.summary", { c: p.chapters.length, k: chosen, n: nf(total), h: nf(heard) })}</p>
        <div class="grid2" style="grid-template-columns:1fr;gap:22px">
          <div class="field"><span class="label">${t("prep.chapters")}</span><span class="hint">${t("prep.chapters.hint")}</span>
            <ol class="chapters">${chapters}</ol>
            <div class="chap-tools"><button class="btn sm" data-act="all">${t("prep.choose.all")}</button><button class="btn sm" data-act="none">${t("prep.choose.none")}</button></div></div>
          <div class="field"><span class="label">${t("prep.changes")}</span><span class="hint">${t("prep.changes.hint")}</span><div class="cats">${catRows}</div></div>
          <div class="field" style="max-width:460px"><label for="lang">${t("prep.language")}</label><select class="input" id="lang"><option>${t("prep.lang.auto", { lang: t("lang." + p.lang), source: p.langSource })}</option><option>${t("lang.en")}</option><option>${t("lang.de")}</option></select><span class="hint">${t("prep.language.hint")}</span></div>
        </div>
        ${st.dirty ? `<div class="update-bar" role="status">${icon("info")}<span>${t("prep.changed")}</span><button class="btn primary" style="margin-left:auto" data-act="update">${t("prep.update")}</button></div>` : ""}
      </div></section>
      <section class="step" aria-labelledby="s2"><header><span class="n">2</span><h2 id="s2">${t("prep.s2")}</h2></header><div class="body grid2">
        <div class="field"><label for="voice">${t("prep.voice")}</label><div class="voice-pick"><select class="input" id="voice">${voices.map((v) => `<option ${v === (p.voice || st.defaultVoice) ? "selected" : ""}>${v}</option>`).join("")}</select><button class="btn" type="button" data-act="sample">${icon("speaker", "s")}${t("prep.preview")}</button></div></div>
        <div class="field"><label for="vspeed">${t("prep.speed")}</label><select class="input" id="vspeed"><option>0.9×</option><option selected>1.0×</option><option>1.1×</option><option>1.2×</option></select></div>
        <div class="field"><span class="label" id="pace-l">${t("prep.pace")}</span><div class="seg" role="group" aria-labelledby="pace-l"><button aria-pressed="true">${t("prep.pace.normal")}</button><button aria-pressed="false">${t("prep.pace.slower")}</button><button aria-pressed="false">${t("prep.pace.slowest")}</button></div><span class="hint">${t("prep.pace.hint")}</span></div>
      </div></section>
      <section class="step" aria-labelledby="s3"><header><span class="n">3</span><h2 id="s3">${t("prep.s3")}</h2>${p.audio ? `<span class="aside num">${p.audio}</span>` : ""}</header><div class="body">${jobTop ? `<p style="color:var(--pencil)">${p.state === "making" ? t("job.leave") : t("job.kept", { k: p.failure.kept })}</p>` : makeBlock(p)}</div></section>
    </div>
    <aside class="side"><div class="card"><h3>${st.lang === "de" ? "Dieses Dokument" : "This document"}</h3><dl class="num">
      <dt>${st.lang === "de" ? "Datei" : "File"}</dt><dd>${p.id}.${p.kind === "txt" ? "txt" : p.kind}</dd>
      <dt>${st.lang === "de" ? "Seiten" : "Pages"}</dt><dd>${nf(p.pages)}</dd><dt>${st.lang === "de" ? "Wörter" : "Words"}</dt><dd>${nf(p.words)}</dd>
      <dt>${t("prep.changes")}</dt><dd>${nf(total)}</dd><dt>${st.lang === "de" ? "Bericht" : "Report"}</dt><dd><a href="#" data-act="noop">${st.lang === "de" ? "lesen" : "read"}</a> · <a href="#" data-act="noop">JSON</a></dd></dl></div>
      <div class="card"><h3>${st.lang === "de" ? "Was bleibt wo" : "What stays where"}</h3><p style="font-size:14px;color:var(--ink-2)">${st.lang === "de" ? "Die Datei, ihre Analyse und der Sprach-Zwischenspeicher bleiben auf diesem Computer. Dein Original wird nie verändert." : "The file, its analysis and the speech cache stay on this computer. Your original file is never changed."}</p></div></aside></div>`;
  }

  function makeBlock(p) {
    const folder = `~/Audiobooks/${p.id}`;
    if (p.state === "making") {
      const j = p.job; const pct = Math.round(p.progress * 100);
      return `<div class="job" role="group" aria-label="${t("job.title")}">
        <div class="line"><b>${p.paused ? t("job.paused") : t("job.reading", { c: j.chapter, t: j.chapters })}</b><span class="num pencil">${pct} % · ${j.left}</span></div>
        <div class="bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>
        <div class="chapters-done" aria-hidden="true">${Array.from({ length: j.chapters }, (_, i) => `<i class="${i < j.chapter - 1 ? "done" : i === j.chapter - 1 ? "now" : ""}"></i>`).join("")}</div>
        <div class="line"><span class="num pencil">${t("job.sentences", { d: nf(Math.round(p.progress * j.total)), n: nf(j.total) })}</span></div>
        <p style="font-size:14px;color:var(--ink-2)">${t("job.leave")}</p>
        <div style="display:flex;gap:8px"><button class="btn" data-act="pausejob" data-id="${p.id}">${icon(p.paused ? "play" : "pausejob", "s")}${p.paused ? t("job.resume") : t("job.pause")}</button><button class="btn danger" data-act="canceljob" data-id="${p.id}">${t("job.cancel")}</button></div></div>`;
    }
    if (p.state === "failed") {
      return `<div class="inline-note bad">${icon("alert", "l")}<div><b>${t("job.failed", { c: p.failure.chapter })}</b>${esc(p.failure.reason)} ${t("job.kept", { k: p.failure.kept })}</div></div>
        <div class="job"><div class="chapters-done">${p.chapters.map((_, i) => `<i class="${i < p.failure.kept ? "done" : ""}"></i>`).join("")}</div></div>
        <div style="display:flex;gap:8px;margin-top:14px"><button class="btn primary" data-act="make" data-id="${p.id}">${t("job.retry")}</button><button class="btn">${t("job.cache", { s: "312 MB" })}</button></div>`;
    }
    if (hasAudio(p)) {
      return `<p class="summary-line"><b>${t("job.done")}.</b> ${t("job.in", { folder: `<span class="path">${folder}</span>` })}</p>
        <ul class="files num"><li>${icon("speaker", "s")}${p.id}.m4b<span class="sz">${p.audio} · 64 MB</span></li><li>${icon("folder", "s")}${st.lang === "de" ? `${p.chapters.length} MP3-Dateien, eine pro Kapitel` : `${p.chapters.length} MP3 files, one per chapter`}<span class="sz">71 MB</span></li><li>${icon("text", "s")}${p.id}.readalong.json<span class="sz">1.2 MB</span></li></ul>
        <div style="display:flex;gap:8px;margin-top:14px"><a class="btn primary" href="#/paper/${p.id}/listen">${icon("speaker", "s")}${t("job.listen")}</a><button class="btn" data-act="make" data-id="${p.id}" ${st.dirty ? "" : ""}>${t("prep.remake")}</button></div>`;
    }
    const ready = st.voiceEN || p.lang === "de" && st.voiceDE;
    return `<div class="grid2"><div class="field"><label for="folder">${t("prep.folder")}</label><input class="input" id="folder" value="${folder}"><span class="hint">${t("prep.folder.hint")}</span></div>
      <div class="field" style="align-content:end"><label class="check"><input type="checkbox">${t("prep.subs")}</label></div></div>
      <p class="hint num" style="margin:14px 0;color:var(--pencil)">${t("prep.estimate", { d: p.audio || "—", m: st.lang === "de" ? "35 Minuten" : "35 minutes" })}</p>
      ${ready ? `<button class="btn primary" data-act="make" data-id="${p.id}" ${st.dirty ? 'aria-disabled="true" title="' + t("prep.changed") + '"' : ""}>${t("prep.make")}</button>` : `<div class="inline-note warn">${icon("alert")}<div><b>${t("firstrun.title")}</b></div><a class="btn" href="#/voices">${t("firstrun.cta")}</a></div>`}`;
  }

  /* ---------- listen ---------- */
  function viewListen(p) {
    const ss = sentences(p); let si = 0;
    const blocks = contentFor(p).map((b) => {
      if (b.h) return `<h3 class="sec">${esc(b.h)}</h3>`;
      if (b.pb) return `<div class="pagebreak num" role="separator">${esc(b.pb)}</div>`;
      if (b.fn) return `<aside class="footnote" aria-label="${t("listen.fn", { n: b.fn })}"><b>${t("listen.fn", { n: b.fn })}</b>${esc(b.text)}</aside>`;
      if (b.skip) return `<div class="skip">${icon("skip")}<span><b>${t("listen.skip")}:</b> ${esc(b.skip)}</span></div>`;
      return `<p>${b.p.map((h) => { const s = ss[si++]; const caps = st.captures.filter((c) => c.paper === p.id && c.ch === st.ch && c.s === s.i && !c.removed);
        const fc = caps.length ? `style="--fc:var(--hl-${caps[caps.length - 1].kind})"` : "";
        return `<span class="s${caps.length ? " flagged" : ""}" tabindex="0" data-s="${s.i}" ${fc}>${h}</span>`; }).join(" ")}</p>`;
    }).join("");
    const ch = p.chapters[st.ch] || p.chapters[0];
    const resumeAt = fmt(position());
    return `<div class="listen${st.panelOpen ? " panel-open" : " no-panel"}" id="listen">
      <div class="desk"><article class="sheet" id="sheet" aria-label="${esc(p.title)}">
        <div class="sheet-top"><a class="btn sm quiet" href="#/paper/${p.id}/prepare" style="margin-left:-10px">${icon("text", "s")}${t("paper.prepare")}</a><span class="crumb"><b>${esc(ch.t)}</b> · <span class="num" id="pg">${t("listen.page", { n: ch.page })}</span></span>
          <span class="tools"><a class="icon-btn" href="#/paper/${p.id}/focus" aria-label="${t("listen.focus")}" title="${t("listen.focus")} (F)">${icon("focus")}</a>
          <button class="icon-btn" data-act="panel" aria-label="${st.panelOpen ? t("listen.hidepanel") : t("listen.panel")}" title="${st.panelOpen ? t("listen.hidepanel") : t("listen.panel")} (P)" aria-pressed="${st.panelOpen}">${icon("panel")}</button></span></div>
        <h2 class="ch">${esc(ch.t.replace(/^\d+\.\s*/, ""))}</h2>
        <p class="voice-note">${t("listen.ai", { voice: p.voice || "Heart" })}</p>
        ${st.resumePending && !st.playing ? `<div class="resume"><span>${t("listen.resume", { t: `<span class="num">${resumeAt}</span>` })}</span><button class="btn primary sm" data-act="play">${t("listen.continue", { t: resumeAt })}</button><button class="btn sm" data-act="restart">${t("listen.start")}</button></div>` : ""}
        <div id="text" lang="${p.lang}">${blocks}</div>
        <div class="page-flags" id="pflags" aria-hidden="true"></div>
      </article></div>
      <aside class="panel" aria-label="${t("panel." + st.panel)}">${panelHTML(p)}</aside></div>`;
  }

  function panelHTML(p) {
    const tab = (id) => `<button role="tab" aria-selected="${st.panel === id}" data-act="tab" data-id="${id}">${t("panel." + id)}${id === "captures" ? ` <span class="num" style="color:var(--pencil)">${chCaps(p).length}</span>` : ""}</button>`;
    let body = "";
    if (st.panel === "captures") {
      const comp = st.composer ? composerHTML() : "";
      const caps = chCaps(p, true).map(capHTML).join("");
      body = `${comp}<h3>${t("panel.inch")}</h3>${caps || (comp ? "" : `<p style="color:var(--pencil);font-size:14px">${t("panel.nocaps")}</p>`)}`;
    } else if (st.panel === "changes") {
      body = `<p style="color:var(--pencil);font-size:13.5px">${t("panel.chg.hint")}</p>` + [
        ["(Okafor & Lind, 2021)", null, "citations", "Author-year citation."], ["(t(34) = 2.81, p < .01)", null, "statistics", "Test statistic inside a citation bracket."],
        ["ms", "milliseconds", "units", "Unit read as a word."], ["h", "hours", "units", "Unit read as a word."], ["e.g.", "for example", "abbreviations", "Abbreviation spelled out."],
        ["³ Two participants…", "Footnote 3, read after its sentence", "footnotes", "Read right after the sentence with its mark."], ["Table 2", "Table 2 is skipped. It lists…", "placeholders", "Spoken notice."], ["[14]", null, "citations", "Numbered citation."],
      ].map(([a, b, cat, why]) => { const off = st.catsOff.has(cat); return `<div class="chg-item"><div class="row"><span class="pr" ${off ? "" : 'style="text-decoration:line-through;text-decoration-color:var(--pencil)"'}>${esc(a)}</span><input type="checkbox" role="switch" class="switch" ${off ? "" : "checked"} aria-label="${t("cat." + cat)}: ${esc(a)}" data-act="cat" data-id="${cat}"></div>
        <div>${off ? `<span class="why">${t("prep.switchedoff")}</span>` : b ? `→ ${esc(b)}` : `→ <span class="why">${t("prep.notread")}</span>`}</div><div class="why">${t("cat." + cat)} · ${esc(why)}</div></div>`; }).join("");
    } else {
      const maxC = 6;
      body = `<ol class="outline">${p.chapters.filter((c) => !c.off).map((c, i) => { const n = st.captures.filter((x) => x.paper === p.id && x.ch === i && !x.removed).length;
        return `<li><a href="#" data-act="gochap" data-i="${i}" aria-current="${i === st.ch}"><span class="ot">${esc(c.t)}</span><span class="num" style="color:var(--pencil);font-size:13px">${fmt(c.sec)}</span>
        <span class="om num"><span class="ramp" data-n="${n}" style="width:${n ? 6 + Math.min(n, maxC) * 10 : 4}px" aria-hidden="true"></span>${n} ${t("nav.captures").toLowerCase()} · ${t("prep.page", { n: c.page })}</span></a></li>`; }).join("")}</ol>`;
    }
    return `<div class="panel-tabs" role="tablist">${tab("captures")}${tab("changes")}${tab("outline")}<button class="icon-btn" data-act="panel" aria-label="${t("listen.hidepanel")}">${icon("x", "s")}</button></div><div class="panel-body" role="tabpanel">${body}</div>`;
  }
  const chCaps = (p, all) => st.captures.filter((c) => c.paper === p.id && c.ch === st.ch && (all || !c.removed)).sort((a, b) => (a.s ?? 99) - (b.s ?? 99));
  function capHTML(c) {
    const p = paper(c.paper);
    const body = c.kind === "quote" ? `<q>“${esc(c.text)}”</q>` : c.kind === "card" ? `<div class="txt"><b>${esc(c.front)}</b></div><div class="txt" style="color:var(--ink-2)">${esc(c.back)}</div>` : c.kind === "note" ? `${c.quote ? `<q>“${esc(c.quote)}”</q>` : ""}<div class="txt">${esc(c.text)}</div>` : `<div class="txt">${esc(c.text)}</div>`;
    return `<article class="cap${c.removed ? " cancelled" : ""}${c.live ? " live" : ""}" data-id="${c.id}">${flag(c.kind)}<span class="k">${t("cap." + c.kind + ".k")}</span>${body}
      <div class="foot num"><span>${t("prep.page", { n: c.page })} · ${c.at}</span><span class="acts">${c.removed ? `<button class="btn sm quiet" data-act="restore" data-id="${c.id}">${icon("undo", "s")}${t("cap.restore")}</button>` : `
        <button class="icon-btn" data-act="playcap" data-id="${c.id}" aria-label="${t("cap.play")}" title="${t("cap.play")}">${icon("play", "s")}</button>
        <button class="icon-btn" data-act="removecap" data-id="${c.id}" aria-label="${t("cap.remove")}" title="${t("cap.remove")}">${icon("x", "s")}</button>`}</span></div></article>`;
  }
  function composerHTML() {
    const c = st.composer; const s = sentences(paper())[c.s];
    const fields = c.kind === "card"
      ? `<label class="sr" for="cfront">${t("cap.front")}</label><textarea class="input" id="cfront" rows="2" style="min-height:60px" placeholder="${t("cap.front")}">${esc(s.plain.replace(/\.$/, "?"))}</textarea><label class="sr" for="cback">${t("cap.back")}</label><textarea class="input" id="cback" rows="2" style="min-height:60px" placeholder="${t("cap.back")}"></textarea>`
      : `<label class="sr" for="cnote">${t("cap.note")}</label><textarea class="input" id="cnote" placeholder="${t("cap.note.ph")}"></textarea>`;
    return `<form class="composer" id="composer">${flag(c.kind)}<span class="k">${t("cap." + c.kind + ".k")}</span><span class="paused-note">${icon("pause", "s")}${t("cap.paused")}</span><q>“${esc(s.plain)}”</q>${fields}
      <span class="hint">${t("cap.savehint", { mod })}</span><div class="row"><button type="button" class="btn sm quiet" style="margin-left:auto" data-act="cancelcap">${t("cap.cancel")}</button><button class="btn sm primary" type="submit">${t("cap.save")}</button></div></form>`;
  }

  function afterListen() {
    layoutFlags();
    markSentence(false);
    if (st.composer) setTimeout(() => $("#composer textarea")?.focus(), 0);
  }
  function layoutFlags(newId) {
    const sheet = $("#sheet"), box = $("#pflags"); if (!sheet || !box) return;
    const p = paper(); const top0 = sheet.getBoundingClientRect().top;
    const used = {};
    box.innerHTML = chCaps(p, true).filter((c) => c.s !== undefined).map((c) => {
      const el = $(`.s[data-s="${c.s}"]`); if (!el) return "";
      const y = Math.round(el.getBoundingClientRect().top - top0 + 6); const k = used[c.s] = (used[c.s] || 0) + 1;
      return `<span class="flag ${c.kind}${c.removed ? " gone" : ""}${c.id === newId ? " new" : ""}" style="top:${y + (k - 1) * 21}px" data-id="${c.id}" title="${t("cap." + c.kind + ".k")}">${icon(c.kind)}</span>`;
    }).join("");
    if (newId) requestAnimationFrame(() => requestAnimationFrame(() => $(`#pflags .flag[data-id="${newId}"]`)?.classList.remove("new")));
  }

  /* ---------- player ---------- */
  let timer = null, startedAt = 0, curDur = 0;
  function loadPaper(id) { const p = paper(id); pause(); st.current = id; st.ch = p.currentChapter ?? 0; st.si = p.listened ? (p.resumeSentence ?? 0) : 0; st.pausedFrac = p.listened ? 0.45 : 0; st.resumePending = !!p.listened; }
  const elapsedFrac = () => curDur ? Math.min(1, (performance.now() - startedAt) / 1000 / curDur) : 0;
  function markSentence(animate = true) {
    const ss = sentences(paper());
    $$(".s").forEach((el) => { const i = +el.dataset.s; el.classList.toggle("done", i < st.si); if (i !== st.si) { el.classList.remove("now", "paused"); el.style.removeProperty("--sweep"); } });
    const el = $(`.s[data-s="${st.si}"]`);
    if (el) {
      el.classList.add("now");
      if (st.playing && animate) {
        const s = ss[st.si]; const left = s.dur / st.speed * (1 - (st.pausedFrac || 0));
        el.classList.add("paused"); el.style.setProperty("--sweep", `${(st.pausedFrac || 0) * 100}%`); void el.offsetWidth;
        el.classList.remove("paused"); el.style.setProperty("--dur", `${left}s`); el.style.setProperty("--sweep", "100%");
      } else { el.classList.add("paused"); el.style.setProperty("--sweep", `${(st.pausedFrac || 0) * 100}%`); }
      if ($("#sheet") && st.follow !== false && st.playing) { const r = el.getBoundingClientRect(); if (r.top < 120 || r.bottom > innerHeight - 160) el.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
    }
    if (st.focus) updateFocus();
    updateDockTime();
    if (st.announce && st.playing) $("#announce").textContent = ss[st.si]?.plain || "";
  }
  function play() {
    const p = paper(); if (!hasAudio(p)) return;
    const ss = sentences(p); if (st.si >= ss.length) st.si = 0;
    st.playing = true; st.resumePending = false; $(".resume")?.remove();
    const s = ss[st.si]; curDur = s.dur / st.speed; const left = curDur * (1 - (st.pausedFrac || 0));
    startedAt = performance.now() - (curDur - left) * 1000;
    markSentence(true); st.pausedFrac = 0;
    clearTimeout(timer); timer = setTimeout(advance, left * 1000);
    renderDockState();
  }
  function pause() {
    if (st.playing) st.pausedFrac = elapsedFrac();
    st.playing = false; clearTimeout(timer);
    const el = $(`.s[data-s="${st.si}"]`); if (el) { el.classList.add("paused"); el.style.setProperty("--sweep", `${st.pausedFrac * 100}%`); }
    renderDockState();
  }
  function advance() {
    const ss = sentences(paper()); st.pausedFrac = 0;
    if (st.si < ss.length - 1) { st.si++; play(); } else { st.playing = false; markSentence(false); renderDockState(); }
  }
  function seek(i, keepPlaying = st.playing) {
    const ss = sentences(paper()); st.si = Math.max(0, Math.min(ss.length - 1, i)); st.pausedFrac = 0; clearTimeout(timer);
    if (keepPlaying) play(); else { st.playing = false; markSentence(false); const el = $(`.s[data-s="${st.si}"]`); el?.classList.add("now", "paused"); renderDockState(); }
  }
  const toggle = () => (st.playing ? pause() : play());
  function renderDock() {
    const dock = $("#dock"); const p = paper();
    const show = hasAudio(p) && st.scenario !== "empty" && st.scenario !== "firstrun";
    dock.hidden = !show; document.documentElement.style.setProperty("--dock", show ? "88px" : "0px");
    if (!show) return;
    const total = p.audioSec || p.chapters.reduce((a, c) => a + c.sec, 0);
    let x = 0; const marks = p.chapters.map((c) => { const at = (x / total) * 100; x += c.sec; return `<i class="chap" style="left:${at}%"></i>`; }).join("");
    const flags = st.captures.filter((c) => c.paper === p.id && !c.removed).map((c) => { const at = ((chStart(p, c.ch) + ((c.s ?? 3) / 10) * (p.chapters[c.ch]?.sec || 600)) / total) * 100; return `<i class="tf" style="left:${at}%;background:var(--hl-${c.kind})"></i>`; }).join("");
    dock.innerHTML = `<div class="timeline"><span class="track"></span><span class="fill" id="fill"></span>${marks}${flags}<input type="range" min="0" max="${total}" step="1" aria-label="${t("player.timeline")}" id="scrub"></div>
      <div class="transport"><button class="icon-btn" data-act="prev" aria-label="${t("player.prev")}" title="${t("player.prev")} (←)">${icon("prev")}</button>
      <button class="play" data-act="toggle" id="playbtn"></button>
      <button class="icon-btn" data-act="next" aria-label="${t("player.next")}" title="${t("player.next")} (→)">${icon("next")}</button></div>
      <div class="nowplaying"><b>${esc(p.title)}</b><span class="num" id="dtime"></span></div>
      <label class="speed"><span class="sr">${t("player.speed")}</span><select id="speed" data-act="speed">${[0.75, 1, 1.25, 1.5, 1.75, 2].map((v) => `<option value="${v}" ${v === st.speed ? "selected" : ""}>${String(v).replace(".", st.lang === "de" ? "," : ".")}×</option>`).join("")}</select></label>
      <div class="capkeys" role="group" aria-label="${t("keys.capture")}">${["note", "quote", "card", "mark"].map((k) => `<button data-act="capture" data-kind="${k}" title="${t("keys." + k)} (${k[0].toUpperCase()})">${flag(k)}<span class="lbl">${t("cap." + k)}</span><kbd>${k[0].toUpperCase()}</kbd></button>`).join("")}</div>`;
    renderDockState(); updateDockTime();
  }
  function renderDockState() {
    const b = $("#playbtn"); if (!b) return;
    b.innerHTML = `<svg class="i l" aria-hidden="true"><use href="#i-${st.playing ? "pause" : "play"}"/></svg>`;
    b.setAttribute("aria-label", st.playing ? t("player.pause") : t("player.play")); b.title = (st.playing ? t("player.pause") : t("player.play")) + " (Space)";
  }
  function updateDockTime() {
    const p = paper(); if (!hasAudio(p) || !$("#dtime")) return;
    const total = p.audioSec || p.chapters.reduce((a, c) => a + c.sec, 0); const pos = position();
    $("#dtime").textContent = `${p.chapters[st.ch]?.t || ""} · ${t("player.of", { a: fmt(pos), b: fmt(total) })} · ${String(st.speed).replace(".", st.lang === "de" ? "," : ".")}×`;
    $("#fill").style.width = `${(pos / total) * 100}%`; $("#scrub").value = pos;
  }
  setInterval(() => { if (st.playing) updateDockTime(); }, 500);

  /* ---------- focus listening ---------- */
  function viewFocus() {
    const p = paper();
    return `<div class="focus-view"><div class="focus-top"><span><b style="color:var(--ink)">${esc(p.title)}</b> · ${esc(p.chapters[st.ch].t)}</span><a class="btn" href="#/paper/${p.id}/listen">${icon("x", "s")}${t("close")} <kbd>Esc</kbd></a></div>
      <div class="focus-stage" aria-live="off"><p class="prev" id="fprev"></p><p class="cur" id="fcur" lang="${p.lang}"></p><p class="next" id="fnext"></p></div>
      <div class="focus-foot"><span><kbd>Space</kbd> ${t("keys.play")}</span><span><kbd>←</kbd> <kbd>→</kbd> ${t("keys.prevnext")}</span><span><kbd>N</kbd> <kbd>Q</kbd> <kbd>C</kbd> <kbd>M</kbd> ${t("keys.capture")}</span></div></div>`;
  }
  function updateFocus() {
    const ss = sentences(paper()); const cur = ss[st.si]; if (!$("#fcur")) return;
    $("#fprev").textContent = ss[st.si - 1]?.plain || ""; $("#fnext").textContent = ss[st.si + 1]?.plain || "";
    $("#fcur").innerHTML = `<span class="${st.playing ? "on" : ""}">${esc(cur.plain)}</span>`;
    const sp = $("#fcur span");
    if (st.playing) { sp.style.transition = "none"; sp.style.setProperty("--sweep", "0%"); void sp.offsetWidth; sp.style.transition = ""; sp.style.setProperty("--dur", `${cur.dur / st.speed}s`); sp.style.setProperty("--sweep", "100%"); }
    else sp.style.setProperty("--sweep", `${(st.pausedFrac || 0) * 100}%`);
  }

  /* ---------- capture ---------- */
  let capN = 100;
  function capture(kind) {
    const p = paper(); if (!hasAudio(p)) return;
    const r = route();
    if (r.view !== "paper" || (r.sub !== "listen" && r.sub !== "focus")) { location.hash = `#/paper/${p.id}/listen`; }
    let s = st.si;
    if (kind === "quote" || kind === "mark") {
      // grace: a capture in the first 1.2 s of a sentence belongs to the sentence that just ended
      if (st.playing && s > 0 && (performance.now() - startedAt) / 1000 < 1.2) s--;
      const ss = sentences(p);
      const c = { id: "n" + capN++, paper: p.id, ch: st.ch, kind, s, text: kind === "quote" ? ss[s].plain : ss[s].plain.split(" ").slice(0, 6).join(" ") + " …", page: p.chapters[st.ch].page, at: fmt(position()), live: true };
      st.captures.push(c); earcon(kind); refreshCaptures(c.id);
      toast(kind, t(kind === "quote" ? "cap.saved.quote" : "cap.saved.mark", { p: c.page }), () => { st.captures = st.captures.filter((x) => x.id !== c.id); refreshCaptures(); });
    } else {
      pause();
      st.composer = { kind, s };
      if (st.focus) { location.hash = `#/paper/${p.id}/listen`; }
      st.panelOpen = true; st.panel = "captures";
      if (route().sub === "listen") { refreshListen(); $("#composer textarea")?.focus(); }
    }
  }
  function saveComposer() {
    const c = st.composer; if (!c) return; const p = paper(); const ss = sentences(p);
    const cap = { id: "n" + capN++, paper: p.id, ch: st.ch, kind: c.kind, s: c.s, page: p.chapters[st.ch].page, at: fmt(position()), live: true };
    if (c.kind === "card") { cap.front = $("#cfront").value.trim() || ss[c.s].plain; cap.back = $("#cback").value.trim() || ss[c.s].plain; }
    else { cap.quote = ss[c.s].plain; cap.text = $("#cnote").value.trim() || "…"; }
    st.captures.push(cap); st.composer = null; earcon(c.kind); refreshCaptures(cap.id);
    toast(c.kind, t(c.kind === "card" ? "cap.saved.card" : "cap.saved.note"), () => { st.captures = st.captures.filter((x) => x.id !== cap.id); refreshCaptures(); });
    $(`.s[data-s="${st.si}"]`)?.focus({ preventScroll: true }); play();
  }
  function closeComposer(resume = true) { if (!st.composer) return; st.composer = null; refreshListen(); if (resume) play(); }
  function refreshListen() { const pnl = $(".panel"); if (!pnl) return; pnl.innerHTML = panelHTML(paper()); const l = $("#listen"); l.classList.toggle("no-panel", !st.panelOpen); l.classList.toggle("panel-open", st.panelOpen); layoutFlags(); }
  function refreshCaptures(newId) {
    renderShell(route());
    if ($(".panel")) { $(".panel").innerHTML = panelHTML(paper()); const p = paper();
      $$(".s").forEach((el) => { const caps = chCaps(p).filter((c) => c.s === +el.dataset.s); el.classList.toggle("flagged", !!caps.length); if (caps.length) el.style.setProperty("--fc", `var(--hl-${caps[caps.length - 1].kind})`); });
      layoutFlags(newId); }
    st.captures.forEach((c) => delete c.live);
    const stateSnap = { playing: st.playing }; renderDock(); if (stateSnap.playing) renderDockState();
  }
  let actx;
  function earcon(kind) {
    if (!st.sounds) return;
    try { actx = actx || new AudioContext(); const o = actx.createOscillator(), g = actx.createGain(); const f = { note: 660, quote: 880, card: 520, mark: 990 }[kind];
      o.frequency.value = f; o.type = "sine"; g.gain.setValueAtTime(0.0001, actx.currentTime); g.gain.exponentialRampToValueAtTime(0.08, actx.currentTime + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, actx.currentTime + 0.18);
      o.connect(g).connect(actx.destination); o.start(); o.stop(actx.currentTime + 0.2); } catch { /* no audio context */ }
  }
  function toast(kind, msg, undo) {
    const el = document.createElement("div"); el.className = "toast";
    el.innerHTML = `${kind ? flag(kind) : icon("check")}<span>${esc(msg)}</span>${undo ? `<button type="button">${t("cap.undo")}</button>` : ""}`;
    $("#toasts").append(el);
    const kill = () => el.remove(); const tm = setTimeout(kill, 6000);
    el.querySelector("button")?.addEventListener("click", () => { clearTimeout(tm); undo(); kill(); });
  }

  /* ---------- captures view ---------- */
  function viewCaptures() {
    const all = st.scenario === "empty" ? [] : st.captures;
    const kinds = ["all", "note", "quote", "card", "mark"];
    const count = (k) => all.filter((c) => !c.removed && (k === "all" || c.kind === k)).length;
    const list = all.filter((c) => (st.capFilter === "all" || c.kind === st.capFilter) && (st.capPaper === "all" || c.paper === st.capPaper));
    const byPaper = {}; list.forEach((c) => (byPaper[c.paper] = byPaper[c.paper] || []).push(c));
    const groups = Object.entries(byPaper).map(([pid, cs]) => { const p = paper(pid);
      return `<section class="cap-group"><h2>${esc(p.title)}</h2><p class="gm num">${esc(p.authors)} · ${cs.length} ${t("nav.captures").toLowerCase()}</p><div class="cap-list">${cs.map(capHTML).join("")}</div></section>`; }).join("");
    const cards = all.filter((c) => c.kind === "card" && !c.removed);
    const papersWith = [...new Set(all.map((c) => c.paper))];
    return `<div class="view"><header class="view-head"><div><h1>${t("caps.title")}</h1><p class="sub num">${t("caps.sub", { n: count("all"), p: papersWith.length })}</p></div>
      <div class="actions"><button class="btn primary" data-act="review" ${cards.length ? "" : "disabled"}>${icon("card", "s")}${t("caps.review")} <span class="num">${cards.length}</span></button></div></header>
      ${st.review ? reviewHTML(cards) : ""}
      <div class="capview"><div>
        <div class="cap-filters"><div class="seg" role="group" aria-label="${t("caps.title")}">${kinds.map((k) => `<button aria-pressed="${st.capFilter === k}" data-act="capfilter" data-id="${k}">${k === "all" ? "" : `<span class="flag ${k}" style="width:16px;height:14px" aria-hidden="true"></span>`}${k === "all" ? t("caps.all") : t("cap." + k)} <span class="num">${count(k)}</span></button>`).join("")}</div>
        <label style="display:flex;gap:8px;align-items:center">${t("caps.from")} <select class="input" style="width:auto" data-act="cappaper"><option value="all">${t("caps.alldocs")}</option>${papersWith.map((id) => `<option value="${id}" ${st.capPaper === id ? "selected" : ""}>${esc(paper(id).title)}</option>`).join("")}</select></label></div>
        ${groups || `<p style="color:var(--pencil)">${t("caps.none")}</p>`}</div>
      <aside class="export" aria-labelledby="exp-h"><h2 id="exp-h" style="font-size:17px">${t("exp.title")}</h2><p style="color:var(--pencil);font-size:14px;margin-top:-4px">${t("exp.hint")}</p>
        ${target("zotero", "quote", all)}${target("obsidian", "note", all)}${target("anki", "card", all)}
        <section class="target"><header>${icon("download")}<b>${t("exp.md")}</b></header><p>${t("exp.md.d")}</p><div class="row"><button class="btn sm">${t("exp.save")}</button></div></section>
      </aside></div></div>`;
  }
  function target(id, kind, all) {
    const n = all.filter((c) => !c.removed && (c.kind === kind || (id === "obsidian" && c.kind === "quote"))).length;
    const offline = id === "anki" && st.ankiOffline;
    const sent = st.sent[id];
    return `<section class="target"><header>${flag(kind)}<b>${t("exp." + id)}</b><span class="state ${offline ? "warn" : "ready"}">${icon(offline ? "alert" : "check", "s")}${offline ? t("exp.offline") : t("exp.connected")}</span></header>
      <p>${t("exp." + id + ".d")}</p>${id === "obsidian" ? `<p class="num" style="font-size:13px"><span class="path">${t("exp.vault", { p: "~/Vault/Readings" })}</span></p>` : ""}
      ${offline && sent ? `<p style="color:var(--wait);font-weight:700;font-size:14px">${t("exp.queued", { n })}</p>` : ""}
      <div class="row"><button class="btn sm" data-act="send" data-id="${id}" data-n="${n}">${icon("send", "s")}${t("exp.send", { n })}</button><small class="num">${sent && !offline ? t("exp.sent", { n: sent.n, t: sent.t }) : t("exp.never")}</small></div></section>`;
  }
  function reviewHTML(cards) {
    const r = st.review; const c = cards[r.i % cards.length]; if (!c) return "";
    return `<section class="review" aria-label="${t("caps.review")}"><div class="row">${flag("card")}<span class="from">${t("rev.from", { paper: esc(paper(c.paper).title), p: c.page })}</span><span class="pos num">${t("rev.of", { a: r.i + 1, b: cards.length })}</span><button class="icon-btn" data-act="endreview" aria-label="${t("close")}">${icon("x", "s")}</button></div>
      <p class="front">${esc(c.front)}</p>${r.show ? `<p class="back">${esc(c.back)}</p><div class="row"><button class="btn" data-act="revnext">${t("rev.again")}</button><button class="btn primary" data-act="revnext">${t("rev.good")}</button></div>` : `<div class="row"><button class="btn primary" data-act="revshow">${t("rev.show")} <kbd>Space</kbd></button></div>`}</section>`;
  }

  /* ---------- voices ---------- */
  function viewVoices() {
    const pack = (id, inst, files) => {
      const total = files.reduce((a, f) => a + f[1], 0); const dl = st.download === id;
      return `<section class="pack"><header>${icon("voices")}<b>${t("voices." + id)}</b><span class="state ${inst ? "ready" : "idle"}">${icon(inst ? "check" : "download", "s")}${inst ? t("voices.installed") : t("voices.missing")}</span></header>
        <table class="num"><thead><tr><th>${t("voices.file")}</th><th class="n">${t("voices.size")}</th><th>${t("voices.licence")}</th></tr></thead><tbody>${files.map((f) => `<tr><td>${f[0]}</td><td class="n">${f[1]} MB</td><td>${f[2]}</td></tr>`).join("")}</tbody></table>
        ${inst ? (id === "en" ? `<div class="voices-list" role="group" aria-label="${t("voices.pick")}">${[["Heart", "US"], ["Bella", "US"], ["Nicole", "US"], ["Michael", "US"], ["Emma", "UK"], ["George", "UK"], ["Fable", "UK"], ["Lewis", "UK"]].map(([v, a]) => `<button aria-pressed="${st.defaultVoice === v}" data-act="defvoice" data-id="${v}"><span>${v}<small>${a === "US" ? (st.lang === "de" ? "Amerikanisches Englisch" : "American English") : (st.lang === "de" ? "Britisches Englisch" : "British English")}</small></span>${icon("speaker", "s")}</button>`).join("")}</div>` : "")
        : `<div class="foot"><p style="font-size:14px;color:var(--ink-2)">${t("voices.hosts")}</p><label class="check"><input type="checkbox" data-act="consent" data-id="${id}" ${st.consent === id ? "checked" : ""}>${t("voices.consent")}</label>
          <div>${dl ? `<div class="job"><div class="bar"><i style="width:${st.dlP}%"></i></div><span class="num" style="font-size:14px">${t("voices.downloading", { p: st.dlP })}</span></div>` : `<button class="btn primary" data-act="download" data-id="${id}" ${st.consent === id ? "" : 'aria-disabled="true"'}>${icon("download", "s")}${t("voices.download", { s: total + " MB" })}</button>`}</div></div>`}</section>`;
    };
    return `<div class="view doc-col"><header class="view-head"><div><h1>${t("voices.title")}</h1><p class="sub">${t("voices.sub")}</p></div></header>
      ${pack("en", st.voiceEN, [["kokoro-v1_0.pth", 312, "Apache-2.0"], ["voices/en (28 voices)", 14, "Apache-2.0"], ["en_core_web_sm (spaCy)", 29, "MIT"]])}
      ${pack("de", st.voiceDE, [["kokoro-thorsten.pth", 318, "Apache-2.0 (CC0 data)"], ["voices/dm_thorsten.pt", 1, "Apache-2.0"], ["espeak-ng data (de)", 11, "GPL-3.0"]])}</div>`;
  }
  function viewPrivacy() {
    const de = st.lang === "de";
    return `<div class="view doc-col prose"><header class="view-head"><div><h1>${t("privacy.title")}</h1></div></header>
      <p class="lead">${de ? "sci2audio ist ein Programm auf deinem Computer, kein Onlinedienst. Niemand erhält deine Daten, auch nicht die Leute, die sci2audio machen." : "sci2audio is a program on your computer, not an online service. Nobody receives your data, not even the people who make sci2audio."}</p>
      <h2>${de ? "Nichts verlässt diesen Computer" : "Nothing leaves this computer"}</h2><ul><li>${de ? "Keine Telemetrie, keine Nutzungsstatistik, keine Absturzberichte, keine Update-Prüfung, kein Konto." : "No telemetry, no usage statistics, no crash reports, no update check, no account."}</li><li>${de ? "Zotero, Obsidian und Anki werden nur auf diesem Computer angesprochen, und nur, wenn du sendest." : "Zotero, Obsidian and Anki are reached only on this computer, and only when you send."}</li></ul>
      <h2>${de ? "Die eine Ausnahme: der Stimmen-Download, den du startest" : "The one exception: the voice download you start"}</h2><p>${de ? "Vorher siehst du jede Datei mit Größe, Lizenz und Host." : "Before it starts you see every file with its size, licence and host."}</p>
      <h2>${de ? "Die Oberfläche ist nur für dich" : "The interface is for you only"}</h2><p>${de ? "Sie hört nur auf 127.0.0.1, mit einem Schlüssel, der bei jedem Start neu ist, und lädt nichts aus dem Internet." : "It listens only on 127.0.0.1, with a key that is new at each start, and loads nothing from the internet."}</p>
      <h2>${de ? "Wo deine Dateien sind" : "Where your files are"}</h2><ul class="num"><li><span class="path">~/Library/Application Support/sci2audio</span> ${de ? "Analysen, Notizen, Einstellungen" : "analyses, captures, settings"}</li><li><span class="path">~/Library/Caches/sci2audio</span> ${de ? "Sprach-Zwischenspeicher und Stimmen" : "speech cache and voices"}</li></ul></div>`;
  }
  function viewSettings() {
    const seg = (name, opts, cur) => `<div class="seg" role="group" aria-label="${name}">${opts.map(([v, l]) => `<button aria-pressed="${cur === v}" data-act="set-${name}" data-id="${v}">${l}</button>`).join("")}</div>`;
    return `<div class="view"><header class="view-head"><div><h1>${t("settings.title")}</h1></div></header><div class="settings">
      <section><h2>${t("settings.appearance")}</h2>${seg("theme", [["system", t("settings.system")], ["light", t("settings.light")], ["dark", t("settings.dark")]], st.theme)}
        <h2>${t("settings.language")}</h2>${seg("lang", [["en", "English"], ["de", "Deutsch"]], st.lang)}</section>
      <section><h2>${t("settings.defaults")}</h2><div class="field"><label for="dfolder">${t("settings.folder")}</label><input class="input" id="dfolder" value="~/Audiobooks"></div>
        <div class="field"><label for="dspeed">${t("settings.speed")}</label><select class="input" id="dspeed" style="width:auto">${[0.75, 1, 1.25, 1.5].map((v) => `<option ${v === st.speed ? "selected" : ""}>${v}×</option>`).join("")}</select></div></section>
      <section><label class="check"><input type="checkbox" role="switch" class="switch" data-act="announce" ${st.announce ? "checked" : ""}><span><b>${t("settings.announce")}</b><br><span style="color:var(--pencil);font-size:14px">${t("settings.announce.hint")}</span></span></label>
        <label class="check"><input type="checkbox" role="switch" class="switch" data-act="sounds" ${st.sounds ? "checked" : ""}><b>${t("settings.sounds")}</b></label></section></div></div>`;
  }

  /* ---------- shortcuts dialog ---------- */
  function openKeys() {
    const k = (keys, label) => `<div><span>${label}</span><span>${keys.map((x) => `<kbd>${x}</kbd>`).join(" ")}</span></div>`;
    $("#keys").innerHTML = `<header><h2 id="keys-h">${t("keys.title")}</h2><button class="icon-btn" data-act="closekeys" aria-label="${t("close")}">${icon("x")}</button></header><div class="keys">
      <h3>${t("keys.listen")}</h3>${k(["Space"], t("keys.play"))}${k(["←", "→"], t("keys.prevnext"))}${k(["⇧ ←", "⇧ →"], t("keys.chap"))}${k(["−", "+"], t("keys.speed"))}
      <h3>${t("keys.capture")}</h3>${k(["N"], t("keys.note"))}${k(["Q"], t("keys.quote"))}${k(["C"], t("keys.card"))}${k(["M"], t("keys.mark"))}
      <h3>${t("keys.move")}</h3>${k(["F"], t("keys.focus"))}${k(["P"], t("keys.panel"))}${k(["?"], t("keys.help"))}${k(["Esc"], t("keys.esc"))}
      <div class="note-line">${t("keys.note.line")}</div></div>`;
    $("#keys").showModal();
  }

  /* ---------- simulations ---------- */
  setInterval(() => {
    st.papers.forEach((p) => {
      if (p.state === "making" && !p.paused) {
        p.progress = Math.min(1, p.progress + (p.fast ? 0.04 : 0.002));
        p.job.chapter = Math.min(p.job.chapters, 1 + Math.floor(p.progress * p.job.chapters));
        if (p.progress >= 1) { p.state = "ready"; p.audioSec = p.chapters.reduce((a, c) => a + c.sec, 0) || 1800; p.audio = p.audio?.replace(/^about /, "") || "30 min"; toast(null, `${t("job.done")}: ${p.title}`); }
        const r = route(); if (r.view === "paper" && r.id === p.id && r.sub === "prepare") { if (p.state === "making") { const b = $("#jobbody"); if (b) b.innerHTML = makeBlock(p); } else { const sc = $("#main").scrollTop; render(); $("#main").scrollTop = sc; } }
        if (r.view === "library" || p.state === "ready") renderShell(r);
        if (r.view === "library" && $(".papers")) { const sc = $("#main").scrollTop; $("#main").innerHTML = viewLibrary(); $("#main").scrollTop = sc; }
      }
    });
  }, 1000);

  /* ---------- events ---------- */
  document.addEventListener("click", (e) => {
    const s = e.target.closest(".s");
    if (s && !e.target.closest("a")) { seek(+s.dataset.s, true); return; }
    const pf = e.target.closest("#pflags .flag"); if (pf) { st.panelOpen = true; st.panel = "captures"; refreshListen(); $(`.cap[data-id="${pf.dataset.id}"]`)?.scrollIntoView({ block: "nearest" }); return; }
    const scn = e.target.closest("[data-scn]");
    if (scn) { const v = scn.dataset.scn; st.scenario = v === "offline" ? "normal" : v; st.ankiOffline = v === "offline"; st.voiceEN = v !== "firstrun"; e.target.closest("details").open = false; pause(); location.hash = v === "offline" ? "#/captures" : "#/library"; render(); return; }
    const a = e.target.closest("[data-act]"); if (!a) return;
    const act = a.dataset.act, id = a.dataset.id, p = paper(route().id) || paper();
    const rerender = () => { const sc = $("#main").scrollTop; render(); $("#main").scrollTop = sc; };
    switch (act) {
      case "toggle": toggle(); break;
      case "play": play(); break;
      case "restart": st.si = 0; st.pausedFrac = 0; seek(0, true); break;
      case "prev": seek(st.si - 1); break;
      case "next": seek(st.si + 1); break;
      case "capture": capture(a.dataset.kind); break;
      case "cancelcap": closeComposer(true); break;
      case "panel": st.panelOpen = !st.panelOpen; refreshListen(); break;
      case "tab": st.panel = id; refreshListen(); break;
      case "gochap": e.preventDefault(); st.ch = +a.dataset.i; st.si = 0; st.pausedFrac = 0; pause(); rerender(); break;
      case "playcap": { const c = st.captures.find((x) => x.id === id); location.hash = `#/paper/${c.paper}/listen`; if (st.current !== c.paper) loadPaper(c.paper); st.ch = c.ch; setTimeout(() => seek(c.s ?? 0, true), 50); render(); break; }
      case "removecap": { const c = st.captures.find((x) => x.id === id); c.removed = true; refreshCaptures(); if (route().view === "captures") rerender(); toast(null, t("cap.removed"), () => { c.removed = false; refreshCaptures(); if (route().view === "captures") rerender(); }); break; }
      case "restore": { const c = st.captures.find((x) => x.id === id); c.removed = false; refreshCaptures(); if (route().view === "captures") rerender(); break; }
      case "keys": openKeys(); break;
      case "closekeys": $("#keys").close(); break;
      case "lang": st.lang = st.lang === "en" ? "de" : "en"; localStore("lang", st.lang); e.target.closest("details").open = false; rerender(); break;
      case "theme": { const dark = document.documentElement.dataset.theme === "dark" || (st.theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches); st.theme = dark ? "light" : "dark"; localStore("theme", st.theme); e.target.closest("details").open = false; rerender(); break; }
      case "set-theme": st.theme = id; localStore("theme", id); rerender(); break;
      case "set-lang": st.lang = id; localStore("lang", id); rerender(); break;
      case "up": case "down": { const i = +a.dataset.i, j = act === "up" ? i - 1 : i + 1; const cs = p.chapters; [cs[i], cs[j]] = [cs[j], cs[i]]; st.dirty = true; rerender(); const li = $(`.chapter[data-i="${j}"]`); li?.classList.add("moved"); li?.querySelector(`[data-act="${act}"]`)?.focus(); break; }
      case "all": p.chapters.forEach((c) => { c.unchosen = false; if (c.off) c.chosen = true; }); st.dirty = true; rerender(); break;
      case "none": p.chapters.forEach((c) => { c.unchosen = true; c.chosen = false; }); st.dirty = true; rerender(); break;
      case "update": st.dirty = false; rerender(); toast(null, st.lang === "de" ? "Analyse aktualisiert" : "Analysis updated"); break;
      case "analyse": st.analysing = id; st.analyseP = 8; rerender(); { const iv = setInterval(() => { st.analyseP += 23; if (st.analyseP >= 100) { clearInterval(iv); st.analysing = null; const q = paper(id); q.state = "analysed"; q.pages = 9; q.audio = "about 15 min"; q.chapters = [{ t: "1. What power is", page: 1, sentences: 60, sec: 0 }, { t: "2. Effect size", page: 4, sentences: 72, sec: 0 }, { t: "3. Sample size", page: 7, sentences: 48, sec: 0 }]; q.langSource = "guessed from the text"; } rerender(); }, 500); } break;
      case "make": if (a.getAttribute("aria-disabled") === "true") break; p.state = "making"; p.progress = p.failure ? p.failure.kept / p.chapters.length : 0; p.fast = true; p.paused = false; p.job = { chapter: 1, chapters: Math.max(1, p.chapters.filter((c) => !c.off).length), total: Math.round(p.words / 18), left: st.lang === "de" ? "etwa 1 Minute übrig" : "about 1 minute left" }; delete p.failure; rerender(); break;
      case "pausejob": p.paused = !p.paused; rerender(); break;
      case "canceljob": p.state = "analysed"; p.paused = false; rerender(); toast(null, t("job.cancelled")); break;
      case "speed": break;
      case "sample": earcon("quote"); break;
      case "capfilter": st.capFilter = id; rerender(); break;
      case "review": st.review = { i: 0, show: false }; rerender(); break;
      case "revshow": st.review.show = true; rerender(); break;
      case "revnext": st.review = { i: st.review.i + 1, show: false }; rerender(); break;
      case "endreview": st.review = null; rerender(); break;
      case "send": { const now = new Date().toTimeString().slice(0, 5); st.sent[id] = { n: a.dataset.n, t: now }; rerender(); if (!(id === "anki" && st.ankiOffline)) toast(null, `${t("exp." + id)}: ${t("exp.sent", { n: a.dataset.n, t: now })}`); break; }
      case "defvoice": st.defaultVoice = id; earcon("note"); rerender(); break;
      case "download": if (a.getAttribute("aria-disabled") === "true") break; st.download = id; st.dlP = 0; rerender(); { const iv = setInterval(() => { st.dlP = Math.min(100, st.dlP + 9); if (st.dlP >= 100) { clearInterval(iv); st.download = null; if (id === "en") { st.voiceEN = true; if (st.scenario === "firstrun") st.scenario = "normal"; } else st.voiceDE = true; } rerender(); }, 300); } break;
      case "noop": e.preventDefault(); break;
      case "paste": { const np = { id: "pasted" + capN++, title: $("#pname").value || "pasted text", authors: st.lang === "de" ? "Eingefügter Text" : "Pasted text", kind: "txt", lang: "en", langSource: "not analysed yet", pages: 0, words: 640, state: "new", lastOpened: "Now", chapters: [] }; st.papers.unshift(np); if (st.scenario === "empty") st.scenario = "normal"; location.hash = `#/paper/${np.id}/prepare`; break; }
    }
  });
  document.addEventListener("change", (e) => {
    const a = e.target.closest("[data-act]"); if (!a) return;
    const act = a.dataset.act, p = paper(route().id) || paper();
    const rerender = () => { const sc = $("#main").scrollTop; render(); $("#main").scrollTop = sc; };
    if (act === "cat") { st.catsOff[a.checked ? "delete" : "add"](a.dataset.id); st.dirty = true; if (route().sub === "listen") refreshListen(); else { rerender(); $(`[data-act="cat"][data-id="${a.dataset.id}"]`)?.focus(); } }
    if (act === "chap") { const c = p.chapters[+a.dataset.i]; if (c.off) c.chosen = a.checked; else c.unchosen = !a.checked; st.dirty = true; rerender(); $(`[data-act="chap"][data-i="${a.dataset.i}"]`)?.focus(); }
    if (act === "speed") { const was = st.playing; if (was) pause(); st.speed = +a.value; if (was) play(); updateDockTime(); }
    if (act === "cappaper") { st.capPaper = a.value; rerender(); }
    if (act === "consent") { st.consent = a.checked ? a.dataset.id : false; rerender(); $(`[data-act="consent"]`)?.focus(); }
    if (act === "announce") st.announce = a.checked;
    if (act === "sounds") st.sounds = a.checked;
    if (act === "file") { const f = a.files[0]; if (!f) return; const np = { id: "file" + capN++, title: f.name.replace(/\.[^.]+$/, ""), authors: f.name, kind: /epub$/i.test(f.name) ? "epub" : /pdf$/i.test(f.name) ? "pdf" : "txt", lang: "en", langSource: "not analysed yet", pages: 0, words: 4200, state: "new", lastOpened: "Now", chapters: [] }; st.papers.unshift(np); if (st.scenario === "empty") st.scenario = "normal"; location.hash = `#/paper/${np.id}/prepare`; }
  });
  document.addEventListener("input", (e) => {
    if (e.target.dataset.act === "search") { st.q = e.target.value; const pos = e.target.selectionStart; render(); const s = $('[data-act="search"]'); s.focus(); s.setSelectionRange(pos, pos); }
    if (e.target.id === "scrub") { const p = paper(); const ss = sentences(p); const v = +e.target.value; let ch = 0, x = 0; while (ch < p.chapters.length - 1 && x + p.chapters[ch].sec <= v) { x += p.chapters[ch].sec; ch++; } if (ch !== st.ch) { st.ch = ch; if (route().sub === "listen") render(); } seek(Math.floor(((v - x) / (p.chapters[ch].sec || 1)) * ss.length)); }
  });
  document.addEventListener("submit", (e) => { if (e.target.id === "composer") { e.preventDefault(); saveComposer(); } });
  document.addEventListener("keydown", (e) => {
    const tag = e.target.tagName, typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag) || e.target.isContentEditable;
    if (e.target.closest?.("#composer")) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); saveComposer(); }
      if (e.key === "Escape") { e.preventDefault(); closeComposer(true); $(`.s[data-s="${st.si}"]`)?.focus(); }
      return;
    }
    if (e.key === "Escape") { if ($("#keys").open) return; if (st.focus) { location.hash = `#/paper/${st.current}/listen`; return; } $$("details[open]").forEach((d) => (d.open = false)); if (st.review) { st.review = null; render(); } return; }
    if (e.metaKey || e.ctrlKey || e.altKey || typing) return;
    const r = route(); const inReader = r.view === "paper" && (r.sub === "listen" || r.sub === "focus");
    if (e.key === "?") { e.preventDefault(); openKeys(); return; }
    if (r.view === "captures" && st.review && e.key === " ") { e.preventDefault(); st.review.show = true; render(); return; }
    if (!inReader) return;
    const onControl = /^(BUTTON|A|SUMMARY)$/.test(tag) && !e.target.classList.contains("s");
    const k = e.key.toLowerCase();
    if (e.key === " " && !onControl) { e.preventDefault(); toggle(); }
    else if (e.key === "Enter" && e.target.classList.contains("s")) { e.preventDefault(); seek(+e.target.dataset.s, true); }
    else if (e.key === "ArrowLeft" && !onControl) { e.preventDefault(); if (e.shiftKey) { st.ch = Math.max(0, st.ch - 1); st.si = 0; render(); } else seek(st.si - 1); }
    else if (e.key === "ArrowRight" && !onControl) { e.preventDefault(); if (e.shiftKey) { st.ch = Math.min(paper().chapters.filter((c) => !c.off).length - 1, st.ch + 1); st.si = 0; render(); } else seek(st.si + 1); }
    else if (k === "n") { e.preventDefault(); capture("note"); }
    else if (k === "q") { e.preventDefault(); capture("quote"); }
    else if (k === "c") { e.preventDefault(); capture("card"); }
    else if (k === "m") { e.preventDefault(); capture("mark"); }
    else if (k === "f") { e.preventDefault(); location.hash = st.focus ? `#/paper/${st.current}/listen` : `#/paper/${st.current}/focus`; }
    else if (k === "p" && r.sub === "listen") { e.preventDefault(); st.panelOpen = !st.panelOpen; refreshListen(); }
    else if (e.key === "-" || e.key === "+" || e.key === "=") { const opts = [0.75, 1, 1.25, 1.5, 1.75, 2]; const i = opts.indexOf(st.speed); const ni = Math.max(0, Math.min(opts.length - 1, i + (e.key === "-" ? -1 : 1))); const was = st.playing; if (was) pause(); st.speed = opts[ni]; if (was) play(); renderDock(); }
  });
  const drop = (e) => { const d = e.target.closest?.("#drop"); if (!d) return; e.preventDefault(); d.classList.toggle("over", e.type === "dragover"); };
  ["dragover", "dragleave", "drop"].forEach((ev) => document.addEventListener(ev, drop));
  window.addEventListener("resize", () => layoutFlags());

  // review switches: ?theme=dark&lang=de&state=firstrun|empty|offline (not remembered)
  const qp = new URLSearchParams(location.search);
  if (qp.get("theme")) st.theme = qp.get("theme");
  if (qp.get("lang")) st.lang = qp.get("lang");
  if (qp.get("state")) { const v = qp.get("state"); st.scenario = v === "offline" ? "normal" : v; st.ankiOffline = v === "offline"; st.voiceEN = v !== "firstrun"; }
  loadPaper(st.current);
  if (!location.hash) location.hash = "#/paper/sleep/listen";
  render();
})();
