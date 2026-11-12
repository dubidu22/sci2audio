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

## Installing (once released)

```bash
uv tool install sci2audio                      # macOS (Apple chips) and Windows
uv tool install sci2audio --torch-backend cpu  # Linux: 1.3 GB instead of 5.6 GB
```

On Linux the plain command also works; it installs the PyTorch build with NVIDIA GPU libraries. With pipx, use Python 3.12 (`pipx install --python python3.12 sci2audio`): the Kokoro packages do not yet declare support for newer Python versions. Intel Macs are not supported, because PyTorch no longer publishes builds for them.

The voice (about 355 MB: the Kokoro model, its English voices and a spaCy English model) is downloaded only when you start it, and its licences are shown first. After that, sci2audio works without a network.

## Development

You need [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                       # install the project and development tools
uv run pytest -m "not slow and not benchmark"   # fast tests
uv run ruff check             # lint
uv run lint-imports           # layer rules
uv run pre-commit install     # run checks before every commit
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how work is planned and reviewed.

## Licence

GPL-3.0-or-later, see [LICENSE](LICENSE). Third-party components and their licences are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Audio made with sci2audio is labelled as AI-generated in its metadata.

Only convert texts you are allowed to use. sci2audio does not remove copy protection.
