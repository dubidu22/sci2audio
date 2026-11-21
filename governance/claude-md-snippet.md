Paste everything below the line into `CLAUDE.md` at the repository root (create the file if there is none).
Keep it short: it only points to the rules, it is not a second copy of them. It is generated from the
config, so change a setting through the governance skill, never by editing this block.

---

## Project governance

This repository is worked on by several Claude threads under one ruleset, owned by Colin.

Before you do anything else in a session:

1. Say which role you have in one line. The roles are the files in `./governance/rules/`.
   If nobody gave you a role, ask the owner which one before you change any file.
2. Read your extract `./governance/rules/<role>.yaml` and `./governance/project-state.yaml`.
   They bind you. The full ruleset is `./governance/claude-project-rules.yaml`.
3. Do only what that role may do. A change to the rules, the roadmap or an approved contract goes
   through the governance skill and the owner, never through an edit of yours.

Order when two sources disagree: the owner's newest message, then the ruleset, then the decision log
(`./governance/kb/decision-log.md`), then the rest of this file.
