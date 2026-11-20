"""Dump the utterances of every corpus source, first run and second run, with default settings,
with "Tables and figures" off, and with it and "Formulas" off. Usage: corpus_utts.py OUTFILE"""
import sys, tempfile
from pathlib import Path
from sci2audio.app import JobSettings, run_script_job
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, cut_utterances
from sci2audio.testing.regression import said
from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category
VARIANTS = {'default': DEFAULT_SWITCHED_OFF, 'figures-off': DEFAULT_SWITCHED_OFF | {Category.TABLES_AND_FIGURES}, 'figures-formulas-off': DEFAULT_SWITCHED_OFF | {Category.TABLES_AND_FIGURES, Category.FORMULAS}}
C = Path("tests/corpus")
srcs = sorted(C.glob("papers/*.pdf")) + sorted(C.glob("text/*.txt")) + sorted(C.glob("markdown/*.md")) + sorted(C.glob("epub/*.epub"))
out = open(sys.argv[1], "w")
for src in srcs:
  for name, off in VARIANTS.items():
    with tempfile.TemporaryDirectory() as d:
        job = run_script_job(src, JobSettings(output_folder=Path(d), switched_off=off), Path(d) / "work")
        for u in job.result.utterances:
            out.write(f"{src.stem}\t{name}\t1\t{int(u.continues)}\t{u.text}\n")
        doc = job.result.run.document
        ctx = StepContext(doc.language, switched_off=off)
        r2 = run_steps(rebuilt_from_script(doc, job.result.run.script()), ctx, switched_off=off)
        for u in cut_utterances(r2.document, r2.script()):
            out.write(f"{src.stem}\t{name}\t2\t{int(u.continues)}\t{u.text}\n")
    print(src.stem, name, flush=True)
