"""Counterexample search for mutant 414-k (`_list` without its "a later bracket is decided
already" check): counts how often that check is true on random texts of bracket lists, nests,
links and identifiers, en and de, both runs. Usage: search_414k.py SEED COUNT"""
import random, sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps
from sci2audio.textprep import citations
seed, count = int(sys.argv[1]), int(sys.argv[2]); rng = random.Random(seed)
hits = []
real = citations._Rules._list
def watched(self, node):
    found = self._lists.get(node.open)
    if found is not None and any(item.open in self._numbered for item in found):
        hits.append(node.open)
    return real(self, node)
citations._Rules._list = watched
POOL = ["[1]", "[2]", "[3, 4]", "[MH17]", ", ", ",", " and ", " und ", " or ", "(", ")", "(see ", "(Smith, 2019)", "(527794)",
        "https://x.org", "Refs.", "in", "It holds", "here", ". ", "(2019)", "Lee", "[12, p. 3]", "CIs", "Eq.", "[0, 1]"]
for n in range(count):
    lang = rng.choice(["en", "de"])
    text = "".join(rng.choice(POOL) + rng.choice(["", " "]) for _ in range(rng.randint(3, 16)))
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    s1 = run_steps(doc, StepContext(lang)).script()
    run_steps(rebuilt_from_script(doc, s1), StepContext(lang))
print(f"seed {seed}: the check was true {len(hits)} times in {count} texts")
