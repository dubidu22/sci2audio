"""Like fuzz2, but a pool with more readings and fewer commas, so spaces are cut more often.
Usage: fuzz3.py SEED N [punct]"""
import random, sys
from sci2audio.core import BlockKind
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.testing.regression import said
from sci2audio.textprep import StepContext, run_steps
from sci2audio.testing import make_document
rng = random.Random(int(sys.argv[1]))
POOL = {
 "de": ["die Hörer", "hörten", "jeden Teil", "der Aufnahme", "im stillen Raum", "z. B.", "3,5 %", "Abb. 2", "und", "dass", "weil", "d. h.", "i. V. m.", "e. V.", "ca. 20 min", "Nr. 5", "oder", "die", "wie", "am 3. Mai 2019", "u. a.", "aber", "5 km/h", "10 mg/kg", "um 13:30 Uhr", "im Jahr 1998", "p < 0,05", "10⁻³", "2 bis 3", "x ≤ 5", "S. 12 f.", "usw. und", "2,5 m²", "vgl. Kap. 3", "o. Ä.", "bzw.", "1.234 Fälle", "Mio. Euro", "−5 °C", "um 10 Uhr"],
 "en": ["the listeners", "heard", "every part", "of the recording", "in the quiet room", "e.g.", "3.5 %", "Fig. 2", "and", "which", "because", "i.e.", "approx. 20 min", "No. 5", "or", "that", "while", "on 3 May 2019", "et al.", "but", "5 km/h", "10 mg/kg", "at 13:30", "in 1998", "p < .05", "10⁻³", "2 to 3", "x ≤ 5", "cf. Sec. 3", "vs.", "1,234 cases", "−5 °C", "2.5 m²", "w.r.t.", "s.t.", "±2", "≥ 3"],
}
punct = len(sys.argv) > 3
bad = 0; cuts = 0
for lang in ("en", "de"):
    for n in range(int(sys.argv[2])):
        words = [rng.choice(POOL[lang] + ([",", ";", "–"] if punct else [])) for _ in range(rng.randint(40, 140))]
        text = ("Wir " if lang == "de" else "We ") + " ".join(words).replace(" ,", ",").replace(" ;", ";") + "."
        doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
        ctx = StepContext(lang)
        first = run_steps(doc, ctx, strict=True)
        second = run_steps(rebuilt_from_script(doc, first.script()), ctx, strict=True)
        a, b = said(first), said(second); cuts += len(a) - 1
        if a != b:
            bad += 1
            if bad <= 6:
                for x, y in zip(a, b):
                    if x != y: print(f"  {lang} #{n}: 1: ...{x[-60:]}\n          2: ...{y[-60:]}"); break
print("differ:", bad, "of", 2 * int(sys.argv[2]), "cuts:", cuts)
