from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import Category, StepContext, run_steps
from sci2audio.textprep import DEFAULT_SWITCHED_OFF as D
T = {0: [(6, 8, ("span", "epub:pagebreak")), (14, 20, ("span", "hidden"))]}
for lang in ("en", "de", "fr"):
    for kind, cat in ((BlockKind.TABLE, Category.TABLES_AND_FIGURES), (BlockKind.FORMULA, Category.FORMULAS), (BlockKind.CODE, Category.CODE), (BlockKind.FIGURE, Category.TABLES_AND_FIGURES)):
        for off in (D, D | {cat}):
            doc = make_document([(kind, "Group 13 Mean SECRET 4.2")], lang, tags=T)
            s = " ".join(p.text for p in run_steps(doc, StepContext(lang), switched_off=off, strict=False).script())
            print(lang, kind.value, "off" if cat in off else "on ", "->", s)
