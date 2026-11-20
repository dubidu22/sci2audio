# Review of KB PR #38 (D-176 to D-191, #67), round 1

Reviewer thread "Review operators and exponents PR 132", 13 Nov 2026. Head reviewed: `e6e0aa9`.

## Checked

- One file changed, 16 rows added, nothing else touched. Rows D-191 down to D-176 sit between
  D-192 and D-175; the whole log is strictly newest first (script check, no order break).
- Merges cleanly with main `8d647f8` (D-320 added there since the branch was cut).
- Each row against plan §5 A to P: same decision, alternative and reason. Rows that record what
  was built rather than the plan's wording say so (D-187 unit chains, D-191 digits kept instead
  of `num2words`), and match the code of PR #132 at `1c037a1`. D-182 and D-185 also name the
  built details ("a capitalised word before it keeps it a year", "a lone I needs a capitalised
  keyword"), both true of the code.
- Status "Decided (Claude)", 13 Nov 02:00 UTC under D-80, Colin informed at 2026-11-13T02:00:41Z,
  matches the project record for the #67 decision post.
- No "fixes"/"closes" next to a code PR or issue link in the body or rows.

## Findings

1. **D-186 wording (nit):** "volume:page pairs ... excluded". The code excludes a ratio only when
   a range follows ("8:64–77"); "Journal 8:64" alone is read "8 to 64" (a unit test pins this).
   Suggest: "(clock times, a volume with its page range such as "8:64–77", and chains excluded)".
2. **Depends on PR #132 round 1:** if R1 gains the abbreviated keywords (review item 3: "Fig. II",
   "Exp. II"), D-185 should name them; if items are deferred to issues, the rows stay as they are.

## Verdict

Approve after item 1 and, if needed, item 2. Merge right after PR #132 merges (a KB PR goes in
after its code PR); #38 goes before #39 and #40, since it has the lowest numbers.
