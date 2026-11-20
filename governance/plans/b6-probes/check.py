import sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.testing.regression import said, render
from sci2audio.textprep import StepContext, run_steps
lang, text = sys.argv[1], sys.argv[2]
doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
ctx = StepContext(lang)
r1 = run_steps(doc, ctx, strict=True)
r2 = run_steps(rebuilt_from_script(doc, r1.script()), ctx, strict=True)
print(len(text)); print(render(r1)); print(said(r1)); print(said(r2)); print("SAME" if said(r1)==said(r2) else "DIFFER")
