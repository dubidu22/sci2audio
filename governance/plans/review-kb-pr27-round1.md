# Review of sci2audio-design PR #27 (D-129 to D-140), round 1

Result: passed, merged by squash at e3b6606 (12 Nov 2026, about 23:50 UTC). No fixes requested.

Checked:
- Base is main at 4931d7e (top row D-141). Diff touches only `docs/kb/00-index/decision-log.md`: 12 new rows plus the D-100 status pointer.
- Twelve rows D-129 to D-140, newest first between D-141 and D-128, 6 columns each.
- Every row: "Decided (Claude)", coordinator 23:31 UTC under D-80, "Colin informed ... 2026-11-12T23:31:34Z" (matches created_at of the chat post cmsg_...R7JwquJpG3dB4GvcE7iQUx).
- Each row matches plan `issue70-script-job-plan.md` section 9 items (1) to (12) in order, and the chat post.
- D-100 (refined) gets "implemented by D-129 and refined by D-130 to D-133" in its Status cell. D-130 widens D-100's "level-1 section" (a stray top-level deeper section also starts a chapter); D-131 narrows "file name" to "without its extension".
- PR description links code PR #90 with "see" and a plain link; no closes/fixes/resolves.
- No other KB file refers to D-129 to D-140.

Details in the rows beyond plan section 9, checked against code PR #90 head (they match the code):
- D-131 "Untitled" as last fallback (`chapters.py` line 67).
- D-132 German names also include Quellen, Quellenverzeichnis (`chapters.py` line 31; plan section 3 listed only Literatur, Literaturverzeichnis).
- D-135 headings numbered `# n. <title>` and "(nothing to read)" (`report.py` lines 238, 242; plan said `# <title>`).
- D-138 phases reading, layout, text steps, writing, done (`job.py` `Phase`; plan listed a separate cutting phase, the code folds it into text-steps).
- D-139 `appauthor=False, roaming=True`, platformdirs `>=4.14.5,<5` (`config.py` line 39, `pyproject.toml`).
If the code review of PR #90 changes any of these, the KB rows need a follow-up.
