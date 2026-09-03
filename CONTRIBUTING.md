# Contributing

## Setting up

```bash
make install                 # backend (with PyTorch) + frontend dependencies
pip install pre-commit && pre-commit install
make dev                     # API on :8000, front end on :5173
```

## Before you push

```bash
make check                   # lint + backend tests + frontend build
```

CI runs the same gates plus a security scan and a Docker build. A red pipeline
blocks the merge.

## Standards

**Tests.** New behaviour needs a test. A bug fix needs a test that fails without
the fix — several tests in this repository exist because a defect reached a
running system, and each names the defect it pins.

**Formatting.** `ruff format` for Python and ESLint for the front end, both
enforced in CI. Do not hand-format around them.

**Migrations.** Model changes require a migration:

```bash
cd backend && alembic revision --autogenerate -m "what changed"
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

Check the generated file before committing — autogenerate misses data
migrations and some constraint changes, and verify the downgrade actually works.

**Commit messages.** Explain why the change is needed, not just what changed.

## Things to be careful with

- **Never commit a checkpoint or a dataset.** `*.pt` and `data/` are ignored on
  purpose; a pre-commit hook rejects large files.
- **Never weaken the untrained-model warnings.** They exist so an untrained
  deployment cannot be mistaken for an evidential one.
- **Preserve the uncertainty semantics.** Scores near the threshold return
  "inconclusive"; confidence is reported separately from probability. Both are
  deliberate and are covered by tests.
- **Split datasets by source video or speaker, never by frame.** Splitting by
  frame leaks identities across train and test and inflates accuracy.
