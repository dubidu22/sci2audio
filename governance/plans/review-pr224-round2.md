# Review: PR #224, round 2

14 Nov 2026 ~01:35 UTC. Head cd01ce7 (fix for round 1 F1), then main (9af111e, #222) merged in by this review thread with the update-branch API: head f3eda28.

- F1 fixed as asked: the awk exits at the next `## [` heading or at a link-definition line (`/^\[[^]]+\]: /`), and `test -s` is replaced by `grep -q '[^[:space:]]'`. Checked here with mawk (the awk on ubuntu runners): on R2's CHANGELOG.md (bccc055) it gives the 1.0.0 section, 74 lines, ending with its last entry and no link lines; on a section of blank lines followed by the link list the guard exits 1.
- Nothing else changed in cd01ce7 (release.yml only, 3+/2-).
- **Verdict: approved.** Merge by squash pinned to f3eda28 once "CI passed" is green on it.

**Merged** 14 Nov 2026 ~01:24 UTC by squash, pinned to f3eda28 (all CI checks green, "CI passed" success): 2819458. Nothing deferred.

Tag on a non-main branch (D-490, checked before the merge): `on: push: tags: ["v*"]` runs on any tag push whatever branch holds it, with release.yml as it is at the tagged commit; the version check reads `__init__.py` at that commit; `gh release create --verify-tag` uses the existing tag; PyPI trusted publishing binds repo, workflow file and environment, not a branch. Nothing assumes main.
