import textwrap, random
from sci2audio.extraction.text import read_text
words = ("Die Auswertung der Daten erfolgte mit einem Programm das wir selbst geschrieben haben "
         "und die Ergebnisse sind in der Tabelle zusammengefasst wobei die Studie gefördert wurde").split()
rng = random.Random(11); hit = 0
for trial in range(2000):
    ws = [rng.choice(words) for _ in range(rng.randint(40, 80))]
    for _ in range(2):  # one dash pair " - ... - " per paragraph
        i = rng.randint(3, len(ws) - 6); ws[i:i] = ["-"]; ws[i+4:i+4] = ["-"]
    text = textwrap.fill(" ".join(ws) + ".", rng.choice([60, 66, 72]))
    tags = [l.runs[0].tags for l in read_text(text.encode(), "x.txt").pages[0].lines]
    hit += any(t[:2] == ("ul", "li") for t in tags)
print(f"{hit}/2000 wrapped German paragraphs with two spaced dash pairs get a list item mid-sentence")
