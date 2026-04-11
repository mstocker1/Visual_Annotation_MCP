# Risks and Release Gates

## Top Risks

1. Stale references after dynamic DOM updates.
- Impact: interaction failures in long flows.
- Mitigation: re-inspect fallback + selector remap + bounded retry.

2. Overlay and popup interference.
- Impact: clicks blocked even when target is present.
- Mitigation: blocker detection + overlay dismissal + center coverage checks.

3. Flaky waits and race conditions.
- Impact: inconsistent pass/fail in automation runs.
- Mitigation: explicit waits, normalized timeout model, deterministic step ordering.

4. Flow complexity growth.
- Impact: unreadable flow definitions and poor debuggability.
- Mitigation: schema validation, strict error codes, compact step logs.

5. Performance on heavy pages.
- Impact: slow inspect and screenshot operations.
- Mitigation: max_elements controls, targeted selectors, performance profiling.

6. Security regressions.
- Impact: unsafe navigation or local file abuse.
- Mitigation: allowlist enforcement, path guards, log redaction.

## Quality Gates

### Gate A - Development Quality

- Lint and formatting pass.
- Static typing pass.
- Unit tests pass.

### Gate B - Integration Quality

- Smoke and integration suite pass.
- Dynamic content and overlay scenarios pass.
- Flow v2 behavior tests pass.

### Gate C - Security and Reliability

- URL allowlist regression suite pass.
- Path traversal and input validation tests pass.
- Secret redaction checks pass.

### Gate D - Release Readiness

- Coverage threshold satisfied.
- CI matrix green across supported platforms.
- Changelog, migration notes, and troubleshooting docs updated.

## Release Readiness Checklist

- RC tag prepared.
- All gates A-D green.
- Known issues documented.
- Rollback strategy documented.
- GA tag and publish steps reviewed.
