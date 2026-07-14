## Summary

<!-- 1–3 sentences: what does this PR do and why? -->

## Related issue

<!-- "Closes #123" or "Ref #123". Use "Closes" to auto-close on merge. -->

## Changes

<!-- Bullet list of what changed. Group by area if large. -->

-

## Checklist

- [ ] `ruff check .` is clean
- [ ] `pytest` passes (with the relevant `[extra]` installed if you touched a backend)
- [ ] New public functions / classes have docstrings
- [ ] Docs updated (`README.md`, `SKILL.md`, `docs/`) if user-facing behavior changed
- [ ] If this adds a backend or embedding provider: registered in the factory (`__init__.py::make_*`), added an `[extra]` in `pyproject.toml`, and added a test class

## Notes for reviewer

<!-- Anything you want eyes on: tricky logic, trade-offs, things you're unsure about. Delete if nothing. -->
