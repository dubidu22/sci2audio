import itertools
from probe import read_all
leads = ["Vom ", "Am ", "Kapitel ", ""]
d1 = ["3.4.2019", "3.4.", "03.04.2019", "29.2.2019", "29.2.2020"]
dashes = ["-", "–", "-\n"]
d2 = ["5.4.", "31.4.", "5.4.2019", "29.2."]
sp = [" ", "  ", "\n", ""]
fr = ["1/2", "1/3", "1/10", "1/11", "1/12", "1/20", "1/2-mal", "1/2,5", "1/2x", "1/2/2020", "1/1", "2/3", "12.03.2019", "3.4.", "1/2–1/3", "1 von 2", "ein halb"]
tails = [" Tag.", ".", ""]
for parts in itertools.product(leads, d1, dashes, d2, sp, fr, tails):
    t = "".join(parts)
    one = read_all(t, "de"); two = read_all(one, "de")
    if one != two:
        print(repr(t), "->", repr(one), "RUN2", repr(two))
