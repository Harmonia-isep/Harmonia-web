# Contributing to Harmonia

Thanks for looking. This is a small project with a specific set of habits, most
of which exist because they were learned the hard way. Reading this first will
save you a round trip.

## Setup

```bash
git clone https://github.com/Harmonia-isep/Harmonia-web.git
cd Harmonia-web
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
git config core.hooksPath .githooks     # see "Commit hygiene" below
```

Run the suite:

```bash
pytest -m "not e2e"     # fast, no browser needed
ruff check .
```

The browser-driven end-to-end tests need Playwright:

```bash
pip install playwright && playwright install chromium
pytest                  # everything
```

## The one rule that matters most: do not claim what you have not measured

Harmonia's README separates its outputs into three tiers: benchmarked against
public ground truth, heuristic with no ground truth, and not measured. That
structure is the point of the project, not decoration.

So:

- **If you change the DSP, run `eval/` and report the delta.** A change to
  `backend/audio/analyzer.py` that improves accuracy without a number attached
  cannot be merged, because nobody can tell whether it improved anything.
- **Negative results are welcome and will be kept.** Several changes in this
  repository were tried, measured, found worse, and reverted, with the
  measurement written down. That record is an asset. If your idea loses, say so
  and we will document it; that is a contribution, not a failure.
- **Do not move a number between tiers without the evidence to justify it.**
  Energy and danceability are heuristics because no ground truth exists for
  them, not because nobody got around to measuring them.

See `eval/README.md` for how to run the harness and what it costs.

## Working habits

- **Propose before implementing** anything larger than a bug fix. Open an issue
  and agree the approach first. This avoids large PRs that need rewriting.
- **One logical change per commit.** A build change and a behaviour change in
  the same commit cannot be bisected apart.
- **Tests must pass before a change is done**, and the PR should quote the
  pytest summary line.
- **Verify, do not assume.** If a claim in a commit message or comment needs
  checking, check it and say what you found. "Should work" is not a result.
- **Document limitations rather than hiding them.** The README has a limitations
  section and it is meant to be used.

## Style

- `ruff check .` must pass. Configuration lives in `pyproject.toml`.
- **No em dashes in prose** written into the repository (README, docs, comments,
  commit messages). Use commas, colons or parentheses.
- Comments should explain *why*, particularly where the code looks odd. Several
  places in this repo look wrong until you know what was measured; those all
  carry a comment saying so.
- Frontend is React with Vite. Source files containing JSX use `.jsx`.

## Commit hygiene

Commit messages should explain the reasoning, not just the change. Look at
`git log` for the register: what was wrong, what was measured, what was decided
and why.

**Never add `Co-Authored-By` trailers or any AI-generated attribution** to
commits or PR descriptions. The `commit-msg` hook in `.githooks/` strips them as
a safety net, which is why the setup step above sets `core.hooksPath`.

## Database changes

The schema is owned by Alembic. If you change a model, generate a migration:

```bash
alembic revision --autogenerate -m "short description"
alembic upgrade head
```

CI runs `alembic upgrade head` against a fresh database and then `alembic check`,
so a model change without a matching migration will fail there.

## Changelog

Every substantive change gets a short entry in `CHANGELOG.md` under the current
phase, saying what changed and, where relevant, what it measured.

## Pull requests

- Target `develop`.
- Say what you changed, why, and how you verified it.
- Include the pytest summary line and, for DSP changes, the eval delta.
- Small and focused beats large and complete.
