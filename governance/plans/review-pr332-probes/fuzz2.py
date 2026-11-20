import itertools
from probe import read_all
leads = ["Vom ", "Am ", "bis ", "Seit ", "ab dem ", "Kapitel ", ""]
d1 = ["3.4.", "3.4.2019", "3.", "03.04.", "29.2."]
dashes = ["-", "–", "—", " – ", "-\n"]
d2 = ["5.4.", "5.4.2019", "5.", "31.4.", "5.4.19"]
mid = ["", "-7.4.", "–7.4.2019"]
tails = [" lief es.", " 1/2 Tag.", " 1/12 Liter.", " 3 Tage.", " 2/3 Tag.", "-Woche.", ".", " 12.03.2019 an.", ", 2019.", " 1/3.", "1/2", " ½ Tag."]
for parts in itertools.product(leads, d1, dashes, d2, mid, tails):
    t = "".join(parts)
    one = read_all(t, "de"); two = read_all(one, "de")
    if one != two:
        print(repr(t), "->", repr(one), "RUN2", repr(two))
