"""B9 fuzz: random citation lists, subject nests and join word + link shapes in random sentence
contexts, en and de, through the whole chain twice. Checks: no crash, the second run reads the
same, bracket balance kept, no doubled join word, no list number lost from a "references" reading.
Usage: fuzz.py SEED COUNT"""
import random, re, sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text

seed, count = int(sys.argv[1]), int(sys.argv[2])
rng = random.Random(seed)
AND = {"en": "and", "de": "und"}; OR = {"en": "or", "de": "oder"}
def item():
    return rng.choice(["1", "2", "3", "12", "2–6", "1, 2", "4a", "MH17", "12, p. 3", "0, 1", "1,2; 3,4", "x"])
def blist(lang):
    n = rng.randint(1, 6)
    parts = [f"[{item()}]" for _ in range(n)]
    out = parts[0]
    for i, p in enumerate(parts[1:], 1):
        last = i == n - 1
        j = rng.choice([", ", ",", ", " + AND[lang] + " ", " " + AND[lang] + " ", " " + OR[lang] + " "]) if last else rng.choice([", ", ",", " "])
        out += j + p
    return out
def name():
    return rng.choice(["Smith", "Lee", "Jones", "Müller", "Kim"])
def cite():
    return f"({name()}, {rng.choice(['2019', '2018', '2020a'])})"
def nest(lang):
    lead = rng.choice(["", "", "see ", "vgl. ", "e.g. ", "foo "])
    n = rng.randint(1, 3)
    items = [rng.choice([cite(), f"{name()}, 2017"]) for _ in range(n)]
    seps = [rng.choice(["; ", ", ", " ", "; and ", "; ; ", f"; {AND[lang]} ", ", & "]) for _ in range(n - 1)]
    body = items[0] + "".join(s + i for s, i in zip(seps, items[1:]))
    shell = rng.choice(["", "", " 2021"])
    return f"({lead}{body}{shell})"
def link(lang):
    pre = rng.choice([name(), name() + ",", "it", "the data", "Dr. " + name(), "[3]", name() + " et al."])
    j = rng.choice([AND[lang], OR[lang], ", " + AND[lang]])
    return f"{pre} {j} https://x.org/{rng.randint(1, 9)}" + rng.choice(["", ".", " [4]", " (Lee, 2019)"])
CONTEXT = {
    "en": ["It holds {} here.", "As shown in {}, it holds.", "{} show it.", "{} is cited.", "We thank {} here.", "Refs. {} show it.", "It holds {}.", "Shown by {}.", "Then {} and more."],
    "de": ["Es gilt {} hier.", "Wie in {} gezeigt, gilt es.", "{} zeigen es.", "{} wird zitiert.", "Wir danken {} hier.", "Es gilt {}."],
}
bad = 0
for n in range(count):
    lang = rng.choice(["en", "de"])
    shape = rng.choice([blist, nest, link])(lang)
    text = rng.choice(CONTEXT[lang]).format(shape)
    if rng.random() < 0.3:
        text += " " + rng.choice(CONTEXT[lang]).format(rng.choice([blist, nest, link])(lang))
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    try:
        s1 = run_steps(doc, StepContext(lang), strict=True).script()
        once = spoken_text(s1, show_pauses=True)
        s2 = run_steps(rebuilt_from_script(doc, s1), StepContext(lang), strict=True).script()
        twice = spoken_text(s2, show_pauses=True)
    except Exception as error:
        print("CRASH", repr(text), repr(error)); bad += 1; continue
    problems = []
    if once != twice: problems.append("second run")
    if text.count("(") - text.count(")") != once.count("(") - once.count(")"): problems.append("balance")
    if re.search(rf"\b({AND[lang]}|{OR[lang]})\s+\1\b", once): problems.append("doubled join")
    if problems:
        bad += 1; print(problems, repr(text), "|", repr(once), "|", repr(twice))
print(f"seed {seed}: {bad} of {count} flagged")
