"""One-line mutants for Working Reader batch D, PR D3 (#394, #447, #452; review round 1): copy src/, apply one
mutant, run the tests that should kill it with PYTHONPATH=<copy>/src (the copy's templates
and static files are the ones served). Usage: REPO=<checkout> python3 this.py <work> [ids]"""
import os, pathlib, shutil, subprocess, sys
REPO = pathlib.Path(os.environ.get("REPO", "/home/user/sci2audio-d3"))
WORK = pathlib.Path(sys.argv[1])
PJ = "sci2audio/web/static/player.js"
J = "sci2audio/web/static/app.js"
TB = "sci2audio/web/templates/base.html"
TL = "sci2audio/web/templates/listen.html"
CSS = "sci2audio/web/static/app.css"
UNIT = ["-m", "not slow and not benchmark and not browser", "tests/unit/test_web_design.py",
        "tests/unit/test_web_listen.py", "tests/unit/test_web_languages.py"]
BROWSER = ["-m", "browser", "-n", "4", "tests/browser/test_focus.py", "tests/browser/test_listen.py",
           "tests/browser/test_settings.py"]
P = "sci2audio/web/pages.py"
I = "sci2audio/web/i18n.py"
TS = "sci2audio/web/templates/settings.html"
# Round 1 of the review (plans/review-pr451-round1.md): B13 was a duplicate of B2 and B15 is
# dropped as asked; both numbers stay unused. U5-U9 and B27-B47 are new for S1-S4, N1,
# D-711 and #452.
MUTANTS = [
    ("U0 clean baseline", TB, "<!doctype html>", "<!doctype html>", UNIT),
    ("U1 rail item enabled", TB, 'id="keys-open" aria-haspopup="dialog" disabled>', 'id="keys-open" aria-haspopup="dialog">', UNIT),
    ("U2 sheet's Close enabled", TB, 'title="{{ t(\'common.close\') }}" disabled>{{ icon(\'x\') }}', 'title="{{ t(\'common.close\') }}">{{ icon(\'x\') }}', UNIT),
    ("U3 focus view shown", TL, 'tabindex="-1" hidden>', 'tabindex="-1">', UNIT),
    ("U4 Focus button enabled", TL, '{% if keys %} aria-keyshortcuts="F"{% endif %} disabled>', '{% if keys %} aria-keyshortcuts="F"{% endif %}>', UNIT),
    ("U5 S3 the route keeps no keys cookie", P, "        (KEYS_COOKIE, known_keys(keys)),  # one of KEYS\n", "", UNIT),
    ("U6 S3 no data-keys on the page", TB, '{% if keys is sameas false %} data-keys="off"{% endif %}', "", UNIT),
    ("U7 S3 keys off by default", I, 'return known_keys(request.cookies.get(KEYS_COOKIE)) != "off"', 'return known_keys(request.cookies.get(KEYS_COOKIE)) == "on"', UNIT),
    ("U8 S3 the switch never ticked", TS, "{% if keys %} checked{% endif %}", "", UNIT),
    ("U9 D-711 the light mark back to the reading yellow", CSS, "--now: #B08400;", "--now: #FFE94A;", UNIT),
    ("B0 clean baseline", PJ, '"use strict";', '"use strict";', BROWSER),
    ("B1 #447 a press closes the panel", PJ, "!narrowOpen || pressing || panel", "!narrowOpen || panel", BROWSER),
    ("B2 #447 focus elsewhere keeps it open", PJ, '  document.addEventListener("focusin", (event) => left(event.target));\n', "", BROWSER),
    ("B3 keys act while typing", PJ, "if (!shortcutsOn() || typing(event.target)) return;", "if (!shortcutsOn()) return;", BROWSER),
    ("B4 keys act with modifiers", PJ, "if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;\n    if (document.querySelector", "if (event.defaultPrevented) return;\n    if (document.querySelector", BROWSER),
    ("B5 keys act under the sheet", PJ, '    if (document.querySelector("dialog[open]")) return;\n    const key = event.key;\n', "    const key = event.key;\n", BROWSER),
    ("B6 Space taken from a control", PJ, 'if (key === " " && !onControl) {', 'if (key === " ") {', BROWSER),
    ("B7 arrows taken from a control", PJ, '(key === "ArrowLeft" || key === "ArrowRight") && !onControl)', '(key === "ArrowLeft" || key === "ArrowRight"))', BROWSER),
    ("B8 Shift moves by sentence", PJ, "if (event.shiftKey) toChapter(", "if (false) toChapter(", BROWSER),
    ("B9 speed not said", PJ, '    say(tr("player.speed_now", { speed: speed.options[to].text }));\n', "", BROWSER),
    ("B10 = is not plus", PJ, 'else if (key === "+" || key === "=") stepSpeed(1);', 'else if (key === "+") stepSpeed(1);', BROWSER),
    ("B11 P in Focus", PJ, '(key === "p" || key === "P") && !focusing)', '(key === "p" || key === "P"))', BROWSER),
    ("B12 focus not given back", PJ, "    reveal(marked);\n    focusOn.focus();", "    reveal(marked);", BROWSER),
    ("B14 stage not filled", PJ, "    marked = element;\n    stage();", "    marked = element;", BROWSER),
    ("B16 Space counts as a scroll", PJ, "if (event.defaultPrevented || !SCROLL_KEYS.has(event.key)) return;", "if (!SCROLL_KEYS.has(event.key)) return;", BROWSER),
    ("B17 reading not shown again", PJ, "    reveal(marked);\n    focusOn.focus();", "    focusOn.focus();", BROWSER),
    ("B18 Focus buttons stay disabled", PJ, "    focusOn,\n    focusOff,\n", "", BROWSER),
    ("B19 a select is no typing", J, 'target.closest("textarea, select, [contenteditable]', 'target.closest("textarea, [contenteditable]', BROWSER),
    ("B20 ? typed opens the sheet", J, "if (!shortcutsOn() || typing(event.target) || document.querySelector", "if (!shortcutsOn() || document.querySelector", BROWSER),
    ("B21 sheet's Close not wired", J, '  close.addEventListener("click", () => sheet.close());\n', "", BROWSER),
    ("B22 focus not given back by the sheet", J, "    if (opener && opener !== document.body && opener.isConnected) opener.focus();\n", "", BROWSER),
    ("B23 rail item stays disabled", J, "  open.disabled = false; // drawn disabled until here (#350, #427)\n", "", BROWSER),
    ("B24 ? never opens it", J, '    if (event.key !== "?" ||', '    if (true ||', BROWSER),
    ("B25 #452 the stage unmarked", CSS, "color: var(--on-now); background-color: var(--now); border-radius: 2px; padding: 0 4px;", "border-radius: 2px; padding: 0 4px;", BROWSER),
    ("B26 #452 an underline back on the mark", CSS, ".read-along .s.now { color: var(--on-now); background-color: var(--now); }", ".read-along .s.now { color: var(--on-now); background-color: var(--now); text-decoration: underline; }", BROWSER),
    ("B27 #452 the mark looks like the tint", CSS, ".read-along .s.now { color: var(--on-now); background-color: var(--now); }", ".read-along .s.now { color: var(--on-now); background-color: var(--held); }", BROWSER),
    ("B28 S1 a field keeps Esc from Focus", PJ, "    const key = event.key;\n    // Esc leaves", "    const key = event.key;\n    if (typing(event.target)) return;\n    // Esc leaves", BROWSER),
    ("B29 S2 a key does not end the press", PJ, '  window.addEventListener("keydown", released, true);\n', "", BROWSER),
    ("B30 S2 a context menu does not end it", PJ, '"pointercancel", "contextmenu", "blur"]', '"pointercancel", "blur"]', BROWSER),
    ("B31 S2 leaving the window does not end it", PJ, '"pointercancel", "contextmenu", "blur"]', '"pointercancel", "contextmenu"]', BROWSER),
    ("B32 S3 the Listen keys ignore the switch", PJ, "if (!shortcutsOn() || typing(event.target)) return;", "if (typing(event.target)) return;", BROWSER),
    ("B33 S3 ? ignores the switch", J, "if (!shortcutsOn() || typing(event.target) || document.querySelector", "if (typing(event.target) || document.querySelector", BROWSER),
    ("B34 S3 Esc obeys the switch", PJ, "    const key = event.key;\n    // Esc leaves", "    const key = event.key;\n    if (!shortcutsOn()) return;\n    // Esc leaves", BROWSER),
    ("B35 S3 the switch does not save itself", J, 'for (const name of ["announce", "keys"])', 'for (const name of ["announce"])', BROWSER),
    ("B36 S3 F still offered with the keys off", TL, '{% if keys %} aria-keyshortcuts="F"{% endif %}', ' aria-keyshortcuts="F"', BROWSER),
    ("B37 S3 the key hints stay in Focus", TL, '  {% if keys %}<p class="focus-foot">', '  {% if true %}<p class="focus-foot">', BROWSER),
    ("B38 N1 a held Space toggles", PJ, "if (once) play.click();", "play.click();", BROWSER),
    ("B39 N1 a held F toggles", PJ, "if (once) setFocus(!focusing);", "setFocus(!focusing);", BROWSER),
    ("B40 N1 a held P toggles", PJ, 'if (once) document.getElementById("panel-toggle").click();', 'document.getElementById("panel-toggle").click();', BROWSER),
    ("B41 S4e plus past the fastest", PJ, "if (to < 0 || to >= speed.options.length) return;", "if (to < 0) return;", BROWSER),
    ("B42 S4d a wheel in Focus scrolls away", PJ, "if (focusing || !following || !follow.checked) return;", "if (!following || !follow.checked) return;", BROWSER),
    ("B43 S4a the stage loses the cut", PJ, "return [...(words || element).childNodes].map((node) => node.cloneNode(true));", "return [document.createTextNode((words || element).textContent)];", BROWSER),
    ("B44 S4b the whole notice on the stage", PJ, 'element.classList.contains("notice") ? element.querySelector("p > span") : element;', "element;", BROWSER),
    ("B45 S4c Back stays on entering or leaving", PJ, "    back.hidden = true;\n    if (on) {", "    if (on) {", BROWSER),
    ("B46 S4c not following again", PJ, "    following = true;\n    back.hidden = true;\n    if (on) {", "    back.hidden = true;\n    if (on) {", BROWSER),
    ("B47 #452 the mark moves", CSS, ".read-along .s.now { color: var(--on-now); background-color: var(--now); }", ".read-along .s.now { color: var(--on-now); background-color: var(--now); transition: background-color 2s; }", BROWSER),
]
only = sys.argv[2:]
for name, rel, old, new, tests in MUTANTS:
    if only and name.split()[0] not in only:
        continue
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(REPO / "src", WORK / "src")
    f = WORK / "src" / rel
    s = f.read_text(encoding="utf-8")
    if s.count(old) != 1:
        print(f"{name}: PATTERN COUNT {s.count(old)}", flush=True)
        continue
    f.write_text(s.replace(old, new), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(WORK / "src"))
    r = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", "-x", *tests],
                       cwd=REPO, env=env, capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    fail = [l for l in lines if l.startswith("FAILED")]
    if name.split()[0][1:] == "0":
        verdict = "FAIL" if r.returncode else "PASS"
    else:
        verdict = "KILLED" if r.returncode else "SURVIVED"
    print(f"{name}: {verdict} | {fail[0] if fail else lines[-1] if lines else ''}", flush=True)
