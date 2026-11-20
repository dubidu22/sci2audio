import sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, cut_utterances
for t in ["Sie war die 2. die das schaffte.", "Er wurde der 3. der Saison.", "Es gilt Kap. 2. Kap. 3 gilt.", "Es gilt Abs. 2. Absatz 3 gilt.",
          "Siehe (Absatz 2. Absatz 3) dazu.", "Es gilt Abs. 2. abs. 3.", "Es gilt Rn. 12. Rn. 13 auch.", "Es gilt Az. 3. Az. 4 auch.",
          "Am Tag 3. Tag 4 kam er.", "Es gilt Abs.2. Abs. 3 gilt.", "Es gilt Randnummer 12. Randnummer 13 gilt.", "Es gilt Abs. 2.\nAbs. 3 gilt."]:
    d = make_document([(BlockKind.PARAGRAPH, t)], "de"); c = StepContext("de")
    f = run_steps(d, c, strict=True); s = run_steps(rebuilt_from_script(d, f.script()), c, strict=True)
    a = [u.text for u in cut_utterances(f.document, f.script())]; b = [u.text for u in cut_utterances(s.document, s.script())]
    print(t, "->", a, "" if a == b else f"RUN2 {b}")
