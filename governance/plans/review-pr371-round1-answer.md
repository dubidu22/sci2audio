# PR #371 Review round 1 (D-638), head 0f43871

Fixed exactly S1. `links.py`: when a link's removal takes the space before it, ends at its own ")" or "]", and an opening bracket is glued right after it, the removal keeps one space, so the kept bracket is not glued to the word before.

| printed | 245323a | 0f43871 |
|---|---|---|
| `Text (see https://example.org)(more) here.` | Text(more) here. | Text (more) here. |
| `Text (see https://example.org)(Fig. 3) here.` | Text(Figure 3) here. | Text (Figure 3) here. |
| `Text [see https://example.org][Fig. 3] here.` | Text[Figure 3] here. | Text [Figure 3] here. |
| `Text, (see https://example.org)(more) here.` | Text,(more) here. | Text, (more) here. |
| `Text (siehe https://example.org)(mehr) hier.` | Text(mehr) hier. | Text (mehr) hier. |
| `Text (siehe https://example.org)(Abb. 3) hier.` | Text(Abbildung 3) hier. | Text (Abbildung 3) hier. |

These rows were added to `links-a-link-bracket-glued-to-the-next-bracket` and `de-links-in-brackets-read-the-same-on-a-second-run`; both cases fail on 245323a. The start-of-text row stays `(results) it holds.`. A removed bracket glued after the link still takes the space, so "Text (see https://example.org)(Smith, 2019) more." reads "Text more.".

Checks at 0f43871:
Checks at 0f43871:
- The fast suite passes: 5497 passed, 1 skipped.
- The 13 corpus documents are identical to main 82d9e0d.
- Nightly seeds 7, 555 and 8080 pass on the links and citations tests.
- Token fuzz seeds 1 to 4 (4 × 10,000 texts) give 15, 17, 18 and 12 second-run differences, against 16, 18, 19 and 13 on main 82d9e0d. No input differs on the branch that does not also differ on main.

Deferred by the review: #372 (more than the first citation of a subject nest in brackets, the same on main).
