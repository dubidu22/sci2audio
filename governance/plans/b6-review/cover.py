"""Which multi-word replacements (run 1) have an internal space that _joined does not rank 5?"""
import sys, collections, tempfile
from pathlib import Path
sys.path.insert(0, "tests/unit")
from sci2audio.testing.regression import load_cases, run_case
from sci2audio.textprep.utterances import _joined, _readings
miss = collections.Counter(); total = collections.Counter()
def check(run, lang, src):
    doc = run.document
    for p in run.script():
        if p.pause or not p.text.strip(): continue
        orig = doc.blocks[p.span.block].text[p.span.start:p.span.end]
        if p.text == orig or " " not in p.text.strip(): continue
        t = "lorem " + p.text.strip() + " ipsum"
        j = _joined(t, len(t) - 1, _readings(lang))
        inner = [k for k in range(7, 6 + len(p.text.strip())) if t[k-1].isspace() and not t[k].isspace()]
        total[lang] += 1
        if any(k not in j for k in inner):
            miss[(lang, orig[:40], p.text.strip()[:60])] += 1
for f in ("english", "german"):
    for case in load_cases(Path(f"tests/regression/{f}.toml")):
        try: check(run_case(case), case.document.language.split("-")[0], case.id)
        except Exception as e: print("ERR", case.id, e)
if len(sys.argv) > 1:
    from sci2audio.app import JobSettings, run_script_job
    C = Path("tests/corpus")
    for src in sorted(C.glob("papers/*.pdf")) + sorted(C.glob("text/*.txt")) + sorted(C.glob("markdown/*.md")) + sorted(C.glob("epub/*.epub")):
        with tempfile.TemporaryDirectory() as d:
            job = run_script_job(src, JobSettings(output_folder=Path(d)), Path(d) / "work")
            check(job.result.run, job.result.run.document.language.split("-")[0], src.stem)
        print(src.stem, flush=True, file=sys.stderr)
print("multi-word replacements:", dict(total), "with an unranked inner space:", sum(miss.values()))
for (lang, o, r), n in miss.most_common(80): print(f"{n:4d} {lang} {o!r} -> {r!r}")
