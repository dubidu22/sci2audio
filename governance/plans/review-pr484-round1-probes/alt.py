from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps
cases = [
 ("en", "https://x.org"), ("en", "see https://x.org"), ("en", "(Smith, 2019)"), ("en", "[3]"),
 ("en", "Bars show the mean; e.g. 3.5 % at 12 m² (Smith et al., 2019)."),
 ("en", "Fig. 3 of Smith (2019)"), ("en", "x"), ("en", "Loss vs. epochs, cf. Table 2"),
 ("de", "Anteil z. B. 3,5 % (Müller 2019, S. 4)"), ("de", "vgl. https://x.org"), ("de", "Abb. 2 aus [4]"),
 ("de", "Heydorn (1974/2004) zeigt das"), ("en", "Mean ± SD of 12 runs; p < .05"),
]
for lang, alt in cases:
    doc = make_document([(BlockKind.FIGURE, ""), (BlockKind.PARAGRAPH, "Next.")], lang, pictures={0: [alt]})
    ctx = StepContext(lang)
    first = run_steps(doc, ctx, strict=True)
    a = " | ".join(p.text for p in first.script() if p.span.block == 0)
    second = run_steps(rebuilt_from_script(doc, first.script()), ctx, strict=True)
    b = " | ".join(p.text for p in second.script() if p.span.block == 0)
    print(f"{lang} {alt!r}\n   -> {a!r}" + ("" if a == b else f"\n   2nd {b!r}"))
