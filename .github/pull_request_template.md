## Summary

<!-- The smallest view that makes the change clear: a diff sketch, call tree, file tree or Mermaid diagram, next to a line or two of text. Closes #. -->

## Evidence

- **Before:** <!-- failing test, output or screenshot -->
  **After:** <!-- passing test, output or screenshot -->
- [ ] `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src`
- [ ] `uv run pytest -m "not slow and not benchmark and not browser"`: <!-- e.g. 42 passed -->
- [ ] Interface changed? `uv run pytest -m browser`: <!-- e.g. 13 passed / not applicable -->
- [ ] Golden files changed? Diff explained: <!-- yes / no change -->

## Licences

<!-- New dependency, copied code, model, voice or sample text? Name it and its licence, or write "none". -->

## Merge Danger

**Door:** <!-- one-way or two-way: can a revert undo it? Deleting or overwriting user files, file formats, golden files and layer contracts are one-way. -->

**Blast Radius:** <!-- one word, then what could break; risk:high paths are listed in CLAUDE.md -->
