from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps
for lang, alt in [("en", "(Smith, 2019)."), ("en", "https://x.org."), ("en", "See [3]."), ("de", "(Müller 2019)."), ("de", "https://x.org – (WBGU 2011, S. 1)"), ("en", "[3], [4]")]:
    doc = make_document([(BlockKind.FIGURE, "")], lang, pictures={0: [alt]})
    print(lang, repr(alt), "->", " ".join(p.text for p in run_steps(doc, StepContext(lang), strict=True).script()))
