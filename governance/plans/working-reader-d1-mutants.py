import shutil, subprocess, sys, os, pathlib
REPO = pathlib.Path("/home/user/sci2audio")
WORK = pathlib.Path(sys.argv[1])
P = "sci2audio/web/player.py"
T = "sci2audio/web/templates/listen.html"
J = "sci2audio/web/static/player.js"
MUTANTS = [
    ("M0 clean baseline", P, "def _looks(text: str) -> str:", "def _looks(text: str) -> str:"),
    ("M1 version guard off", P, "marked = bool(record.made_with) and record.made_with == __version__", "marked = True"),
    ("M2 whole-block cut marked", P, "if span.start == 0 and span.end >= len(block.text.rstrip()):", "if False:"),
    ("M3 looks-alike reading marked", P, "_looks(edit.replacement) != _looks(original)", "edit.replacement != original"),
    ("M4 hyphen joins marked", P, "edit.step in _UNMARKED_STEPS", "False"),
    ("M5 left-out chapters counted", P, "run.read_at(outcome.edit.span.block) in heard", "True"),
    ("M6 counts without marks", P, "counts.get(str(c), 0) if marked else None", "counts.get(str(c), 0)"),
    ("M7 every category on", P, "str(c) not in switched_off, counts", "True, counts"),
    ("M8 run with today's switches", P, "run = _settled(document, record.switched_off, steps)", "run = _settled(document, frozenset(), steps)"),
    ("M9 cut drawn as reading", P, '(span.start, span.end, "cut", "")', '(span.start, span.end, "said", "")'),
    ("M11 announce region always", T, '{% if announce %}<p id="reading"', '{% if true %}<p id="reading"'),
    ("M12 announce flag always", T, '{% if announce %} data-announce', '{% if true %} data-announce'),
    ("J0 clean baseline", J, "function sweepSync() {", "function sweepSync() {"),
    ("J1 announce never", J, "if (reading && element && !audio.paused)", "if (false)"),
    ("J2 no tint", J, 'marked.classList.add("done");', ""),
    ("J3 sweep under reduced motion", J, "if (!marked || reduced.matches || !marked.animate)", "if (!marked || !marked.animate)"),
    ("J4 Esc keeps panel", J, "event.preventDefault();\n      set(false);", "event.preventDefault();"),
    ("J5 focus stays on toggle", J, "if (open && !wide.matches) selected().focus();", ""),
    ("J6 arrows do not focus", J, "choose(tabs[to], true);", "choose(tabs[to], false);"),
    ("J7 panel controls stay disabled", J, "for (const control of [toggle, close, ...tabs]) control.disabled = false;", ""),
    ("J8 sweep never pauses", J, "if (audio.paused || pending || loaded < 0) sweep.pause();", "if (false) sweep.pause();"),
    ("J9 tint without adjacency", J, "if (element && !audio.paused && index > 0 && chunks[index - 1][3] === marked.id)", "if (element && !audio.paused)"),
    ("J10 timeline move not saved", J, "    keep(c, time);\n    showTime(time, true);\n  }", "    showTime(time, true);\n  }"),
    ("J11 panel stays open when the focus leaves", J, "panel.contains(event.relatedTarget)) return;\n    narrowOpen = false;", "panel.contains(event.relatedTarget)) return;"),
    ("J12 End stops at a 5 s step", J, 'else if (event.key === "End") to = Number(timeline.max);', 'else if (event.key === "End") to = Math.floor(Number(timeline.max) / 5) * 5;'),
    ("M14 cut not told to screen readers", T, "</s><span class=\"visually-hidden\"> {{ t('listen.cut_hidden') }}</span>", "</s>"),
    ("M13 marks note never", T, "{% if not view.marked %}", "{% if false %}"),
]
only = sys.argv[2:]
for name, rel, old, new in MUTANTS:
    if only and name.split()[0] not in only:
        continue
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(REPO / "src", WORK / "src")
    f = WORK / "src" / rel
    s = f.read_text()
    if s.count(old) != 1:
        print(f"{name}: PATTERN COUNT {s.count(old)}", flush=True); continue
    f.write_text(s.replace(old, new))
    env = dict(os.environ, PYTHONPATH=str(WORK / "src"))
    if name.startswith("M0"):
        pass
    tests = (["-m", "browser", "tests/browser/test_listen.py"] if rel == J else
             ["-m", "not slow and not benchmark and not browser", "tests/unit/test_web_listen.py", "tests/unit/test_web_player.py", "tests/unit/test_web_chapter_order.py"])
    r = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", "-x", *tests],
                       cwd=REPO, env=env, capture_output=True, text=True)
    last = [l for l in r.stdout.splitlines() if l.strip()][-1]
    fail = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
    print(f"{name}: {('FAIL' if r.returncode else 'PASS') if name[1]=='0' else ('KILLED' if r.returncode else 'SURVIVED')} | {fail[0] if fail else last}", flush=True)
