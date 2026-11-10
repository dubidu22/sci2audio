# sci2audio

**Turn scientific papers and books into faithful audiobooks, offline, with free local voices.**

> **Pre-release: not ready for use yet.** The code is being moved in from an earlier private version, one reviewed step at a time. Follow the [v1.0 milestone](https://github.com/dubidu22/sci2audio/milestones) for progress.

## What it will do

- Read PDF, EPUB, Markdown and plain text.
- Prepare the text for listening with transparent rules: remove page headers, hyphenation, citations and URLs; read units, statistics and abbreviations properly; skip formulas and tables with a short spoken notice.
- Speak it with local Kokoro voices (English first, German later).
- Export MP3 and M4B with chapters, and show a read-along view that highlights the original text.

## Principles

- **Your files stay on your computer.** No account, no upload, no telemetry. The only network access is the download of a voice you choose.
- **Faithful, not rewritten.** Every change to the text is a marked, explainable rule; nothing is summarised.
- **Free and open source** under the GNU GPL v3 or later.
- **Accessible:** the interface is built to work with screen readers and the keyboard.

## Development

You need [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                       # install the project and development tools
uv run pytest -m "not slow"   # fast tests
uv run ruff check             # lint
uv run lint-imports           # layer rules
uv run pre-commit install     # run checks before every commit
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how work is planned and reviewed.

## Licence

GPL-3.0-or-later, see [LICENSE](LICENSE). Third-party components and their licences are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Audio made with sci2audio is labelled as AI-generated in its metadata.

Only convert texts you are allowed to use. sci2audio does not remove copy protection.
