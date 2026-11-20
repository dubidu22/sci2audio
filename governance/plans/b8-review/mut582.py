import subprocess, sys, shutil, os
from pathlib import Path
ROOT = Path("/home/user/probe/mut")
PY = "/home/user/sci2audio/.venv/bin/python"
F = "src/sci2audio/web/figures.py"; P = "src/sci2audio/extraction/pdf.py"; E = "src/sci2audio/extraction/epub.py"
WT = "tests/unit/test_web_figures.py"; XT = "tests/unit/test_extraction_figures.py"
M = [
 ("m1 drop id check", F, "if document.content.source.sha256[:16] != document_id:", "if False:", [WT]),
 ("m2 clean_path", E, "if not ref or clean_path(ref) != ref:", "if not ref:", [XT]),
 ("m3 no S_ISREG in read_cached", F, "if not stat.S_ISREG(info.st_mode) or info.st_size > FILE_LIMIT:", "if info.st_size > FILE_LIMIT:", [WT]),
 ("m4a no _real_folder in read_cached", F, "    figures = folder / CACHE_FOLDER\n    if not _real_folder(figures):\n        return None\n    path", "    figures = folder / CACHE_FOLDER\n    path", [WT]),
 ("m4b no _real_folder in write_cached", F, "        if not _real_folder(figures):\n            return False\n        with part", "        with part", [WT]),
 ("m5a write ignores unchanged", F, "if still is not None and still.folder == folder:", "if True:", [WT]),
 ("m5b no folder compare", F, "if still is not None and still.folder == folder:", "if still is not None:", [WT]),
 ("m6 parents=True", F, "figures.mkdir(exist_ok=True)", "figures.mkdir(exist_ok=True, parents=True)", [WT]),
 ("m7a prune newest first", F, "kept = sorted(_crops_in(figures), key=lambda entry: (entry[1], entry[0].name))", "kept = sorted(_crops_in(figures), key=lambda entry: (entry[1], entry[0].name), reverse=True)", [WT]),
 ("m7b never prune", F, "        if total <= limit:\n            return", "        return", [WT]),
 ("m8 MAX_IMAGES 5", F, "MAX_IMAGES = 4", "MAX_IMAGES = 5", [WT]),
 ("m8b pages by number", F, "for number, found in list(boxes.items())[:MAX_IMAGES]:", "for number, found in sorted(boxes.items())[:MAX_IMAGES]:", [WT]),
 ("m9 crop not flipped", P, "crop=(x0, height - y1, width - x1, y0)", "crop=(x0, y0, width - x1, height - y1)", [XT]),
 ("m10 limits not passed", P, '    "REGION_SIDE",\n    "REGION_PIXELS",\n', "", [XT]),
 ("m11 alt order", F, "_fold(p.alt) or caption or notice", "caption or _fold(p.alt) or notice", [WT]),
 ("m12 outside shows figures", "src/sci2audio/web/pages.py", "figures=not found.outside", "figures=True", [WT]),
 ("m14 F1 no epub lock", F, "            with self._lock(document_id):\n                picture = extract_epub_picture(source, shown.ref)", "            if True:\n                picture = extract_epub_picture(source, shown.ref)", [WT]),
 ("m15a F3 following reads", F, "if not is_kept(folder, cache_name(document_id, shown.region)):", "if read_cached(folder, cache_name(document_id, shown.region)) is None:", [WT]),
 ("m15b is_kept no S_ISREG", F, "return stat.S_ISREG(info.st_mode) and info.st_size <= FILE_LIMIT", "return info.st_size <= FILE_LIMIT", [WT]),
 ("m16 margin 0", F, "MARGIN = 4.0", "MARGIN = 0.0", [WT]),
 ("m17 batch off by one", F, "if len(found) >= BATCH - 1:", "if len(found) >= BATCH:", [WT]),
 ("m18 no 4pt clip on page", P, "        x0, y0 = max(box.x0, 0.0), max(box.y0, 0.0)\n        x1, y1 = min(box.x1, width), min(box.y1, height)", "        x0, y0, x1, y1 = box.x0, box.y0, box.x1, box.y1", [XT]),
 ("m19 caption ignored", F, "self.captions.setdefault(block.describes, text)", "pass", [WT]),
 ("m20 table epub shown", F, "if self.format is SourceFormat.EPUB and block.kind is not BlockKind.TABLE:", "if self.format is SourceFormat.EPUB:", [WT]),
 ("m21 code shows figures", "src/sci2audio/web/player.py", "if catalog is not None and view.notice and not view.code:", "if catalog is not None and view.notice:", [WT]),
]
def run(tests):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    first = next((l for l in r.stdout.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")), "")
    return r.returncode, first, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
code, _, tail = run([WT, XT])
print("baseline", code, tail, flush=True)
if code != 0: sys.exit(1)
for name, f, old, new, tests in M:
    path = ROOT / f; src = path.read_text()
    assert src.count(old) == 1, (name, src.count(old))
    path.write_text(src.replace(old, new))
    try:
        code, first, tail = run(tests)
    finally:
        path.write_text(src)
    print(("KILLED  " if code else "SURVIVED"), name, "|", first or tail, flush=True)
