# Review PR #198, round 1 (issue #195, heading property test)

Head c79bf80 (main 14513b2 merged in). This PR changes one test file only. Verdict: **clean, no must-fix or should-fix. Merge.**

## Against the #75 design (D-405 to D-418, D-408 in particular)

D-408: where a page has no heading, each outline entry pointing at it starts a section at the block holding its item, or at the page's first block. That block becomes a HEADING when its text is the entry's title. Otherwise the section starts at that block, titled as the entry (white space folded, `tagged._Headings._from_entry`). The new property says exactly this:
- With positions, it is unchanged: section starts == headings.
- Without positions, every heading still starts a section, and its title is still `title(block.text)`.
- A section that starts at a non-heading block must carry the title of an outline entry for that block's page.

The property is loosened only for content without positions, and only to sections titled after an outline entry on the same page.

## Checks I ran myself

- **The coordinator's case from the #189 thread:** a positionless page whose only line is "0", plus the outline entry ("A", level 1, page 1, item ""). As an `@example` on main 14513b2 it fails with `assert [0] == []`, the same assertion as #195. On the PR it passes under both the `dev` and `nightly` profiles. So it is the same failure as #195, and this PR fixes it.
- **Mutation from the PR body:** if `_from_entry` titles the section `entry.title + "x"`, the test fails. Confirmed.
- **Mutation, D-408's "page without headings" condition:** in `tagged._Headings.build` I changed `elif indexes:` to `if indexes:`, so entries also start sections on pages that have headings. The property test survives this (nightly, run twice), as it did before the PR. It is killed by `test_layout_tagged.py::test_the_first_outline_entry_for_a_page_sets_its_base_level`. I tried a tighter property: on such a page, every HEADING must be the target of an outline entry. It also survived 2000 nightly examples, because the generator rarely makes that combination. So no change is asked: the example test covers the condition.
- **Fast suite on the head:** 3109 passed, 1 skipped.
- **CI** on c79bf80: all checks green.

## Notes (no action)

- N1. The page-without-headings rule is guarded by an example test, not by the property (see above). That is acceptable.
- N2. The schemathesis flake mentioned in the PR body (`PUT /api/v1/settings`, once, dev profile) isn't filed. The author will file it if it shows again; that matches the quarantine rule (two failures).
