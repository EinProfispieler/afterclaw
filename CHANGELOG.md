# Changelog

All notable changes to this project will be documented in this file.

## [0.9.16] - 2026-05-21

### Added

- Subtitle alignment supports mixed-language season patterns such as `第一季` / `第1季` combined with two-digit episode numbers (for example, `第1季.13` -> `S01E13`).

### Changed

- Subtitle alignment compatibility expanded to cover additional token styles in one flow: `SxEx`, `x` style (`8x03`), compact 3-digit style (`213` -> `S02E13`), and Chinese season text variants.
- BitTorrent fix flow now returns stronger diagnostics and applies path-move preference repair for qBittorrent Docker deployments.

## [0.9.15] - 2026-05-21

### Changed

- Improved BitTorrent "Fix permissions" behavior:
  - Supports non-qB clients (`deluge`, `transmission`, `rtorrent`) via their corresponding config/permission repair flow.
  - For Docker qBittorrent, added mount accessibility checks and clear diagnostics when target paths are not mounted into container.
- Stabilized qBittorrent integration around host-network deployments by aligning runtime checks with the active container setup.

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
