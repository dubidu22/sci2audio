"""A step that edits inside a placeholder because of a neighbouring paragraph it also edits:
non-idempotent on a second run, caught on main by the main idempotence check?"""
from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.testing import text_step_problems
from sci2audio.textprep import Category, Stage, StepContext, TextStep

class Neighbour(TextStep):
    id = "neighbour"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE
    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        flagged = any("loss" in b.text and not b.is_placeholder for b in document.blocks)
        for index, block in enumerate(document.blocks):
            if not block.is_placeholder and (at := block.text.find("loss")) >= 0:
                edits.append(Edit(Span(index, at, at + 4), EditKind.REMOVE, "r", self.id))
            elif flagged and block.is_placeholder and len(block.text) > 2:
                edits.append(Edit(Span(index, 0, 1), EditKind.REMOVE, "r", self.id))
        return edits

problems = text_step_problems(Neighbour())
print(len(problems))
for p in problems[:6]: print(" ", p[:200])
