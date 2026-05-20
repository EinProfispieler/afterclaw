# Changelog

All notable changes to this project will be documented in this file.

## [0.9.14] - 2026-05-21

### Added

- Added dedicated `FAQ` main tab on homepage with terminal/SSH host key troubleshooting guidance.
- Added subtitle upload support for `.sup` files.
- Added subtitle alignment token compatibility for `S8E3` and `8x03` patterns.

### Changed

- Improved subtitle upload warning hints to follow current UI language (Chinese/English).
- Updated subtitle-related guidance text to include `.sup` extension.

## [0.9.11] - 2026-05-19

### Changed

- Temporarily disabled the backup feature (Backup tab and `/api/backup/*`
  routes) pending fixes. The `fcc/modules/backup` package remains in the
  tree and can be re-enabled later.

## [0.9.0-dev] - 2026-04-27

### Added

- Introduced `fcc` package entrypoint (`python3 -m fcc`).
- Added Phase 0 scaffolding modules: config/platform/security/registry/web renderer.
- Added cross-platform installer script layout under `scripts/`.
- Added starter tests for config and security helpers.

### Changed

- Runtime is unified as a single implementation in `app.py`.
- `fcc` package entry (`python3 -m fcc`) now calls the same `app.py` runtime.
