# Review of PR #323, round 2 (#202 inline fractions, D-575)

Reviewed head e0deb8d (one commit on e7ad8c5, no force-push). Verdict: **approved**.

## Items

- **R1-1 fixed.** `geometry.fraction_bar` keeps "every numerator letter over the bar has its middle above it" and measures reach from the nearest one. My probe (liu's "∂E^m_q over ∂q" boxes, superscript lifted 0 / 0.5 / 0.8 / 1.0 / 2.0 pt): all keep " " now (round 1: lost from 1.0 pt). New test pins the 2 pt lift.
- **R1-2 fixed.** `FRACTION_BAR = 0.25`, `LayoutSettings.fraction_bar = 0.25`, comments say why. My probe: "1 over h" in 5 pt with a 0.8 pt bar reads "1 h". The rerun sweep shows the corpus result unchanged from bar 0.12 to 1.0 and reach 0.3 to 3.0, so both defaults have about 2× headroom.
- **R1-3 fixed.** Underline guards in extraction and layout; both pass on e7ad8c5 too, as guards should. My round-1 underline probe (4 words, 5 depths, 2 tucks, 3 rule thicknesses) is identical to main on e0deb8d.
- **R1-4 fixed.** Settings comments name extraction's FRACTION_BAR / FRACTION_REACH.
- **R1-5 fixed.** `separators` defaults come from `LayoutSettings`.
- **R1-6 fixed.** Docstring and settings comment say layout's em is the line's letter size.

Note (no action): `test_a_fraction_over_its_bar_keeps_its_space` now asserts the first line only (`[0]`), because the 5 pt case moves "then more" to a line of its own. The first line still holds the whole fraction and, in the 7 pt cases, "then more", so the check of the fraction is as strong as before.

## Verified

- Fast suite locally on e0deb8d: 4701 passed, 1 skipped (`HYPOTHESIS_PROFILE=ci`); ruff, format, lint-imports (3 kept) clean.
- Goldens unchanged since round 1 (76 snapshots pass; PR diff touches no snapshot).
- Spoken scripts of all 8 papers byte-identical to round 1's head (which differed from main only in liu's 3 sentences).
- CI on e0deb8d green on ubuntu, windows, macos and browser before merge.

Nothing deferred. #322 (liu line-end fraction, reading order) was filed by the author.
