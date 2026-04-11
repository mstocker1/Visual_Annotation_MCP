# Release Notes and Migration Guidance

This document is the Sprint 6 template for release candidate and GA communications.

## Release Checklist

1. CI quality gates green (`.github/workflows/ci.yml`).
2. Publish build job green (`.github/workflows/publish.yml`).
3. Coverage floor satisfied.
4. Dependency audit passing.
5. Docs updated (`README.md`, operations, contracts).

## Release Notes Template

## [X.Y.Z] - YYYY-MM-DD

### Added
- New MCP tools:
- New flow actions:
- New environment controls:

### Changed
- Behavioral changes:
- Validation or contract updates:
- Observability updates:

### Fixed
- Bug fixes:
- Reliability fixes:

### Security
- Hardening changes:
- New allowlist/policy behavior:

### Performance
- Latency/throughput improvements:

### Migration Notes
- Backward compatibility status:
- Config changes required:
- Deprecated behavior (if any):

### Verification
- Unit tests:
- Smoke test:
- CI run URL:

## Migration Guidance (Current)

### Upgrading to Sprint 5/6 baseline

1. Ensure your MCP config includes required environment controls for your deployment:
- Optional host allowlist: `VISUAL_ANNOTATION_ALLOWED_HOSTS`
- Optional upload path allowlist: `VISUAL_ANNOTATION_ALLOWED_PATHS`
- Optional telemetry events: `VISUAL_ANNOTATION_TELEMETRY=1`
- Development-only unrestricted override: `VISUAL_ANNOTATION_ALLOW_UNRESTRICTED=1`

2. If you rely on `upload_file`, verify files are under approved roots when path allowlist is enabled.

3. Default policy is deny-by-default for navigation and local file access unless allowlists are configured.

4. If you ingest logs, parse JSON lines and key off:
- `request_id`
- `event`
- `tool`

5. For CI consumers, mirror quality gates locally:
- `ruff check .`
- `pydocstyle visual_annotation_mcp`
- `mypy visual_annotation_mcp`
- `coverage run -m unittest discover -s tests -p "test_*.py"`
- `coverage report`

## Rollback Guidance

1. Revert to previous tag.
2. Disable new env controls if they block traffic unexpectedly.
3. Re-run smoke tests against rollback target before restoring service.
