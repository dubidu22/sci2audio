"""PR 6 mutants: (path under src/sci2audio, text, replacement); each text occurs once."""
P = "textprep/placeholders.py"
D = "testing/documents.py"
T = "testing/text_steps.py"
M = [
    # read_over
    (P, "        if span.end <= start or span.start >= end:\n            continue\n        if piece.text == printed",
        "        if span.end < start or span.start >= end:\n            continue\n        if piece.text == printed"),
    (P, "        if span.end <= start or span.start >= end:\n            continue\n        if piece.text == printed",
        "        if span.end <= start or span.start > end:\n            continue\n        if piece.text == printed"),
    (P, "read.append(printed[max(start, span.start) : min(end, span.end)])", "read.append(printed[span.start : span.end])"),
    (P, "        elif start <= span.start and span.end <= end:\n            read.append(piece.text)",
        "        elif start <= span.start or span.end <= end:\n            read.append(piece.text)"),
    (P, "        else:\n            return None\n    return \"\".join(read)", "        else:\n            continue\n    return \"\".join(read)"),
    # _read_in_place
    (P, "    if not wanted:\n        return []\n", "    if not wanted and False:\n        return []\n"),
    (P, "            if target not in described:\n", "            if True:\n"),
    (P, "            block = replace(block, describes=described[target])\n", ""),
    (P, "            order=tuple(item for item in page.order if item in used),\n", "            order=(),\n"),
    (P, "    content = replace(document.content, pages=pages, outline=())", "    content = replace(document.content, pages=pages)"),
    (P, "if step.stage is Stage.INLINE]", "if step.stage is not Stage.MOVE]"),
    (P, "run_steps(small, context, inline, context.switched_off)", "run_steps(small, context, inline)"),
    (P, "        own = [piece for piece in script if piece.span.block == position]", "        own = list(script)"),
    (P, "if start >= 0 else None", "if start > 0 else None"),
    (P, "read.append(\" \".join((reading or \"\").split()) or name)", "read.append((reading or \"\") or name)"),
    (P, "read.append(\" \".join((reading or \"\").split()) or name)", "read.append(\" \".join((reading or \"\").split()))"),
    (P, "read.append(\" \".join((reading or \"\").split()) or name)", "read.append(name)"),
    # find
    (P, "            if block.describes in ours and block.label\n", "            if block.describes is not None and block.label\n"),
    (P, "captions.setdefault(block.describes, []).append(wording.label(label))", "captions.setdefault(block.describes, []).append(label)"),
    (P, "            and index not in captions\n", ""),
    (P, "(Block(BlockKind.PARAGRAPH, wording.skipped([name], BlockKind.FORMULA)), name)", "(Block(BlockKind.PARAGRAPH, name), name)"),
    (P, "names = captions.get(index, []) or ([named[index]] if index in named else [])", "names = captions.get(index, []) or ([wording.formula.format(block.label)] if index in named else [])"),
    # rebuild as printed
    (D, "        if block.is_placeholder and index not in own_output:\n            # a notice", "        if False:\n            # a notice"),
    (D, "blocks.append(Block(block.kind, block.text, role=block.role, label=block.label))", "blocks.append(Block(block.kind, block.text, role=block.role))"),
    (D, "label = read_over(block.text, pieces, start, start + len(block.label))", "label = block.label"),
    # check on own output inside a placeholder (D-710, round 1)
    (D, "        if block.is_placeholder and index not in own_output:\n            # a notice", "        if block.is_placeholder:\n            # a notice"),
    (T, "            if (block := document.blocks[edit.span.block]).is_placeholder\n", "            if (block := document.blocks[edit.span.block]) is not None\n"),
    (T, "            and (edit.span.start, edit.span.end) != (0, len(block.text))\n        }", "        }"),
    (T, "    if not inside:\n        return []\n    own =", "    own ="),
    (T, "own_output=inside)", "own_output=())"),
    (T, "    if again is None or problems:\n        return [f\"inside a placeholder, on its own output", "    if False:\n        return [f\"inside a placeholder, on its own output"),
    (T, "        if before[index] != after[index]\n    ]", "        if before[index] == after[index]\n    ]"),
    (T, "    return problems + _inside_placeholder_problems(step, document, context, first, before)", "    return problems"),
    (T, "        after = _rendered(own, apply_edits(own, again))", "        after = _rendered(own, apply_edits(own, first))"),
    # round 2, S1: every placeholder compared
    (T, "        for index in inside\n        if before[index] != after[index]", "        for index in inside[:1]\n        if before[index] != after[index]"),
]
