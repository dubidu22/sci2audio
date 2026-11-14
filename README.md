# sci2audio

**Turn scientific papers and books into faithful audiobooks, offline, with free local voices.**

sci2audio reads a PDF, EPUB, Markdown or plain-text file in English, prepares its text for listening with rules you can check and switch off, speaks it with a local Kokoro voice, and writes an M4B audiobook with chapters, one MP3 per chapter, and a read-along view that highlights the original text as it is read. Everything runs on your own computer.

## What it does

- **Reads** PDF, EPUB, Markdown and plain text. It finds the reading order of one- and two-column pages, leaves out running heads, page numbers and sidebars, and finds headings, footnotes, captions, tables, figures and formulas. A scanned PDF needs a text layer: sci2audio has no text recognition yet.
- **Prepares the text** with transparent rules: it joins words hyphenated at a line end, leaves out citations, URLs and DOIs, reads units, statistics, numbers and abbreviations as words where the voice would get them wrong, and replaces formulas, tables and figures with a short spoken notice in the text's language (English or German). Footnotes are read where their mark stands. Every change is listed in a report with its reason, and each kind of change can be switched off.
- **Speaks** it with a local Kokoro voice: 28 English voices and the German voice Thorsten, at the speed you choose, with abbreviations it spells out (such as NLP) read at their own, slower pace if you like. An interrupted run picks up where it stopped.
- **Writes** an M4B with chapter marks and the cover, one MP3 per chapter, and a read-along file. The audio is labelled as AI-generated in its metadata.
- **Plays** it in a read-along view that shows the text as printed and highlights the sentence being read. Click any sentence to play from there.

## Principles

- **Your files stay on your computer.** No account, no upload, no telemetry. The only network access is the download of the voice, which you start yourself.
- **Faithful, not rewritten.** Every change to the text is a marked, explainable rule; nothing is summarised.
- **Free and open source** under the GNU GPL v3 or later.
- **Accessible:** the interface works with the keyboard alone and with screen readers, in English and German.

## What the rules do

A paragraph written for this README, as printed:

> Participants slept 7.5 h on average (Smith et al., 2020), and reaction times fell by 12 ms per hour of sleep (t(34) = 2.81, p < .01; 95% CI [4.1, 19.9]). Naps, e.g. after lunch, were not counted [3]. The data are available at https://example.org/sleep-data.

What sci2audio reads aloud (`sci2audio script`):

> Participants slept 7.5 hours on average, and reaction times fell by 12 milliseconds per hour of sleep (t of 34 equals 2.81, p less than .01; 95% confidence interval 4.1 to 19.9). Naps, for example after lunch, were not counted. The data are available.

The report next to the script lists all 13 changes, each with the text as printed, what is read instead and why. Three of its lines, without the page, chapter and step:

```text
“(Smith et al., 2020)” → left out. Reason: citation "(Smith et al., 2020)" is not read (TP-03).
“at https://example.org/sleep-data” → left out. Reason: URL "https://example.org/sleep-data" is not read; "at" before it goes too, so the sentence still reads (TP-07).
“ms” → read as “milliseconds”. Reason: "ms" read as "milliseconds".
```

Numbers such as "7.5" and ".01" stay as printed: the voice reads them well.

## Installing

sci2audio runs on macOS with Apple chips, Windows and Linux. Intel Macs are not supported, because PyTorch no longer publishes builds for them.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (0.13.8 or newer), a tool that installs Python programs together with the Python they need.
2. Install sci2audio:

   ```bash
   uv tool install sci2audio                      # macOS (Apple chips) and Windows
   uv tool install sci2audio --torch-backend cpu  # Linux: 1.3 GB instead of 5.6 GB
   ```

   On Linux the plain command also works; it installs the PyTorch build with NVIDIA GPU libraries.

   With pipx instead of uv, use Python 3.12.16 or newer in the 3.12 series (`pipx install --python python3.12 sci2audio`): the Kokoro packages do not yet declare support for newer Python versions, and older 3.12 releases read some broken HTML and Markdown differently.

3. Start it:

   ```bash
   sci2audio ui
   ```

   This opens the interface in your browser; it stays on this computer. The first time, it asks to download the voices (the Kokoro model, its English voices and a spaCy English model, about 355 MB; the German voice Thorsten by Thorsten-Voice, about 330 MB). It shows every file with its size and licence first and downloads only after you agree; `sci2audio voices download --language en` or `--language de` fetches one language only. A text is read by a voice of its own language: German texts by Thorsten, English texts by the chosen English voice. After that, sci2audio works without a network.

ffmpeg, which writes the MP3 and M4B files, comes with sci2audio (through the `imageio-ffmpeg` package). If that build is missing for your system, sci2audio uses an `ffmpeg` on your PATH.

To update: `uv tool upgrade sci2audio`. To remove: `uv tool uninstall sci2audio`, then delete the folders listed on the privacy page.

## Command line

```bash
sci2audio voices download            # once: shows the files, sizes and licences, then asks
sci2audio script paper.pdf           # the listening script and a report of every change
sci2audio convert paper.pdf          # the audiobook: M4B with chapters, MP3s, read-along file
```

`script` needs no voice and lists the chapters; choose them with `--chapters 1,3-5` (counted from 1, or `all`; by default every chapter but the reference list). Switch a kind of text handling off with `--off citations` (read as printed) or on with `--on footnote-texts` (leave the notes out); `sci2audio script --help` lists the categories. `convert` takes the same options and `--voice`, `--speed`, `--letter-pace normal|slower|slowest` (how fast spelled-out abbreviations such as NLP are read), `--format both|m4b|mp3` and `--with-script`.

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

## Privacy

sci2audio is a program on your computer, not an online service. Nobody receives your data, neither its makers nor anyone else.

- It sends nothing anywhere: no telemetry, no usage statistics, no crash reports, no update check, no account.
- It uses the network only for the voice download you start, after showing every file, its size and licence.
- The interface's server listens only on 127.0.0.1, with a key that is new for each start, and refuses requests from other web pages. The pages load nothing from the internet.
- Your files, their analysis, the speech cache, the settings and the voice stay in folders on your computer. The interface's privacy page (`/privacy`) names them and says how to remove them.

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

GPL-3.0-or-later, see [LICENSE](LICENSE). Third-party components and their licences are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Audio made with sci2audio is labelled as AI-generated in its metadata, and the player names the synthetic voice.

Only convert texts you are allowed to use. sci2audio does not remove copy protection.

## Problems and ideas

Please open an [issue](https://github.com/dubidu22/sci2audio/issues). For a text that is read wrongly, include the sentence as printed, what sci2audio read, and, if you can, the report line for it. The changes in each release are in [CHANGELOG.md](CHANGELOG.md).
