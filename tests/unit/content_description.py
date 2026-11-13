"""A readable description of `Content` for golden files (D-317, D-349): source, metadata and
outline, then each page's items in stored order, every line in full with its runs' tags and
style, every picture with its path and alternative text. Shared by the EPUB, Markdown and
text golden files.
"""

from sci2audio.core import Content, TextLine


def describe(content: Content) -> str:
    """Source, metadata and outline, then each page's items in stored order."""
    meta = content.metadata
    source = content.source
    out = [f"{source.name}  sha256 {source.sha256[:16]}"]
    if source.encoding:  # text and Markdown only, so the EPUB golden file stays as it was
        out.append(
            f"encoding: {source.encoding}" + (" (guessed)" if source.encoding_guessed else "")
        )
    out.append(
        f"metadata: title={meta.title!r} authors={list(meta.authors)} date={meta.date!r}"
        f" identifier={meta.identifier!r} language={meta.language!r}"
    )
    out.append("outline:")
    out.extend(
        f"  {entry.level} p{entry.page} {entry.item or '-'} {entry.title!r}"
        for entry in content.outline
    )
    for page in content.pages:
        out.append(f"== page {page.number}  lines {len(page.lines)}  pictures {len(page.pictures)}")
        items = {item.id: item for item in (*page.lines, *page.pictures)}
        for item_id in page.order:
            item = items[item_id]
            if isinstance(item, TextLine):
                out.append(f"{item.id}  {_runs(item)}")
            else:
                out.append(f"{item.id}  picture ref={item.ref!r} alt={item.alt!r}")
    return "\n".join(out) + "\n"


def _runs(line: TextLine) -> str:
    parts = []
    for run in line.runs:
        style = " ".join(run.tags) + ("; b" if run.bold else "") + ("; i" if run.italic else "")
        parts.append(f"{{{style}}}{run.text}")
    return "".join(parts)
