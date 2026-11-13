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

On Linux the plain command also works; it installs the PyTorch build with NVIDIA GPU libraries. With pipx, use Python 3.12.16 or newer in the 3.12 series (`pipx install --python python3.12 sci2audio`): the Kokoro packages do not yet declare support for newer Python versions, and older 3.12 releases read some broken HTML and Markdown differently. Intel Macs are not supported, because PyTorch no longer publishes builds for them.

The voice (about 355 MB: the Kokoro model, its English voices and a spaCy English model) is downloaded only when you start it, and its licences are shown first. After that, sci2audio works without a network.

## Command line

```bash
sci2audio voices download            # once: shows the files, sizes and licences, then asks
sci2audio script paper.pdf           # the listening script and a report of every change
sci2audio convert paper.pdf          # the audiobook: M4B with chapters, MP3s, read-along file
```

`script` needs no voice and lists the chapters; choose them with `--chapters 1,3-5` (counted from 1, or `all`; by default every chapter but the reference list). Switch a kind of text handling off with `--off citations` (read as printed) or on with `--on footnote-texts` (leave the notes out); `sci2audio script --help` lists the categories. `convert` takes the same options and `--voice`, `--speed`, `--format both|m4b|mp3` and `--with-script`.

Files go next to the input file, or into the folder given with `-o`; existing files are replaced only with `--overwrite`. If `convert` is stopped (Ctrl-C, a crash, a closed laptop), run the same command again: the sentences already spoken are kept in a speech cache in your cache folder, and `sci2audio clean paper.pdf` removes it. The command line takes its defaults from the settings saved by the interface and never changes them; `--ignore-settings` uses the built-in defaults.

Exit codes, for scripts:

| Code | Meaning |
|---|---|
| 0 | done |
| 1 | failed for another reason (a write, the disk, ffmpeg, the voice, the download, or "no" to the download) |
| 2 | a bad option or value |
| 3 | the file does not exist or is not a file |
| 4 | a file type sci2audio can't read |
| 5 | the file is damaged, protected or can't be opened |
| 6 | the voice files are not installed (`sci2audio voices download`) |
| 7 | output files exist (add `--overwrite`) |
| 8 | another sci2audio job is working on this file |
| 130 | stopped with Ctrl-C |

## Development

You need a recent [uv](https://docs.astral.sh/uv/) (0.13.8 or newer; older ones do not know Python 3.12.16). `.python-version` pins Python 3.12.16, which uv downloads on the first `uv sync`; CI and the release workflow use the same uv-managed Python, never a runner's own (D-378).

```bash
uv sync                       # install the project and development tools
uv run pytest -m "not slow and not benchmark and not browser"   # fast tests
uv run pytest -m browser       # the interface in a browser (after `uv run playwright install chromium`)
uv run ruff check             # lint
uv run lint-imports           # layer rules
uv run pre-commit install     # run checks before every commit
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how work is planned and reviewed.

## Licence

GPL-3.0-or-later, see [LICENSE](LICENSE). Third-party components and their licences are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Audio made with sci2audio is labelled as AI-generated in its metadata.

Only convert texts you are allowed to use. sci2audio does not remove copy protection.
