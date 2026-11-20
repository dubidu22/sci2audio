import sys

from sci2audio.testing.documents import make_document, rebuilt_from_script
from sci2audio.testing.regression import render, said
from sci2audio.textprep import StepContext, run_steps, cut_utterances
from sci2audio.core import Block
lang = sys.argv[1]
for text in sys.argv[2:]:
    doc = make_document([("paragraph", text)], language=lang) if True else None
    ctx = StepContext(lang)
    r1 = run_steps(doc, ctx, strict=True)
    r2 = run_steps(rebuilt_from_script(doc, r1.script()), ctx, strict=True)
    print(repr(text))
    print("  run1:", said(r1))
    print("  run2:", said(r2))
