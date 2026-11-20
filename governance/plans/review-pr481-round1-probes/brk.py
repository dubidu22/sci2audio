import sys
sys.path.insert(0, "tests/unit")
from test_textprep_utterances import cut_read
en = "the listeners heard every part of the recording in the quiet room and "
de = "die Hörer hörten jeden Teil der Aufnahme im stillen Raum und "
cases = [
 ("en paren-comma", "en", "We " + en * 2 + "(as we saw in the first study, which " + en + "of the long run) " + en * 2 + "it ended."),
 ("en paren-spaces", "en", "We " + en * 3 + "(as the first and the second experiment of the long study showed) " + en * 2 + "it ended."),
 ("en quote-comma", "en", "We " + en * 2 + "“we hear, what we read, and we read " + en + "what we hear” " + en * 2 + "it ended."),
 ("de quote-comma", "de", "Wir " + de * 3 + "„Wir hören, was wir lesen, und wir lesen " + de + "was wir hören“ " + de * 2 + "und es endete."),
 ("de paren-comma", "de", "Wir " + de * 3 + "(wie die erste Studie, die " + de + "zeigte) " + de * 3 + "und es endete."),
 ("de guillemets", "de", "Wir " + de * 3 + "»Wir hören, was wir lesen, und wir lesen " + de + "was wir hören« " + de * 2 + "und es endete."),
 ("all inside", "en", "We said (" + en * 6 + "and so on) then."),
]
for name, lang, t in cases:
    parts = cut_read(t, lang)
    print(f"## {name}:", " ## ".join(p[-28:] + " || " + q[:28] for p, q in zip(parts, parts[1:])))
