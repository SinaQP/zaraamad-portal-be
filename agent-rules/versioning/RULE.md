# Versioning Rule

Use `MAJOR.MINOR.PATCH`.

For this repository, use these rules:

- Patch bump: small bug fix, refactor, cleanup, test/doc update, config-only change, small performance improvement, or small adjustment to existing endpoints that does not introduce a new business capability.
- Minor bump: new feature, new endpoint, new module, new integration, new business flow, or any clearly user-visible capability added to the system.
- Major bump: large breaking change, removed or renamed APIs, major data-contract rewrite, or a release where clients need significant migration work.

Default rule:

- If the change is small and you are unsure, use a patch bump.

Version update checklist:

- Update `APP_VERSION` in `.env.example`.
- Update `APP_VERSION` in `.env`.
- Update `version` in `pyproject.toml`.
- Regenerate `app/version.py` with `python scripts/build_version.py`.
- Keep the README release/versioning section aligned.

Example for this codebase:

- Shared pagination refactor across existing list endpoints with no new business feature: patch bump.
