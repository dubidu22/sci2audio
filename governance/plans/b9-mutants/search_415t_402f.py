"""Counterexample search for mutants 415-t (`_keeps_text` as `bool(found)`) and 402-f
(`_join_before` without its "punctuation follows the link" return): counts how often each
guard decides anything on random texts of nests, lead words, lists, names, join words and
links, en and de, both runs. Usage: search_415t_402f.py SEED COUNT"""
import random, re, sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps
from sci2audio.textprep import citations, links
seed, count = int(sys.argv[1]), int(sys.argv[2]); rng = random.Random(seed)
t_hits, f_hits, f_calls, t_calls = [], [], 0, 0
real_keeps = citations._keeps_text
def keeps(found, node):
    global t_calls
    t_calls += 1
    if bool(found) != real_keeps(found, node):
        t_hits.append(found)
    return real_keeps(found, node)
citations._keeps_text = keeps
real_before = links._join_before
def before(text, start, end, claimed, words):
    global f_calls
    f_calls += 1
    if end < len(text) and text[end] in ".,;:!?)]":
        joins = [w for w in words.joins if w.isalpha()]
        listed = "|".join(re.escape(w) for w in sorted(joins, key=len, reverse=True))
        window = max(claimed, start - links._LOOK_BACK)
        left = re.search(rf"(?<!\S)([^\W\d_][\w’'-]*)(\s*,)?\s+({listed})\Z", text[window:start], re.IGNORECASE)
        if left and left.group(1)[0].isupper() and not links._starts_sentence(text, window + left.start(1), -1, words.abbreviations):
            f_hits.append(text)
    return real_before(text, start, end, claimed, words)
links._join_before = before
POOL = ["(", ")", "(see ", "(e.g. ", "(cf. ", "(vgl. ", "(Smith, 2019)", "(Lee, 2018)", "(Müller, 2019)", "Smith", "Lee",
        "Müller", " and ", " und ", " or ", ", ", "; ", "https://x.org", "https://a.org/b", " is cited", " wird zitiert",
        "Text", "here", ". ", ".", "2020", "[1]", "[2]", "It holds", "We thank", "(527794)", ")", ",", ":", "!"]
for n in range(count):
    lang = rng.choice(["en", "de"])
    text = "".join(rng.choice(POOL) + rng.choice(["", " "]) for _ in range(rng.randint(3, 16)))
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    s1 = run_steps(doc, StepContext(lang)).script()
    run_steps(rebuilt_from_script(doc, s1), StepContext(lang))
print(f"seed {seed}: 415-t guard differed {len(t_hits)} times in {t_calls} calls; "
      f"402-f guard decided {len(f_hits)} times in {f_calls} calls; {count} texts")
for h in (t_hits[:3] + f_hits[:3]):
    print("  ", h)
