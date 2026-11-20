"""Compare sci2audio's English rules with Kokoro's English front end (misaki + spaCy) on one text.

Run from the root of the sci2audio repository, in an environment with sci2audio's dependencies,
spaCy, en_core_web_sm and misaki installed:

    pip install spacy misaki num2words wordfreq && python -m spacy download en_core_web_sm
    python docs/kb/02-product-and-pipeline/tools/english_check/compare.py [sample_en.md]

Prints: sci2audio's spoken script, its findings, spaCy's sentences/entities/homograph tags, and
misaki's phonemes with unknown words shown as ⟨word⟩ (Kokoro would send those to espeak-ng).
Used for audit-english-rules-vs-spacy-2026-11-09.md.
"""
import sys
from pathlib import Path

sample = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sample_en.md")
text = sample.read_text(encoding="utf-8")

sys.path.insert(0, ".")
from sci2audio.analysis import analyse, apply_fixes  # noqa: E402
from sci2audio.normalizer import rule_based_script  # noqa: E402

report = analyse(text, "en")
script = rule_based_script(apply_fixes(report.text, report)[0], lang="en")
print("=== sci2audio script\n" + script)
print("\n=== sci2audio findings")
for f in report.findings:
    d = f.__dict__
    span = text[d["start"]:d["end"]] if "start" in d else ""
    print(f"  {d['action'].value:12} {span[:60]!r}")

import spacy  # noqa: E402

doc = spacy.load("en_core_web_sm")(text)
print("\n=== spaCy sentences")
for i, s in enumerate(doc.sents):
    print(f"  {i:2} {s.text[:90]!r}")
print("\n=== spaCy entities")
for e in doc.ents:
    print(f"  {e.label_:12} {e.text!r}")
print("\n=== spaCy homograph tags")
for t in doc:
    if t.lower_ in {"read", "record", "wound", "lead", "live", "present", "tear", "close"}:
        print(f"  {t.text:8} {t.tag_}")

from misaki import en  # noqa: E402

g2p = en.G2P(trf=False, british=False, fallback=lambda t: ("⟨" + t.text + "⟩", 1))
print("\n=== misaki phonemes (⟨…⟩ = unknown, espeak-ng fallback in Kokoro)")
for para in [p for p in text.split("\n\n") if p.strip()]:
    print("  " + g2p(para)[0])
