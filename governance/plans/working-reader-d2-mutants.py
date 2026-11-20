"""One-line mutants for Working Reader batch D, PR D2: copy src/, apply one mutant, run the
tests that should kill it with PYTHONPATH=<copy>/src (the copy's templates and static files
are the ones served)."""
import os, pathlib, shutil, subprocess, sys
REPO = pathlib.Path(os.environ.get("REPO", "/home/user/sci2audio-d2"))
WORK = pathlib.Path(sys.argv[1])
L = "sci2audio/web/library.py"
P = "sci2audio/web/pages.py"
C = "sci2audio/cli.py"
J = "sci2audio/web/static/app.js"
TI = "sci2audio/web/templates/index.html"
TV = "sci2audio/web/templates/voice.html"
TD = "sci2audio/web/templates/document.html"
UNIT = ["-m", "not slow and not benchmark and not browser", "tests/unit/test_web_library.py",
        "tests/unit/test_web_pages.py", "tests/unit/test_web_design.py", "tests/unit/test_cli_convert.py",
        "tests/unit/test_web_outside.py"]
BROWSER = ["-m", "browser", "tests/browser/test_library.py", "tests/browser/test_voice_cards.py",
           "tests/browser/test_flow.py::test_a_report_downloaded_while_the_page_loads_leaves_it_wired"]
MUTANTS = [
    ("U0 clean baseline", L, "def folded(text: str) -> str:", "def folded(text: str) -> str:", UNIT),
    ("U1 accents kept", L, 'if not unicodedata.category(c).startswith("M")', "if True", UNIT),
    ("U2 sharp s kept", L, 'return plain.replace("ß", "ss")', "return plain", UNIT),
    ("U3 any word", L, "return all(word in found_by", "return any(word in found_by", UNIT),
    ("U4 authors not searched", L, 'return folded(" ".join([title, *authors, file]))', 'return folded(" ".join([title, file]))', UNIT),
    ("U5 rows never hidden", TI, '{% if row.id not in shown %} hidden{% endif %}', "", UNIT),
    ("U6 no-match never said", TI, "{% if query and not shown %}", "{% if false %}", UNIT),
    ("U7 default not first", P, "key=lambda v: (v.id != default, v.language, v.name)", "key=lambda v: (v.language, v.name)", UNIT),
    ("U8 missing size of all packs", P, 'sum(f.size for f in missing if f.pack == language)', "sum(f.size for f in missing)", UNIT),
    ("U9 sample buttons enabled", TV, 'data-stop-short="{{ t(\'setup.stop_short\') }}" disabled>', 'data-stop-short="{{ t(\'setup.stop_short\') }}">', UNIT),
    ("U10 CLI document number", C, "number = event.chapter_number", "number = event.chapter + 1", UNIT),
    ("U11 report link navigates", TD, '?download=true" download aria-label="{{ t(\'document.file_report_md\') }}"', '?download=true" aria-label="{{ t(\'document.file_report_md\') }}"', UNIT),
    ("B0 clean baseline", J, "function folded(text) {", "function folded(text) {", BROWSER),
    ("B1 JS accents kept", J, '.normalize("NFKD").replace(/\\p{M}/gu, "")', "", BROWSER),
    ("B2 JS any word", J, "row.hidden = !words.every(", "row.hidden = !words.some(", BROWSER),
    ("B3 region kept on no match", J, "region.hidden = shown === 0;", "", BROWSER),
    ("B4 two files dropped open", J, "if (dropped.length !== 1) {", "if (dropped.length < 1) {", BROWSER),
    ("B5 no over state", J, 'form.classList.toggle("over", on)', "null", BROWSER),
    ("B6 drop hint never shown", J, "if (hint) hint.hidden = false;", "", BROWSER),
    ("B7 second sample does not stop first", J, "      const again = playing === button;\n      stop();", "      const again = playing === button;", BROWSER),
    ("B8 sample buttons stay disabled", J, "    button.disabled = false;\n  }\n}", "  }\n}", BROWSER),
    ("B9 sample never plays", J, "audio.play().catch(() => stop());", "", BROWSER),
    # round 1 (#446 review S1, N1): each must be killed by its new test
    ("R2 a stopped sample still plays", J, "          if (mine !== asked) return; // stopped, or another sample asked for since\n", "", BROWSER),
    ("R3 a sample that ended keeps Stop", J, '  audio.addEventListener("ended", stop);\n', "", BROWSER),
    ("R4 command-line rows cannot be found", P, '"find": search_text(job.name, (), job.name),', '"find": "",', UNIT),
    ("R5 a drop beside the opener opens the file", J, '      event.preventDefault();\n      event.dataTransfer.dropEffect = "none";\n', "", BROWSER),
    ("R6 every drag beside the opener cancelled", J, "      if (!carriesFiles(event) || form.contains(event.target)) return;", "      if (form.contains(event.target)) return;", BROWSER),
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
