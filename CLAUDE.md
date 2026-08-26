# Harmonia: working agreement for Claude Code

Reference this file and HARMONIA_REBUILD_PLAN.md at the start of each session.

## Commit and PR hygiene
Never add a `Co-Authored-By` trailer or any generated-with attribution to commit
messages or PR descriptions.

## Working agreement (from HARMONIA_REBUILD_PLAN.md section 3)
- Confirm the approach before implementing. Propose the change, wait for agreement,
  then write code. Do not batch multiple phases into one commit.
- One phase per session unless told otherwise.
- Tests must pass before a phase is considered done. Report the pytest summary line.
- Prefer paste-ready terminal commands over describing manual file edits.
- Honesty over polish. Known limitations get documented in the README, not hidden.
- Do not overstate certainty. If a claim needs verification, say so and verify it.
- No em dashes in prose written into the repo (README, docs, comments).
- Every phase ends with a short note in CHANGELOG.md.

## Fresh clone setup
This repo stores its git hooks in `.githooks`. After cloning, enable them with:

    git config core.hooksPath .githooks

That activates the `commit-msg` hook, which strips AI attribution trailers as a
safety net.
