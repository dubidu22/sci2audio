import itertools
from probe import read_all
leads = ["Am ", "Vom ", "bis ", "Kapitel ", "am ", "Seit dem ", ""]
d = ["3.4.", "31.4.", "29.2.", "03.04.", "3.4.-5.4.", "3.4.–5.4."]
sp = [" ", "  ", "\n", "", " – "]
fr = ["1/2", "1/3", "1/4", "1/10", "1/12", "1/20", "1/99", "2/3", "1/2-mal", "1/2,5", "1/2x", "1/2/2020", "1/1", "1/0", "11/2", "1/2–1/3", "1/2 %", "1/2."]
tails = [" Tag.", ".", " kg", " und mehr.", ""]
for parts in itertools.product(leads, d, sp, fr, tails):
    t = "".join(parts)
    one = read_all(t, "de"); two = read_all(one, "de")
    if one != two:
        print(repr(t), "->", repr(one), "RUN2", repr(two))
