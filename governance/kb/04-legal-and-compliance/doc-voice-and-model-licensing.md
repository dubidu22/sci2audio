# Voice and model licensing: what may be sold, served, shipped

`[DOC]` · Status: **inventory current as of 9 Nov 2026; German free-tier decision open (audit B-05)** · Owner: Colin · **Not legal advice.** · Related: `audit-legal-readiness.md` (A-03…A-06, D-01, D-05), `doc-copyright-and-tos-liability.md`, `02-product-and-pipeline/doc-mobile-listening-app.md`, ADR-005, ADR-006, `docs/RECHTSLAGE.md`, `browserstimme.py`, `piperstimmen.py`, `tts.py`, `web.py` (`OFFERED_VOICES`, `SOLD_VOICES`, `UNLICENSED_VOICES`, `OFFLINE_ONLY_VOICES`)

> **Status after the pivot (D-41): active.** Governs which voices and models the open-source app may ship or download (D-43). The sales-mode sections are archived.

Three different licence questions apply to every component. They're often confused:
1. **Use on the server** (SaaS): sci2audio runs it; users get output.
2. **Distribution:** sci2audio ships the model or code to users (the browser voice today; desktop/mobile apps tomorrow).
3. **Output rights:** may the generated audio be sold or handed to a paying user?

---

## 1. Inventory

| Component | Licence of code / weights / data `[external fact unless noted]` | Server use, paid | Distribution | Output in paid runs | Where it runs today `[repo fact]` |
|---|---|---|---|---|---|
| **Azure Speech Neural / HD** (prebuilt voices) | Microsoft Product Terms + Products and Services DPA. Output-use rights: "For Customers of the **paid tier** TTS Service only, Customer may use the audio output of prebuilt neural voices … including for commercial purposes" (quoted in a Microsoft Q&A answer) | ✅ on paid tier (S0) | n/a (cloud) | ✅ (paid tier) — with disclosure of the synthetic voice (Code of Conduct) and **no use of output to train a competing TTS** | Server; `SOLD_VOICES`; region Sweden Central |
| **Piper Thorsten de_DE medium** | Data: Thorsten-Voice **CC0**. Weights: MODEL_CARD says "Finetuned from U.S. English lessac voice (medium quality)". lessac rests on Blizzard Challenge 2013 data, released for **non-commercial research** only. The Piper author calls the legal status "not yet clarified" (artifact; HF discussion 94) | ❌ not for sale (`sale=False`) | ⚠️ served to browsers in **free test mode** (63 MB, `/api/browserstimme/<version>/`) | ❌ | Browser ("Thorsten im Browser") |
| **Piper English: Linda (LJ Speech), Kristin, Cori, Norman (LibriVox)** | Public-domain recordings, **trained from scratch**; MODEL_CARD shipped | ✅ | ✅ (`sale=True`) | ✅ | Browser |
| **Piper English: John** | Public domain; fine-tuned from **Kristin** (itself from scratch) — not from lessac | ✅ | ✅ | ✅ | Browser |
| Piper lessac/Ryan family (Alan, Amy, Kerstin, Karlsson, Thorsten low, Jenny, Alba, VCTK, LibriTTS-R …) | Research-only or CC BY-NC-SA origins | ❌ | ❌ | ❌ | Not shipped (`browserstimme.py` comment) |
| Piper HFC female (Hi-Fi CAPTAIN, NICT) | **CC BY-NC-SA 4.0** | ❌ | ❌ | ❌ | CLI only; `piperstimmen.NONCOMMERCIAL` (the earlier "HiFi-TTS, CC BY 4.0, NVIDIA" mislabel is fixed) |
| Piper MLS (de, CC BY 4.0, from scratch), LibriTTS (en, CC BY 4.0) | Clean, but multi-speaker | ✅ (with attribution) | ✅ | ✅ | Not shipped yet (needs a speaker picker). **MLS would be a sellable German male voice** per `RECHTSLAGE.md` |
| Piper runtime `piper1-gpl` | **GPL-3.0** | ✅ (GPL triggers on distribution, not on running a service) | ⚠️ GPL duties if shipped | n/a | sci2audio doesn't import Piper; phonemes via `piper_lautschrift.py` (GPL-3, separate program) |
| espeak-ng (phonemizer behind Piper/Kokoro) | **GPL-3.0** | ✅ | ⚠️ | n/a | Server (separate process) |
| onnxruntime / onnxruntime-web 1.31.1 | MIT | ✅ | ✅ (licence beside file) | n/a | Browser bundle |
| lamejs 1.2.7 (MP3 encoder in the browser) | **LGPL-3.0**, shipped unmodified with licence text | ✅ | ✅ with LGPL duties (below) | n/a | Browser bundle |
| **Kokoro-82M** (hexgrad) | Weights **Apache 2.0**; inference code MIT; espeak-ng GPLv3 dependency | ✅ | ✅ (Apache NOTICE) | ✅ | CLI/local only (`OFFLINE_ONLY_VOICES`: needs a full CPU core for minutes) |
| **Kokoro German — Thorsten-Voice/Kokoro** | Fine-tune of Kokoro-82M on the **CC0** Thorsten-Voice dataset (12,283 sentences); released **Apache 2.0** | ✅ | ✅ | ✅ | `.[kokoro-de]` extra; not on Fly (PyTorch CPU build not in the image) |
| Other German Kokoro voices (kikiri victoria/martin, HUI-based base model, CC0 corpus; Apache 2.0) | Apache 2.0, per their model cards | ✅ (verify each card) | ✅ | ✅ | Not used |
| **Edge TTS** (unofficial Read Aloud endpoint) | No contract; Microsoft points commercial users to Azure; per a developer report, Microsoft blocked the browser method on 17 Dec 2025 | ❌ | ❌ | ❌ | CLI only (`UNLICENSED_VOICES`) |
| System voices (macOS `say`, Windows SAPI) | Apple: "personal, non-commercial use" | ❌ online | ❌ | ❌ | Local only (`OFFLINE_ONLY_VOICES`) |
| **Device voice** (Web Speech API, live in the visitor's browser, no file) | The user uses their own OS/browser voices | n/a (no server output) | n/a | No file is produced; offering an MP3 from it would not be allowed | Online ("Gerätestimme", `geraetestimme.py`); lawyer to confirm Q-L08 |
| OpenAI TTS, ElevenLabs | Commercial per their terms; OpenAI requires a clear notice that the voice is AI-generated | ✅ | n/a | ✅ | CLI providers in `tts.py`; not online |
| **Anthropic** Haiku 5.5 / Sonnet 5.5 | Commercial Terms: outputs belong to the customer; no training on API data; customer warrants rights to inputs; may build own products, not resell the raw API | ✅ | n/a | ✅ | Server |
| PP-DocLayoutV2 (PaddleOCR, Apache 2.0) → ONNX (Apache 2.0), onnxruntime (MIT) | Apache/MIT | ✅ | ✅ | n/a | Local only (`bildmodell.py`) |

## 2. Consequences for sales mode

| Language | Free file voice in sales mode | Paid file voices | Free live voice |
|---|---|---|---|
| English | ✅ Piper Linda/Kristin/Cori/Norman/John (browser) | Azure Neural/HD | Device voice |
| **German** | ❌ **none** (Thorsten `sale=False`) | Azure Neural/HD | Device voice |

This conflicts with:
- the price page (`preise.html`: "Standardstimme (Thorsten …) 0,00 €"), audit D-05;
- Batch 3's package "Kostenlos-Datei" and the Thorsten quota logic (`Pricing.thorsten_gratis = 50,000`, `thorsten_cent = 5`). Those knobs only matter while Thorsten can be served, i.e. in the free test.

## 3. Obligations by licence type

### 3.1 Apache 2.0 (Kokoro, Thorsten-Voice/Kokoro, PP-DocLayoutV2)
- Ship the licence text and any NOTICE file when distributing; state changes to modified files.
- No copyleft; fine for server, desktop and app stores.

### 3.2 CC BY 4.0 data (MLS, LibriTTS voices)
- Attribution to the dataset authors when distributing the model: ship the MODEL_CARD (already the pattern). An "Über die Stimmen" page lists sources.
- CC0/public domain: no duty, attribution still good practice.

### 3.3 LGPL-3.0 (lamejs in the browser bundle)
- Ship the licence text (done). Keep lamejs as a **separate, replaceable file**, not minified into app code, so users can swap it (done: unmodified, beside the licence).
- If lamejs is ever modified, publish the modified source.
- In a mobile app bundle the same applies; the replaceability requirement is easier with a separate JS file than with a compiled bundle.

### 3.4 GPL-3.0 (Piper runtime, espeak-ng, `piper_lautschrift.py`, `kokoro_sprecher.py`)
- **Server use: no duty to publish source.** GPL triggers on distribution, unlike AGPL. Keeping GPL code in separate programs called as processes (the repo's pattern) also keeps the rest of sci2audio out of GPL scope.
- **Distribution (desktop app, local mode installer, Capacitor app with on-device TTS):** offer the complete corresponding source of the GPL parts and the licence, under GPL.
- **App stores:** distributing GPL software through Apple's App Store is widely considered problematic, because store terms add restrictions that GPL forbids `[advisor proposal — known community position, not verified this session]`. If on-device German TTS is wanted in the iOS app, prefer **Kokoro with a non-GPL phonemizer** or server-generated audio (the listening app's v1 plays server files anyway, ADR-005/ADR-006).

### 3.5 Azure Speech terms (summary)
- Paid tier (S0) for commercial output rights; F0 (free tier) is for evaluation. Audit B-07: verify the resource.
- Code of Conduct: disclose the synthetic nature. Done via the AI label in metadata and player; add a line to the price/voice pages.
- **Output must not be used to create, train or improve a TTS.** sci2audio's `sci2audio stimme` training tool must **never** use Azure audio as training data. Write that into the tool's docs and refuse Azure-generated WAVs in its data loader.
- Data: prebuilt neural voice input/output not stored in Microsoft logs (Microsoft documentation).

### 3.6 Anthropic
- No training on inputs/outputs; outputs owned by the customer.
- The customer's input-rights warranty means a copyright problem with a user's text is also a contract problem with Anthropic. That's another reason for "AI only on green".

## 4. Thorsten: the three ways to a sellable German voice

| Option | What | Licence status | Effort / cost | Quality | Fit |
|---|---|---|---|---|---|
| **A. Kokoro German (Thorsten-Voice/Kokoro)** on a **worker** | Run the Apache-2.0 Kokoro fine-tune on a dedicated CPU worker (ADR-002 job queue), not on the web machines | ✅ clean (CC0 data, Apache weights) | M: PyTorch CPU in a worker image; a dedicated CPU machine (Fly performance CPU) only while jobs run; per-minute cost to measure | Natural; Thorsten's own voice | **Best**: same voice users know, legally clean |
| B. Own Piper Thorsten **from scratch** (`sci2audio stimme`, since 1 Nov) | Train VITS from random init on the CC0 dataset; MODEL_CARD names the source | ✅ clean by construction | L: rented GPU for days, plus evaluation `[advisor estimate, unverified]`; tool exists but untrained | Unknown until trained; Piper medium quality at best | Keeps the free in-browser voice for German (no server CPU) |
| C. Piper MLS (de, CC BY 4.0, from scratch, multi-speaker) | Add a speaker picker to the browser voice | ✅ with attribution | S–M: UI for speaker choice; pick 1–2 good speakers | Varies by speaker | Fast route to *a* free sellable German browser voice |
| D. Wait for upstream re-training on a clean base | Piper's author was reported to retrain voices on a CC-BY base (LibriTTS-R) | Depends on result | 0 effort, unknown timing | — | Watch, don't plan on it |
| E. No free German file voice | Device voice live only; files only with Azure | ✅ | 0 | Device-dependent | Launch fallback (audit B-05 default) |

`[advisor proposal]` Launch with **E**, build **C** as the quick German browser voice (no server cost, keeps the "Thorsten im Browser" architecture), and plan **A** with the phase-2 worker. B only if C's quality disappoints and A's CPU cost is too high.

## 5. Process: voice licence gate (for every new voice or model)
1. Read the MODEL_CARD: dataset licence **and** training base ("fine-tuned from …"). `piperstimmen.from_lessac()` automates this for Piper.
2. Classify server use / distribution / output for paid mode (table in §1).
3. Set `sale=True/False` (browser) or add to `SOLD_VOICES`/`UNLICENSED_VOICES`/`OFFLINE_ONLY_VOICES`.
4. Ship licence + MODEL_CARD; update `RECHTSLAGE.md` and the ToS voice section in the same PR (`lane:voice`, `risk:high` for anything sold).
5. Record in `decision-log.md`.

## 6. Advisor pre-analysis
- **The repo's licence hygiene is good.** `from_lessac()` checks, `sale` flags and licence files beside bundles are more than most commercial projects do. The weak spot is **documentation drift** (`RECHTSLAGE.md` still promises Kokoro in sales mode).
- **German free files are the gap**, and they matter commercially: the "free file" is the acquisition hook for students. Close it with MLS (cheap) or Kokoro-on-worker (best), not by risking Thorsten-lessac.
- **Desktop/mobile changes the licence surface.** Everything GPL that is fine on a server becomes a distribution duty in an installer, and a likely blocker in the App Store. Factor this into ADR-005 phase 4.
- **Azure's "no training on output" clause** is easy to violate by accident in a voice-training side project. Guard it in code.

## 7. Critical open questions
| # | Question | Default |
|---|---|---|
| Q1 | German free tier at launch: E only, or E + MLS (C) before launch? | E at launch, C within 4 weeks |
| Q2 | Kokoro worker CPU cost per 1,000 words on Fly performance CPUs? | Measure in the phase-2 spike |
| Q3 | Is the device voice (live, no file) fine in sales mode? | Yes per repo; lawyer Q-L08 confirms |
| Q4 | Azure resource tier and region confirmed? | S0, EU (audit B-07) |
| Q5 | Remove Edge/HFC/system voices from the codebase before any distributed app? | Yes; keep only in a dev-only extra |
