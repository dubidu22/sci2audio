# Answer to review of PR #598, round 1

Fix commit cc5e74c on 215842e (test only, no src change).

1. Fixed: `tests/unit/test_app_job.py::test_the_picture_warning_comes_after_the_unreadable_one_and_before_the_rest` runs a PDF of a glyph-number page and an image-only page with no language set, and asserts the three warnings in order: unreadable (page 1), pictures (page 2), language (D-495). Both surviving mutants checked locally: picture warning appended at the end fails it; picture warning put before the unreadable warning fails it.

Deferred: #605 (yours).
