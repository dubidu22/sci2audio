# Plan: page progress while a PDF is read (#343) and cancel that stops the reader (#344)

Lane: app. Branch `app/pdf-progress-cancel` from main 87c6503. **Not critical:**
- no lint-imports layer changes, and extraction still imports only core;
- no core dataclass, plugin contract or golden file changes.

Both issues run through the same new path, `isolate.run` → `extract_pdf` →
`read_document`, so I propose **one PR closing both** (see "Open choice").

## How it works today

The reader child (D-581) already sends `("step", "opening" | "page N" | "outline")` to the
parent. `isolate._wait` uses these steps only for the time limit. The parent blocks in
`receive.poll(step_seconds)` with no way to stop early, and `read_document` reports only
`Phase.READING`.

## Design

### extraction (pure, imports only core)

- `isolate.run(..., on_step=None, cancel=None)`:
  - Each step message is passed to `on_step(step)`. A callback that raises does not stop
    the read; its error is logged and dropped.
  - `cancel` is a `threading.Event`. `_wait` polls in slices of 0.1 s, keeping its own
    deadline per step, so the time limit stays exact. When `cancel` is set, the child is
    killed and `Stopped("cancelled", step)` is returned. The `finally` block already joins
    the child and frees the reader slot.
  - `Readers.__enter__` gains the same cancel check while it waits for a free slot, so a
    cancelled job never starts a child.
- The child reports `page N of M` instead of `page N`, where M is the page count PDFium
  gives once the file is open. The existing time-limit messages keep reading "reading
  page N".
- `extract_pdf(path, *, pages=None, cancel=None)`:
  - `pages(n, total)` is called for each page as the child starts it;
  - a cancel raises the new `ReadCancelled(Exception)`. It is **not** an `ExtractionError`,
    so nothing reports it as a damaged file.
  - Both arguments are keyword-only and optional, so every other caller and the
    `EXTRACTORS` table work unchanged.

### app

- `read_document(source, settings, report, *, pages=None, cancel=None)` passes both to
  `extract_pdf`. Other file types read in a fraction of a second and take neither.
  `ReadCancelled` becomes `JobCancelledError`.
- The audio job passes its `cancel` event in. Its `AudioProgress` gains `page: int = 0` and
  `pages: int = 0`, sent with `Phase.READING`.
- The script job gets an optional `pages` callback next to `progress`. Script jobs are not
  cancellable today (web: `cancellable=kind is AUDIO`), and making them cancellable is out
  of scope here.

### web

- The script job's progress becomes `{"phase": "reading", "page": n, "pages": m}`, and the
  audio job's dict gains the same two keys.
- In `app.js`, `describe()` shows "Reading page 120 of 400", and `fraction()` drives the
  progress bar from page / pages.
- The screen-reader announcer keeps its rate limit (D-253).
- English and German strings are added.

### cli

`convert` and `script` print "Reading page 120 of 400" with `\r` on stderr, in the same style
as "Speaking chapter ...". It is not printed with `-q`.

## Tests

- **isolate**, with a module-level slow test target that reports steps and sleeps:
  - the steps reach `on_step` in order;
  - a cancel during a long step ends the child within 1 s and returns `Stopped("cancelled")`;
  - `Readers.alive` is back to 0, and a further `run` starts at once;
  - a cancel while waiting for a slot starts no child;
  - the time limit still fires on time with the sliced poll;
  - an `on_step` that raises does not stop the read.
- **pdf**:
  - `extract_pdf(pages=...)` on a multi-page corpus PDF sees pages 1..N in order, each with
    total N;
  - a cancel raises `ReadCancelled`, not `ExtractionError`.
- **app**: the parent's `_read_file` is patched to a slow, importable test target (the child
  imports it by name).
  - The audio job, cancelled while reading, raises `JobCancelledError`.
  - No reader child is left (`multiprocessing.active_children()`), and the next job reads
    at once.
  - Progress events carry page and pages in order.
- **web**: through TestClient, a script job's events show reading page n of m. A browser
  test checks the job page's text "Reading page …".
- **cli**: `convert` prints the page lines, and prints none with `-q`.

## Open choice

**One PR closing #343 and #344 (recommended).** Both add a keyword to the same three
functions and test the same slow child. Two PRs would mean either stacking the second on the
first or waiting for the first to merge, under the review freeze.

The alternative is two PRs in order: #343 first, then #344 after #343 merges.

## Size

- About 150 lines of code across isolate, pdf, app, web and cli, plus strings.
- About 250 lines of tests.
