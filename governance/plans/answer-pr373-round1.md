# PR #373 round 1: answer (head 7a7acb1)

- **S1 fixed.** `player-data` now carries `audiobook`, the stamp of the read-along file the page was drawn for (`pages.listen`). `player.js` sends it with every save, and saves nothing without one. `PositionIn.audiobook` is required (`^[0-9a-f]{16}$`). The route answers **409 `other-audiobook`** and writes nothing when the stamp differs from the current read-along file's (`api.save_position`). The error sentence is in en.toml and de.toml.
  - Test `test_a_new_audiobook_drops_the_saved_position`: save, rerun the audio job at speed 1.5 (a different read-along file), old stamp → 409 and no record, new stamp → 204.
  - `test_a_position_the_audiobook_does_not_have_is_refused` adds a missing stamp and a malformed one (422).
- **N1 fixed.** `resume-continue` and `resume-start` are drawn `disabled`, and `player.js` enables them right after their listeners are added.
  - Browser test `test_the_offer_waits_for_the_script_before_it_can_be_pressed`: it holds `player.js`, reloads with `wait_until="commit"`, asserts both buttons are disabled, releases the script, and asserts both are enabled.
- **Checks.** Fast suite 5589 passed, 1 skipped. Browser suite 65 passed, 1 skipped (#365). ruff, ruff format, lint-imports clean.
- **#376** (the web hint) goes into PR B.
