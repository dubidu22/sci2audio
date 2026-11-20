import subprocess, pathlib, sys
R = pathlib.Path("/home/user/sci2audio")
F = "src/sci2audio/layout/furniture.py"; O = "src/sci2audio/layout/order.py"; B = "src/sci2audio/layout/build.py"
M = [
 ("m01 skip-stamps-notes", F, "line.id in page.stamps\n                or line.id in page.notes\n                or line_size", "line_size"),
 ("m02 small >= -> >", F, "or line_size(line) >= settings.small * size\n                or starts", "or line_size(line) > settings.small * size\n                or starts"),
 ("m03 A >= -> >", F, "if pages >= most)", "if pages > most)"),
 ("m04 A no head_share", F, "most = max(settings.head_pages, settings.head_share * page_count)", "most = settings.head_pages"),
 ("m05 A no head_pages", F, "most = max(settings.head_pages, settings.head_share * page_count)", "most = settings.head_share * page_count"),
 ("m06 B no head_share", F, "short = max(settings.repeat_pages, settings.head_share * page_count)", "short = settings.repeat_pages"),
 ("m07 B no repeat_pages", F, "short = max(settings.repeat_pages, settings.head_share * page_count)", "short = settings.head_share * page_count"),
 ("m08 B apart dropped", F, "        if apart:\n            texts[text]", "        if True:\n            texts[text]"),
 ("m09 lending all", F, "lending = [(number, y) for number, y, _, apart, _ in lines if apart]", "lending = [(number, y) for number, y, _, apart, _ in lines]"),
 ("m10 no label guard", F, "                or starts_with_label(line.text)\n", ""),
 ("m11 bottom like top", F, 'if band == "bottom":', 'if False:'),
 ("m12 shape precondition off", F, "if not band or _repeated(places, box.y0, drift) < settings.repeat_pages:", "if not band:"),
 ("m13 pages_near no del", F, "            if not counts[number]:\n                del counts[number]\n", ""),
 ("m14 pages_near low <=", F, "ordered[low][1] < y - drift", "ordered[low][1] <= y - drift"),
 ("m15 pages_near high <", F, "ordered[high][1] <= y + drift", "ordered[high][1] < y + drift"),
 ("m16 pages_near drift 0 low", F, "ordered[low][1] < y - drift", "ordered[low][1] < y"),
 ("m17 B drift 0", F, "repeats = _pages_near([(number, y) for _, number, y in same], [y for *_, y in same], drift)", "repeats = _pages_near([(number, y) for _, number, y in same], [y for *_, y in same], 0.0)"),
 ("m18 B text key ignored", F, "texts[text].append", "texts[''].append"),
 ("m19 order total all", O, "total = _text(counted(elements))", "total = _text(elements)"),
 ("m20 order filled band", O, "_filled(mine, cuts, settings)", "_filled(band, cuts, settings)"),
 ("m21 order text band", O, "if _text(mine) >= settings.column_text", "if _text(band) >= settings.column_text"),
 ("m22 build any kind", B, "if block.kind is BlockKind.FIGURE for part", "for part"),
 ("m23 build no caption needed", B, "named = [doc.blocks[b.describes] for b in doc.blocks if b.describes is not None]", "named = list(doc.blocks)"),
 ("m24 shapes small only drift", F, "drift = settings.head_drift * size\n    found: set[str] = set()", "drift = 0.0\n    found: set[str] = set()"),
 ("m25 furniture loose small", F, "loose = line_size(line) < settings.small * self.size or line.id in self.apart", "loose = line.id in self.apart"),
]
tests = ["tests/unit/test_layout.py","tests/unit/test_layout_corpus.py","tests/unit/test_corpus_truth.py","tests/unit/test_layout_contents_labels.py","tests/unit/test_layout_tagged.py","tests/unit/test_layout_graphics.py","tests/unit/test_layout_code.py","tests/unit/test_textprep_furniture.py"]
sel = sys.argv[1:] 
for name, f, old, new in M:
    if sel and name.split()[0] not in sel: continue
    p = R / f; src = p.read_text()
    n = src.count(old)
    if n != 1: print(name, "PATTERN COUNT", n); continue
    p.write_text(src.replace(old, new))
    import shutil; shutil.rmtree(R/"src/sci2audio/layout/__pycache__", ignore_errors=True)
    try:
        r = subprocess.run([str(R/".venv/bin/python"),"-m","pytest","-q","-x","-n","4","-p","no:cacheprovider",*tests], cwd=R, capture_output=True, text=True, timeout=900, env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
        last = [l for l in r.stdout.splitlines() if l.strip()][-1]
        fails = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        print(name, "KILLED" if r.returncode else "SURVIVED", "|", last[:100], "|", fails[:1])
    finally:
        p.write_text(src)
        shutil.rmtree(R/"src/sci2audio/layout/__pycache__", ignore_errors=True)
