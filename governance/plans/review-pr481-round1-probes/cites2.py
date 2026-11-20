import sys
sys.path.insert(0, "tests/unit")
from test_textprep_utterances import cut_read
cases = [
 ("de", "Das galt (Wintersemester 2019) für alle."),
 ("de", "Das zeigen (Chen 2020, S. Li 2021) beide."),
 ("de", "Das zeigen (Chen 2020, S. Liv) beide."),
 ("de", "Das zeigt (Heydorn 1974/1975, S. 3) klar."),
 ("de", "Das zeigt (Heydorn/Koneffke 1973, S. 12) klar."),
 ("de", "Das gilt (und/oder 2019) hier."),
 ("de", "Das gilt (Ein/Aus 2019) hier."),
 ("de", "Das gilt (Preis/Leistung 2019) hier."),
 ("de", "Das zeigt (WBGU 2011, S. 1) klar."),
 ("de", "Das zeigt (EU 2016, S. 4) klar."),
 ("de", "Das zeigt (Lorenz 1974/2004, S. xv) klar."),
 ("en", "This holds (Input/Output 2019) here."),
 ("en", "This holds (Smith 2019, p. vi) here."),
]
for lang, t in cases:
    print(lang, "|", t, "->", " ".join(cut_read(t, lang)))
