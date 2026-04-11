# Visual Annotation MCP Sprint Execution Plan

This plan consolidates a swarm-style analysis pass into one execution package for Sprints 0 through 6.

## Objectives

1. Expand interaction capabilities for real-world UI automation.
2. Deliver robust multi-step flow orchestration with assertions and extraction.
3. Add security, observability, and release hardening for production readiness.

## Sprint Timeline

- Sprint 0: Architecture and contracts
- Sprint 1: Locator and wait reliability
- Sprint 2: Popup and form completion
- Sprint 3: Flow runner v2
- Sprint 4: Assertions and extraction
- Sprint 5: Observability and security
- Sprint 6: Stabilization and release

## Sprint 0 - Architecture and Contracts

### Scope

- Define tool naming and parameter conventions.
- Define error schema and machine-readable error codes.
- Define flow JSON schema v2.
- Add compatibility policy for old flow schema.

### Deliverables

- Tool contract spec in docs.
- Error model and serialization contract.
- Flow schema examples and validation rules.

### Done Criteria

- Every tool request and response has documented fields.
- Validation errors map to stable error codes.

## Sprint 1 - Locator and Wait Reliability

### Scope

- Add deterministic locators:
  - click_by_role
  - click_by_selector
  - fill_by_label
- Add synchronization tools:
  - wait_for_selector
  - wait_for_text
  - wait_for_navigation
- Add stale handle recovery for id-based actions.

### Deliverables

- New MCP tools and BrowserSession implementations.
- Regression tests for covered, hidden, delayed, and stale element scenarios.

### Done Criteria

- Element actions succeed with dynamic page state changes.
- Retry and recovery behavior is deterministic and test-covered.

## Sprint 2 - Popup and Form Completion

### Scope

- Expand blocker handling:
  - detect_blockers
  - dismiss_overlay
  - close_cookie_banner
- Expand form controls:
  - select_option
  - check_uncheck
  - submit_form
  - upload_file

### Deliverables

- Popup and form convenience APIs.
- Flow examples for modal dismissal and signup completion.

### Done Criteria

- Cookie/modal blockers can be cleared in common page patterns.
- Typical signup form can be completed with first-party tools.

## Sprint 3 - Flow Runner v2

### Scope

- Introduce flow state machine and execution context.
- Add variables and interpolation.
- Add branching and retry policy.
- Add on_error behavior: fail, skip, fallback_action.

### Deliverables

- run_flow_v2 with schema validation.
- Structured execution result with per-step status and timing.

### Done Criteria

- Complex flows with conditionals and retries execute reliably.
- Failure output is actionable for LLM planning.

## Sprint 4 - Assertions and Extraction

### Scope

- Assertions:
  - assert_element_exists
  - assert_element_visible
  - assert_text_contains
  - assert_url_matches
- Extraction:
  - extract_element
  - extract_form_data
  - extract_table
  - extract_page_model
- Story mapping:
  - run_story templates with setup/steps/teardown

### Deliverables

- Assertion and extraction tools.
- Story-level templates for repeated journeys.

### Done Criteria

- Flows can assert correctness and return structured page data.
- Reusable story templates run with parameter sets.

## Sprint 5 - Observability and Security

### Scope

- Structured logging and request correlation ids.
- Metrics and optional telemetry.
- URL/file/path hardening and secret redaction in logs.
- Concurrency and timeout hardening.

### Deliverables

- Observability guide and env var controls.
- Security test suite and hardening checklist.

### Done Criteria

- Tool latency and failure trends are measurable.
- Security gates pass with documented threat mitigations.

## Sprint 6 - Stabilization and Release

### Scope

- Coverage and type-check hardening.
- CI matrix and security scans.
- Changelog, deployment docs, release notes.
- RC and GA rollout process.

### Deliverables

- Release candidate pipeline.
- Production-ready docs and migration notes.

### Done Criteria

- CI gates pass for lint, typing, tests, and audit.
- GA release can be shipped with low regression risk.

## Cross-Sprint Rules

- Keep tools backward compatible unless clearly versioned.
- Every new tool requires:
  - docs update
  - one success test
  - one negative-path test
- Error responses must include:
  - error_code
  - action
  - step index when flow-related
  - remediation hint

## Execution Order and Critical Path

1. Contracts and schema first (Sprint 0).
2. Reliable interaction primitives second (Sprints 1-2).
3. Orchestration layer third (Sprint 3).
4. Validation and extraction fourth (Sprint 4).
5. Operational hardening last (Sprints 5-6).

## Program Completion Definition

Program is complete when:

- All sprint done criteria are met.
- Acceptance matrix in docs/sprints/ACCEPTANCE_MATRIX.md is green.
- CI and release gates in docs/sprints/RISKS_AND_GATES.md are green.
- Documentation and examples are fully updated.
