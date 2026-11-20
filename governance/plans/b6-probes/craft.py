"""Find a long sentence (own words, no comma) whose run-2 cut falls inside a reading on main."""
import itertools, sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.testing.regression import said
from sci2audio.textprep import StepContext, run_steps
lang = sys.argv[1]
if lang == "de":
    head = "Die Hörerinnen und Hörer der langen Aufnahme bewerteten in der zweiten Runde der Studie"
    pads = ["sehr", "ruhig", "und", "genau", "jede", "einzelne", "Stelle", "der", "Lesung"]
    mid = "die Pausen u. a. nach jedem Absatz und den Anteil von 3,5 % der Sätze"
    tail = "als zu lang für ein ruhiges Hören am Abend in einem stillen Raum ohne jede Ablenkung durch Musik oder Gespräche im Hintergrund der Wohnung."
else:
    head = "The listeners of the long recording rated in the second round of the study"
    pads = ["very", "calmly", "and", "carefully", "every", "single", "part", "of", "the", "reading"]
    mid = "the pauses e.g. after each paragraph and the share x ≤ 5 of the sentences"
    tail = "as too long for calm listening in the evening in a quiet room without any distraction by music or talk in the background of the flat."
for n in range(0, 40):
    for m in range(0, 30):
        words = (pads * 8)[:n]
        words2 = (pads * 8)[:m]
        text = " ".join([head, *words, mid, *words2, tail])
        doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
        ctx = StepContext(lang)
        r1 = run_steps(doc, ctx, strict=True)
        r2 = run_steps(rebuilt_from_script(doc, r1.script()), ctx, strict=True)
        a, b = said(r1), said(r2)
        if a != b:
            print(n, m, len(text)); print(text); print(a); print(b); sys.exit()
print("none")
