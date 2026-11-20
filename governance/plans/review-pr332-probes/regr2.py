import sys
from pathlib import Path
from sci2audio.testing import rebuilt_from_script
from sci2audio.testing.regression import load_cases
from sci2audio.textprep import StepContext, run_steps, spoken_text
root = Path(sys.argv[1])
for f in ("english.toml", "german.toml"):
    for case in load_cases(root / "tests/regression" / f):
        ctx = StepContext(case.document.language)
        s1 = run_steps(case.document, ctx, strict=True).script()
        d2 = rebuilt_from_script(case.document, s1)
        s2 = run_steps(d2, ctx, strict=True).script()
        a, b = spoken_text(s1), spoken_text(s2)
        if a != b:
            print(f"{f}:{case.id}: {a!r}\n    RUN2 {b!r}")
