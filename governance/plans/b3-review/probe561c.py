import textwrap, random
from sci2audio.extraction.text import read_text
words = ("Die Auswertung der Daten erfolgte mit einem Programm das wir selbst geschrieben haben "
         "und die Ergebnisse der Teilnehmer sind in der Tabelle zusammengefasst wobei die Studie "
         "von der Deutschen Forschungsgemeinschaft gefördert wurde und an drei Standorten lief").split()
url = "https://example.org/archiv/daten/2026/pilotstudie/hoeren/rohdaten/version-3/index.html"
rng = random.Random(7); splits = 0; total = 0; example = None
for trial in range(2000):
    ws = [rng.choice(words) for _ in range(rng.randint(30, 60))]
    ws.insert(rng.randint(5, len(ws)-5), url)
    text = textwrap.fill(" ".join(ws) + ".", rng.choice([60, 66, 72]), break_long_words=False)
    tags = [l.runs[0].tags for l in read_text(text.encode(), "x.txt").pages[0].lines]
    total += 1
    if tags[1:].count(("p",)):
        splits += 1; example = example or text
print(f"{splits}/{total} wrapped German paragraphs holding one URL are cut into two paragraphs")
print(example)
