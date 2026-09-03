## What this changes

<!-- The problem being solved, and why this is the right fix. -->

## How it was verified

<!-- Commands run and what they showed. "Tests pass" alone is not verification
     for a behaviour change — say what you observed. -->

- [ ] `make check` passes (lint, tests, frontend build)
- [ ] New behaviour has a test; a bug fix has a test that fails without the fix
- [ ] Model changes include a migration, with the downgrade verified

## Risk

<!-- What could this break, and how would it show? Note any migration,
     configuration or deployment step required. -->

## Checklist

- [ ] No checkpoint, dataset or `.env` committed
- [ ] Untrained-model warnings and uncertainty semantics left intact
- [ ] Documentation updated if behaviour or setup changed
