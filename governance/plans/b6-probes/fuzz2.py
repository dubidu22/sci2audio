"""Random long sentences (seed argv[1]): utterances on a first run and on a second run over its script."""
import random, sys
from sci2audio.core import BlockKind
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.testing.regression import said
from sci2audio.textprep import StepContext, run_steps
from sci2audio.testing import make_document
rng = random.Random(int(sys.argv[1]))
POOL = {
 "de": ["die Hörer", "hörten", "jeden Teil", "der Aufnahme,", "im stillen Raum", "z. B.", "3,5 %", "Abb. 2", "und", "dass", "weil", "„wir hören, was wir lesen“", "(siehe S. 12)", "e. V.", "ca. 20 min", "Nr. 5", "oder", "die", "wie", "am 3. Mai 2019", "–", "Heydorn (1974/2004, S. 273)", "u. a.", ";", "aber"],
 "en": ["the listeners", "heard", "every part", "of the recording,", "in the quiet room", "e.g.", "3.5 %", "Fig. 2", "and", "which", "because", "“we hear, what we read”", "(see p. 12)", "et al.", "approx. 20 min", "No. 5", "or", "that", "while", "on 3 May 2019", "–", "Smith (1890/1990, p. 5)", "i.e.", ";", "but"],
}
bad = 0; cuts = 0
for lang in ("en", "de"):
    for n in range(int(sys.argv[2]) if len(sys.argv) > 2 else 150):
        words = [rng.choice(POOL[lang]) for _ in range(rng.randint(40, 120))]
        text = ("Wir " if lang == "de" else "We ") + " ".join(words).replace(" ;", ";") + "."
        doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
        ctx = StepContext(lang)
        first = run_steps(doc, ctx, strict=True)
        second = run_steps(rebuilt_from_script(doc, first.script()), ctx, strict=True)
        a, b = said(first), said(second); cuts += len(a) - 1
        if a != b:
            bad += 1
            if bad <= 4:
                for x, y in zip(a, b):
                    if x != y: print(f"  {lang} #{n}: 1: ...{x[-50:]}\n          2: ...{y[-50:]}"); break
print("differ:", bad, "cuts:", cuts)
