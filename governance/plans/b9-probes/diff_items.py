"""Differential check for the #621 Windows fix (an item of a nest holds no bracket): reads
random nest texts with two source trees and counts differences, both runs.
Usage: diff_items.py OLD_SRC NEW_SRC SEED COUNT (runs each tree in a child process)"""
import json, random, subprocess, sys
if sys.argv[1] == "--read":
    sys.path.insert(0, sys.argv[2])
    from sci2audio.core import BlockKind
    from sci2audio.testing import make_document, rebuilt_from_script
    from sci2audio.textprep import StepContext, run_steps, spoken_text
    out = []
    for lang, text in json.loads(sys.stdin.read()):
        doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
        s1 = run_steps(doc, StepContext(lang)).script()
        s2 = run_steps(rebuilt_from_script(doc, s1), StepContext(lang)).script()
        out.append([spoken_text(s1), spoken_text(s2)])
    print(json.dumps(out)); sys.exit()
old, new, seed, count = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
rng = random.Random(seed)
POOL = ["(", ")", "((", "))", "(see ", "(e.g. ", "(vgl. ", "(Smith, 2019)", "(Lee, 2018)", "(Müller, 2019)", "Jones, 2020",
        "; ", ", ", "; and ", " und ", " 2020)", " (2019))", "((Smith, 2019) 2020)", "(Kim, 2017; Lee, 2018)",
        " is cited.", " wird zitiert.", "Text ", " here.", "[1]", "https://x.org", "foo "]
texts = []
for _ in range(count):
    lang = rng.choice(["en", "de"])
    texts.append([lang, "".join(rng.choice(POOL) for _ in range(rng.randint(2, 12)))])
def read(src):
    r = subprocess.run([sys.executable, __file__, "--read", src], input=json.dumps(texts), capture_output=True, text=True)
    return json.loads(r.stdout)
a, b = read(old), read(new)
diff = [(t, x, y) for t, x, y in zip(texts, a, b) if x != y]
print(f"seed {seed}: {len(diff)} of {count} texts read differently")
for d in diff[:8]:
    print("  ", d)
