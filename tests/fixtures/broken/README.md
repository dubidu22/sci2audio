# Broken files for extraction tests

Files that extraction must refuse with a clear message (Issue #23, testing issue #5). Other broken
cases (empty, truncated, not a PDF) are made from the corpus inside the tests, so only files that
can't be made that way are stored here. All are our own work, made for these tests, CC0-1.0.

| File | What it is | Made with |
|---|---|---|
| `password-protected.pdf` | A blank 200 × 200 pt page, encrypted (AES-256, user password `sci2audio`) | pikepdf, once; pikepdf is not a dependency |
