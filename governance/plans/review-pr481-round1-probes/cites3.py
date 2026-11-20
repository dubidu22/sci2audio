import sys
sys.path.insert(0, "tests/unit")
from test_textprep_utterances import cut_read
cases = [
 ("de", "Das galt im Jahr (2019/2020) für alle."),
 ("de", "Wie Müller (2019/2020) zeigt, gilt es."),
 ("de", "Der Anteil (1/2 2019) sank."),
 ("de", "Der Anteil (Hälfte 1/2) sank."),
 ("en", "The share (Smith 1/2) fell."),
 ("en", "This held (Fall 2019/2020) for all."),
 ("de", "Das galt (Wintersemester 2019/2020) für alle."),
 ("de", "Das galt (Wintersemester 2019/20) für alle."),
]
for lang, t in cases:
    print(lang, "|", t, "->", " ".join(cut_read(t, lang)))
