"""Counterexamples for the surviving mutants of #476 (review probes, not shipped)."""
from test_layout import LEFT, RIGHT, content, line
from test_layout_paragraphs import PITCH, joined, lines, paragraphs
from sci2audio.core import TextLine, TextRun
from sci2audio.layout import build_document


def rows_at(spans, top=200.0, texts=None):
    texts = texts or ["The first line of the block.", "The second line ends here.",
                      "A third line starts anew", "and goes on to its end."]
    return [line(t, x0, top + PITCH * k, x1) for k, (t, (x0, x1)) in enumerate(zip(texts, spans))]


def test_m24_two_right_edges_are_no_flush_right_block():
    """Rows start at three places but end at two edges: the indented third row starts a paragraph."""
    above = lines("a", LEFT, RIGHT, 100, 3)
    block = rows_at([(LEFT, 450), (LEFT + 8, 450), (LEFT + 20, 400), (LEFT, 400)])
    assert paragraphs(build_document(content(above + block))) == [joined(above), joined(block[:2]), joined(block[2:])]


def test_m25_two_middles_are_no_centred_block():
    above = lines("a", LEFT, RIGHT, 100, 3)
    block = rows_at([(LEFT, 450), (LEFT + 10, 440), (LEFT + 30, 380), (LEFT, 410)])
    assert joined(block[2:]) in paragraphs(build_document(content(above + block)))


def test_m6_one_italic_word_leaves_a_centred_row_upright():
    middle = (LEFT + RIGHT) / 2
    def centred(runs, width, k):
        box_line = line("x", middle - width / 2, 100 + PITCH * k, middle + width / 2)
        return TextLine(box_line.id, tuple(TextRun(t, "Times", 10.0, italic=i) for t, i in runs), box_line.box)
    rows = [centred([("Department of Listening and Reading,", False)], 300, 0),
            centred([("for the ", False), ("Journal", True), (" of Sound, Town", False)], 220, 1),
            centred([("Example Country 12345", False)], 260, 2)]
    body = lines("z", LEFT, RIGHT, 100 + 3 * PITCH + 10, 3)
    assert paragraphs(build_document(content(rows + body))) == [joined(rows), joined(body)]


def test_m20_a_short_line_goes_on_with_e_g_and_i_e():
    for start in ("e.g. the ones on the shelf.", "i.e. the ones on the shelf."):
        rows = [line("Running text that fills its column from one edge to the other edge", LEFT, 100, RIGHT),
                line("we read the papers aloud", LEFT, 100 + PITCH, LEFT + 150),
                line(start, LEFT, 100 + 2 * PITCH, LEFT + 300)]
        assert paragraphs(build_document(content(rows))) == [joined(rows)], start
