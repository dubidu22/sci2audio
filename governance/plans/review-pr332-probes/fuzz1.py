import sys
from probe import read_all
chars = [chr(c) for c in range(0x21, 0x7f)] + list("°±×÷·…–—‘’“”«»§¶†‡′″‰€£µΩαβγδΔΣπ≤≥≠≈∼∓⁺⁻⁰¹²³½¼→←↑↓∈∉⊂∩∪∞√∂∇∑∏∫‖⟨⟩")
for c in chars:
    for fmt in ("It is {c}−1/2 here.", "It is {c} −1/2 here.", "{c}−1/2"):
        t = fmt.format(c=c)
        one = read_all(t, "en"); two = read_all(one, "en")
        bad = []
        if one != two: bad.append("RUN2 " + repr(two))
        if "−" in one and ("half" in one or "out of" in one): bad.append("SIGN-UNREAD")
        if bad: print(repr(t), "->", repr(one), *bad)
