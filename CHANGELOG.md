# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- CI quality workflow with OS/Python matrix in `.github/workflows/ci.yml`.
- Dependency audit stage using `pip-audit`.
- Operations runbook in `docs/OPERATIONS.md`.
- Release notes and migration template in `docs/RELEASE_NOTES_AND_MIGRATION.md`.

### Changed
- Added dev quality tooling configuration in `pyproject.toml` for `ruff`, `mypy`, `pydocstyle`, and `coverage`.
- Added release gate command block and CI badge in `README.md`.
- Tightened flow typing and validation defaults in:
  - `visual_annotation_mcp/flow_executor.py`
  - `visual_annotation_mcp/flow_contracts.py`

### Security
- Added dependency auditing workflow (`pip-audit`) with a temporary ignore for `CVE-2026-1703` affecting bootstrap `pip` in CI runners.

### Verification
- Local validation includes linting, typing, unit tests, coverage reporting, smoke test, and dependency audit.

## [0.1.0] - 2026-04-10

### Added
- Initial public release of Visual Annotation MCP with navigation, inspect, screenshot, and annotation capabilities.
- Flow execution support and dynamic page interaction tools.
