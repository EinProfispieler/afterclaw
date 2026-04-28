# Changelog

All notable changes to this project will be documented in this file.

## [0.9.0-dev] - 2026-04-27

### Added

- Introduced `fcc` package entrypoint (`python3 -m fcc`).
- Added Phase 0 scaffolding modules: config/platform/security/registry/web renderer.
- Added cross-platform installer script layout under `scripts/`.
- Added starter tests for config and security helpers.

### Changed

- Runtime is unified as a single implementation in `app.py`.
- `fcc` package entry (`python3 -m fcc`) now calls the same `app.py` runtime.
