import sys
sys.path.insert(0, "tests/unit")
from test_textprep_utterances import cut_read
cases = [
 ("de", "Das galt (Wintersemester 2019/2020) für alle."),
 ("de", "Das galt (Haushaltsjahr 2019/2020) für alle."),
 ("de", "Das galt (Saison 1999/2000) für alle."),
 ("de", "Das galt (Sommer 2019) für alle."),
 ("de", "Das zeigen mehrere (Müller 2019, S. C. Weber 2020) Studien."),
 ("de", "Das zeigen mehrere (Müller 2019; S. L. Weber 2020) Studien."),
 ("de", "Das gilt (Müller 2019, S. 12/13) hier."),
 ("de", "Das galt (Schuljahr 2019/20) für alle."),
 ("de", "Die Quote (DAX 2019/2020) stieg."),
 ("de", "Das zeigt (BMBF 2019, S. 4) klar."),
 ("de", "Das zeigt (OECD 2019, S. 4) klar."),
 ("en", "This held (Fall 2019/2020) for all."),
 ("en", "This held (FY 2019/2020) for all."),
 ("en", "This held (fiscal year 2019/2020) for all."),
 ("en", "Values (Ratio 1/2 2019) were low."),
 ("en", "This held (Smith 2001, p. C) too."),
 ("en", "This held (Smith 2001, p. cl) too."),
]
for lang, t in cases:
    print(lang, "|", t, "->", " ".join(cut_read(t, lang)))
