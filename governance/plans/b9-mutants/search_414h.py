"""Counterexample search for mutant 414-h (the per-item `_not_citations` check in
`_bracket_lists` left out): random texts of brackets, joins, CI words, signs, label words and
percentages; whole chain, en and de; original vs mutant. Usage: search_414h.py SEED COUNT"""
import random, sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, spoken_text
from sci2audio.textprep import citations
seed, count = int(sys.argv[1]), int(sys.argv[2]); rng = random.Random(seed)
POOL = ["[1]", "[2]", "[1, 3]", "[2, 4]", "[0.1, 0.3]", "[12]", "[3–5]", ",", ", ", " and ", " und ", " or ", "CI", "CIs", "95% CI",
        "KI", "95 %-KI", "=", "∈", "≤", "Eq.", "Fig.", "Abb.", "5%", "x", "equals", "gleich", "less than", "kleiner als", "Table", "the", "It holds", "here", "."]
def build():
    return "".join(rng.choice(POOL) + rng.choice(["", " "]) for _ in range(rng.randint(3, 14)))
orig = citations._Rules._not_citations
def said(text, lang):
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    return spoken_text(run_steps(doc, StepContext(lang), strict=False).script())
src = open(citations.__file__, encoding="utf-8").read()
assert "                    or self._not_citations(text, ahead.open)\n" in src
found = 0
for n in range(count):
    lang = rng.choice(["en", "de"]); text = build()
    a = said(text, lang)
    # the mutant: `_bracket_lists` sees no item as an interval or label number
    real = citations._Rules._bracket_lists
    def mutant(self, text, roots, _real=real):
        saved = self._not_citations
        self._not_citations = lambda t, p: False
        try:
            return _real(self, text, roots)
        finally:
            del self._not_citations
    citations._Rules._bracket_lists = mutant
    try:
        b = said(text, lang)
    finally:
        citations._Rules._bracket_lists = real
    if a != b:
        found += 1; print(repr(text), lang, "|", a, "|", b)
print(f"seed {seed}: {found} of {count} differ")
