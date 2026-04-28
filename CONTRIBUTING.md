# Contributing

## Local Setup

1. Use Python 3.9+.
2. Install deps:
   - `python3 -m pip install -r requirements.txt`
   - `python3 -m pip install pytest`
3. Run:
   - `python3 -m fcc`

## Tests

- `python3 -m pytest -q tests/`

## Commit Guidelines

- Keep commits focused by module/phase.
- Mention the Phase target in commit message, e.g. `phase0: add fcc package entrypoint`.
- Update `CHANGELOG.md` for user-facing changes.

## Pull Requests

- Include problem statement + validation steps.
- Attach screenshots for UI changes.
- Keep backward compatibility with `python3 app.py` unless explicitly deprecating.
