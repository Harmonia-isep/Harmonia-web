## What this changes

<!-- What was wrong, and what this does about it. -->

## Why

<!-- The reasoning. If a decision could have gone another way, say why it went this way. -->

## How it was verified

<!--
Not "should work". What did you actually run, and what did it say?
Paste the pytest summary line.
-->

```
pytest -m "not e2e"  ->
ruff check .         ->
```

## If this touches the DSP

<!--
Changes to backend/audio/ need a measurement. Run the eval harness and report
the delta against the baseline in eval/baseline.md. A negative result is a
perfectly good outcome and will be documented rather than discarded.
Delete this section if it does not apply.
-->

- [ ] `eval/` was run and the delta is reported above
- [ ] `eval/baseline.md` updated if the shipped numbers changed
- [ ] README accuracy tiers still accurate (nothing moved tier without evidence)

## Checklist

- [ ] Tests pass, and the summary line is quoted above
- [ ] `ruff check .` passes
- [ ] One logical change (build changes separated from behaviour changes)
- [ ] A `CHANGELOG.md` entry was added
- [ ] A migration was generated if a model changed
- [ ] No em dashes in prose, and no AI attribution trailers in commits
