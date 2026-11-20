"""PR B (#474) round 1 mutants (the reviewer's survivors, rebuilt by the author). Usage from
the repo root: python3 round1.py NAME; restore with git checkout."""
import sys

M = "src/sci2audio/web/markers.py"
A = "src/sci2audio/web/api.py"
MUTANTS = {
    "R3": (M, "best = min(starts, key=lambda s: abs(where[s] - anchor.start))", "best = starts[0]"),
    "R3b": (M, "best = min(starts, key=lambda s: abs(where[s] - anchor.start))", "best = starts[-1]"),
    "R5": (M, "low = max(0, min(anchor.block, len(self.texts)) - NEAR_BLOCKS)\n        high = min(len(self.texts), anchor.block + NEAR_BLOCKS + 1)",
           "low = max(0, min(anchor.block, len(self.texts)) - 1)\n        high = min(len(self.texts), anchor.block + 1 + 1)"),
    "R6b": (M, "block = max(shares, key=lambda b: (len(shares[b]), -b))", "block = max(shares, key=lambda b: (len(shares[b]), b))"),
    "R6c": (M, "block = max(shares, key=lambda b: (len(shares[b]), -b))", "block = max(shares)"),
    "R7": (M, "            if overlap > most:", "            if overlap >= most and overlap > 0:"),
    "R9": (M, "            if out and out[-1] != \" \":", "            if True:"),
    "R10": (M, "        if char == \"­\":\n            at += 1\n            continue\n", ""),
    "S2": (A, "        if span is None or span.start >= span.end:", "        if span is None:"),
    "S3": (A, "        book.document.check_span(span)\n", "        pass\n"),
    "U5": (M, "self._clock() - entry[1] > UNDO_SECONDS", "self._clock() - entry[1] >= UNDO_SECONDS"),
    "L3": (M, "if not isinstance(entries, list) or len(entries) > MAX_MARKERS:", "if not isinstance(entries, list):"),
}
name = sys.argv[1]
path, old, new = MUTANTS[name]
text = open(path, encoding="utf-8").read()
assert text.count(old) == 1, (name, old)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
