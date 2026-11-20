## Review of PR #169, round 2 (head 3b9f656)

S2 is fixed as asked: three tests and the docstring paragraph. I checked them locally. S1 is deferred to #174, which the coordinator put in v1.1 (D-377).

### Must-fix

M1. **`tests (macos-latest)` fails on `test_an_unclosed_html_comment_hides_the_rest_of_the_file`** (job 131981099487). The macOS runner uses CPython 3.12.10. That version's `HTMLParser` does not treat an unclosed `<!--` as a comment: `close()` emits it as data, so `<!-- hello\n\nworld` gives the line `<!-- hello world` instead of failing. Linux (CPython 3.12.16) and Ubuntu's patched 3.12.3 drop it, as the test expects. I reproduced both outcomes against `PageReader` on 3.12.10 and on 3.12.3.

Suggested fix: decide the unclosed comment in `markdown.py` itself, so it does not depend on the interpreter. An `html_block` token whose content starts with `<!--` and has no `-->` is rendered as nothing (a render rule for `html_block` that checks this, or else the default). With that, the three pinned behaviours hold on every Python. Keep the test as it is: it is right, and only the platform was wrong. Then CI needs to be green on all three systems.

The wider problem: about 8 kinds of broken markup read differently on different Python patch levels, and this affects EPUB too. That is filed as #175 and not part of this PR.

## Review of PR #169, round 2 addendum (head 3b9f656)

`tests (windows-latest)` also failed. It runs CPython 3.12.10 too, at C:\hostedtoolcache\...\3.12.10. There are two failures:

- `test_an_unclosed_html_comment_hides_the_rest_of_the_file`: this is M1, the same cause as on macOS.
- `test_pathological_inputs_are_read_in_linear_time[table rows]`: 5.13 s against a 5 s bound. The same case takes about 0.6 s on Linux.

### Must-fix (added)

M2. **Pin the CI Python (decision D-378, on #175).** CI, and the release workflow, use a uv-managed CPython 3.12 at 3.12.16 or newer instead of each runner's own interpreter. For example: pin `.python-version` to the exact patch level, and make setup-uv or the environment use managed Pythons only, so the runners' 3.12.10 is never picked. State that minimum in the install docs and in `docs/release-checklist.md`. Keep M1 as well, so the unclosed-comment test is stable either way.

M3. **The timing bound for table rows is too tight for the Windows runner.** The test is there to catch quadratic behaviour, and quadratic behaviour at 20,000 rows costs minutes, not seconds. Raise the bound (for example to 30 s), or compare against a run of 2,000 rows (time(20,000) < 30 × time(2,000)), so that a slow runner cannot fail it. Do not mark it skip or slow.


## Round 2 answer (9f7c232)

- M1 fixed: `_html_block` render rule drops an html_block that starts with `<!--` and holds no `-->`. A new test checks the rendered HTML itself. The author verified it on a uv-managed 3.12.10, where it fails without the rule and passes with it. Remaining edge for #175: an unclosed `<!--` inside a block of another type (e.g. within `<div>`) still goes to HTMLParser, but CI is now pinned.
- M2 fixed: `.python-version` is 3.12.16, `UV_PYTHON_PREFERENCE: only-managed` is set in ci/nightly/mutation/release, and the README install and development sections plus a release-checklist item state the minimum. `requires-python` stays >=3.12 (patched distro builds); accepted.
- M3 fixed: the timing bound is 30 s.
- The author's note on pre-commit rewriting `.ambr` golden files is filed as #176.
- Main merged into the branch as d85c81b (conflict with #171 in release-checklist.md, both kept; zap.yml got the same Python pin). Locally the fast suite passed: 2853.

## Outcome

CI on 8ea4469 green on all three systems (uv-managed CPython 3.12.16). Squash-merged 13 Nov 2026 18:46 UTC as 5d8fd2f.
