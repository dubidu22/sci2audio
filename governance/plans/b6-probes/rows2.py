from pathlib import Path
from sci2audio.testing.regression import load_cases, run_case, said
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, notice_read
for f in ["english.toml", "german.toml"]:
    n = bad = 0
    for case in load_cases(Path("tests/regression") / f):
        if case.utterances is None: continue
        n += 1
        context = StepContext(case.document.language, switched_off=case.switched_off)
        first = run_case(case)
        read = [i for i, b in enumerate(case.document.blocks) if b.is_placeholder and not notice_read(b, context)]
        second = run_steps(rebuilt_from_script(case.document, first.script(), own_output=read), context, switched_off=case.switched_off, strict=True)
        a, b = said(first), said(second)
        if a != b:
            bad += 1
            print(f, case.id, "\n   1:", a, "\n   2:", b)
    print(f, n, "rows with utterances,", bad, "cut differently on run 2")
