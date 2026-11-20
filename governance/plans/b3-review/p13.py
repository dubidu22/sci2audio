from sci2audio.extraction.text import read_text
for t in ['She said “yes,”\nThen the second line runs on for quite a long while here.\n',
          'Er sagte: »Ja,«\nDann läuft die zweite Zeile noch eine ganze Weile weiter.\n',
          'EU\nThe second line runs on for quite a long while here, as prose does.\n']:
    print([l.runs[0].tags for l in read_text(t.encode(), "x.txt").pages[0].lines])
